#Parser.src/services/html_parser/edisclosure_messages_parser.py
"""
Парсер для сообщений E-disclosure.ru, интегрированный в систему
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from Parser.src.core.models import Source
from Parser.src.services.enricher.enrichment_service import EnrichmentService
from .base_html_parser import BaseHTMLParser

logger = logging.getLogger(__name__)


class EDisclosureMessagesParser(BaseHTMLParser):
    """Парсер для сообщений E-disclosure.ru"""

    def __init__(
        self,
        source: Source,
        db_session: AsyncSession,
        enricher: Optional[EnrichmentService] = None
    ):
        super().__init__(source, db_session, enricher)
        
        self.base_url = "https://www.e-disclosure.ru"
        self.session = requests.Session()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    async def get_article_urls(self, max_articles: int = 100) -> List[str]:
        """Получить список URL сообщений из E-disclosure"""
        try:
            logger.info(f"Getting message URLs from E-disclosure (max: {max_articles})")
            
            # URL страницы поиска сообщений
            messages_url = f"{self.base_url}/poisk-po-soobshheniyam"
            
            response = self.session.get(messages_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            message_urls = set()
            
            # Ищем таблицы с сообщениями
            tables = soup.find_all('table')
            
            for table in tables:
                try:
                    tbody = table.find('tbody')
                    if tbody:
                        rows = tbody.find_all('tr')
                        
                        for row in rows:
                            # Ищем ссылки в строке
                            links = row.find_all('a', href=True)
                            for link in links:
                                href = link.get('href', '').strip()
                                if href and self._is_message_url(href):
                                    full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                                    message_urls.add(full_url)
                                    
                                    if len(message_urls) >= max_articles:
                                        break
                            
                            if len(message_urls) >= max_articles:
                                break
                    
                    if len(message_urls) >= max_articles:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error processing table: {e}")
                    continue
            
            # Дополнительный поиск по селекторам
            message_selectors = [
                'a[href*="EventId="]',
                'a[href*="/message/"]',
                'a[href*="/event/"]',
                'a[href*="/disclosure/"]'
            ]
            
            for selector in message_selectors:
                try:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href', '').strip()
                        if href and self._is_message_url(href):
                            full_url = f"{self.base_url}{href}" if href.startswith('/') else href
                            message_urls.add(full_url)
                            
                            if len(message_urls) >= max_articles:
                                break
                    
                    if len(message_urls) >= max_articles:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            urls_list = list(message_urls)[:max_articles]
            logger.info(f"Found {len(urls_list)} message URLs from E-disclosure")
            
            return urls_list
            
        except Exception as e:
            logger.error(f"Error getting message URLs from E-disclosure: {e}")
            return []

    def _is_message_url(self, url: str) -> bool:
        """Проверяет, является ли URL ссылкой на сообщение E-disclosure"""
        if not url:
            return False
        
        # Исключаем служебные страницы
        exclude_patterns = [
            '/search',
            '/auth',
            '/login',
            '/register',
            '/about',
            '/contacts',
            '/help',
            '/faq',
            '/privacy',
            '/terms',
            '/sitemap',
            '/rss',
            '/api/',
            'javascript:',
            'mailto:',
            '#'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False
        
        # Ищем паттерны сообщений E-disclosure
        message_patterns = [
            r'EventId=',
            r'/message/',
            r'/event/',
            r'/disclosure/',
            r'/report/',
            r'/announcement/'
        ]
        
        for pattern in message_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        return False

    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        """Парсить отдельное сообщение E-disclosure"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлекаем заголовок
            title = self._extract_title(soup, url)
            if not title:
                logger.warning(f"No title found for {url}")
                return None
            
            # Извлекаем контент
            content = self._extract_content(soup)
            if not content:
                logger.warning(f"No content found for {url}")
                return None
            
            # Извлекаем дату
            publish_date = self._extract_date(soup)
            
            # Извлекаем метаданные
            metadata = self._extract_metadata(soup, url)
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': 'e-disclosure.ru',
                'date': publish_date,
                'parser': 'edisclosure_messages',
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Error parsing message {url}: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup, url: str) -> str:
        """Извлекает заголовок сообщения"""
        # Сначала пробуем стандартные селекторы
        title_selectors = [
            'h1',
            '.message-title',
            '.event-title',
            '.disclosure-title',
            '.title',
            '[class*="title"]'
        ]
        
        for selector in title_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True)
                    if title and len(title) > 5:
                        return title
            except:
                continue
        
        # Для сообщений E-disclosure пробуем извлечь из URL или мета-тегов
        try:
            # Извлекаем EventId из URL
            event_id_match = re.search(r'EventId=([^&]+)', url)
            if event_id_match:
                event_id = event_id_match.group(1)
                return f"E-disclosure сообщение {event_id}"
        except:
            pass
        
        # Пробуем meta теги
        try:
            og_title = soup.find('meta', attrs={'property': 'og:title'})
            if og_title:
                title = og_title.get('content', '').strip()
                if title:
                    return title
            
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text(strip=True)
                if title and title != "E-disclosure":
                    return title
        except:
            pass
        
        return "E-disclosure сообщение"

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлекает основной текст сообщения"""
        # Ищем блок с содержимым сообщения
        content_selectors = [
            'div[style*="word-break: break-word"][style*="word-wrap: break-word"][style*="white-space: pre-wrap"]',
            'div[style*="pre-wrap"]',
            '.message-content',
            '.event-content',
            '.disclosure-content',
            '.content',
            '.message-text',
            '.event-text'
        ]
        
        for selector in content_selectors:
            try:
                content_element = soup.select_one(selector)
                if content_element:
                    content_text = content_element.get_text(strip=True)
                    if content_text and len(content_text) > 20:
                        return content_text
            except:
                continue
        
        # Fallback - ищем все div с содержимым
        try:
            content_divs = soup.find_all('div', style=True)
            for div in content_divs:
                style = div.get('style', '')
                if 'pre-wrap' in style or 'break-word' in style:
                    content_text = div.get_text(strip=True)
                    if content_text and len(content_text) > 50:
                        return content_text
        except:
            pass
        
        # Последний fallback - ищем все параграфы
        try:
            paragraphs = soup.find_all('p')
            texts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 30:
                    texts.append(text)
            
            if texts:
                return '\n\n'.join(texts)
        except:
            pass
        
        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Извлекает дату сообщения"""
        date_selectors = [
            'time[datetime]',
            '.date',
            '.message-date',
            '.event-date',
            '.disclosure-date',
            '[class*="date"]',
            '[class*="time"]'
        ]
        
        for selector in date_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    # Пробуем атрибут datetime
                    datetime_attr = element.get('datetime')
                    if datetime_attr:
                        return datetime_attr
                    
                    # Пробуем текст элемента
                    date_text = element.get_text(strip=True)
                    if date_text and len(date_text) < 50:
                        return date_text
            except:
                continue
        
        return datetime.now().strftime('%Y-%m-%d')

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> dict:
        """Извлекает метаданные сообщения"""
        metadata = {}
        
        # Извлекаем meta теги
        meta_tags = {
            'description': soup.find('meta', attrs={'name': 'description'}),
            'keywords': soup.find('meta', attrs={'name': 'keywords'}),
            'author': soup.find('meta', attrs={'name': 'author'}),
            'og:title': soup.find('meta', attrs={'property': 'og:title'}),
            'og:description': soup.find('meta', attrs={'property': 'og:description'}),
        }
        
        for key, tag in meta_tags.items():
            if tag:
                content = tag.get('content', '').strip()
                if content:
                    metadata[key] = content
        
        # Извлекаем EventId из URL
        try:
            event_id_match = re.search(r'EventId=([^&]+)', url)
            if event_id_match:
                metadata['event_id'] = event_id_match.group(1)
        except:
            pass
        
        # Определяем тип документа по URL
        if '/message/' in url:
            metadata['document_type'] = 'message'
        elif '/event/' in url:
            metadata['document_type'] = 'event'
        elif '/disclosure/' in url:
            metadata['document_type'] = 'disclosure'
        elif '/report/' in url:
            metadata['document_type'] = 'report'
        else:
            metadata['document_type'] = 'unknown'
        
        # Определяем, что это корпоративное сообщение
        metadata['is_corporate_message'] = True
        metadata['regulatory_source'] = 'e-disclosure'
        
        return metadata
