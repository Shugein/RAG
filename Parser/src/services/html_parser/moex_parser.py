#Parser.src/services/html_parser/moex_parser.py
"""
Парсер для MOEX (Московская биржа), интегрированный в систему
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


class MOEXParser(BaseHTMLParser):
    """Парсер для MOEX (Московская биржа)"""

    def __init__(
        self,
        source: Source,
        db_session: AsyncSession,
        enricher: Optional[EnrichmentService] = None
    ):
        super().__init__(source, db_session, enricher)
        
        self.base_url = "https://www.moex.com"
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
        """Получить список URL статей из MOEX"""
        try:
            logger.info(f"Getting article URLs from MOEX (max: {max_articles})")
            
            # URL страницы новостей MOEX
            news_page_url = f"{self.base_url}/ru/news/"
            
            response = self.session.get(news_page_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            article_urls = set()
            
            # Ищем контейнер с новостями
            news_container = soup.find('div', class_='new-moex-news-list')
            if news_container:
                # Ищем ссылки на новости
                news_links = news_container.find_all('a', class_='new-moex-news-list__link')
                
                for link in news_links:
                    href = link.get('href')
                    if href and self._is_news_url(href):
                        if href.startswith('/'):
                            full_url = f"{self.base_url}{href}"
                        else:
                            full_url = href
                        
                        article_urls.add(full_url)
                        
                        if len(article_urls) >= max_articles:
                            break
            
            # Дополнительный поиск по другим селекторам
            additional_selectors = [
                'a[href*="/n"]',
                '.news-item a',
                '.news-list a',
                '[href*="/news/"]',
                '[href*="/press/"]'
            ]
            
            for selector in additional_selectors:
                try:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href', '').strip()
                        if href and self._is_news_url(href):
                            if href.startswith('/'):
                                full_url = f"{self.base_url}{href}"
                            else:
                                full_url = href
                            
                            article_urls.add(full_url)
                            
                            if len(article_urls) >= max_articles:
                                break
                    
                    if len(article_urls) >= max_articles:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            urls_list = list(article_urls)[:max_articles]
            logger.info(f"Found {len(urls_list)} article URLs from MOEX")
            
            return urls_list
            
        except Exception as e:
            logger.error(f"Error getting article URLs from MOEX: {e}")
            return []

    def _is_news_url(self, url: str) -> bool:
        """Проверяет, является ли URL ссылкой на новость MOEX"""
        if not url:
            return False
        
        # Исключаем служебные страницы
        exclude_patterns = [
            '/auth/',
            '/search/',
            '/download/',
            '/upload/',
            'javascript:',
            'mailto:',
            '#',
            '.pdf',
            '.xlsx',
            '.doc',
            '/help/',
            '/about/',
            '/contacts/',
            '/privacy/',
            '/terms/',
            '/sitemap/'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False
        
        # Ищем паттерны новостей MOEX
        news_patterns = [
            r'/n\d+',  # /n123456
            r'/news/',
            r'/press/',
            r'/announcement/',
            r'/press-release/'
        ]
        
        for pattern in news_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        return False

    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        """Парсить отдельную статью MOEX"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Извлекаем заголовок
            title = self._extract_title(soup)
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
            
            # Извлекаем теги
            tags = self._extract_tags(soup)
            
            # Извлекаем метаданные
            metadata = self._extract_metadata(soup, url)
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': 'moex.com',
                'date': publish_date,
                'parser': 'moex',
                'metadata': {
                    **metadata,
                    'tags': tags
                }
            }
            
        except Exception as e:
            logger.error(f"Error parsing article {url}: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок статьи"""
        title_selectors = [
            'h1',
            '.news-title',
            '.article-title',
            '.title',
            '[class*="title"]',
            'title'
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
        
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлекает основной текст статьи"""
        # Сначала пробуем найти основной контент
        content_selectors = [
            '.news-content',
            '.article-content',
            '.content',
            '.news-text',
            '.article-text',
            '.main-content',
            'article',
            'main'
        ]
        
        for selector in content_selectors:
            try:
                content_element = soup.select_one(selector)
                if content_element:
                    # Ищем параграфы внутри контентного элемента
                    paragraphs = content_element.find_all('p')
                    if paragraphs:
                        texts = []
                        for p in paragraphs:
                            text = p.get_text(strip=True)
                            if text and len(text) > 20:
                                # Фильтруем рекламные тексты
                                if not any(word in text.lower() for word in [
                                    'подписаться', 'реклама', 'cookie', 'javascript', 
                                    'загрузить', 'скачать', 'продолжить чтение'
                                ]):
                                    texts.append(text)
                        
                        if texts:
                            full_content = ' '.join(texts)
                            if len(full_content) > 50:
                                return full_content
            except:
                continue
        
        # Fallback - ищем все параграфы на странице
        try:
            paragraphs = soup.find_all('p')
            texts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50:
                    # Фильтруем рекламные тексты
                    if not any(word in text.lower() for word in [
                        'подписаться', 'реклама', 'cookie', 'javascript',
                        'загрузить', 'скачать', 'продолжить чтение'
                    ]):
                        texts.append(text)
            
            if texts:
                return ' '.join(texts)
        except:
            pass
        
        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Извлекает дату публикации"""
        date_selectors = [
            'time[datetime]',
            '.news_date',
            '.date',
            '.publish-date',
            '.article-date',
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

    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает теги статьи"""
        tags = []
        
        tag_selectors = [
            '.tags a',
            '.keywords a',
            '.categories a',
            '[class*="tag"] a',
            '[class*="keyword"] a',
            '[class*="category"] a'
        ]
        
        for selector in tag_selectors:
            try:
                tag_elements = soup.select(selector)
                for elem in tag_elements:
                    tag = elem.get_text(strip=True)
                    if tag and tag not in tags and len(tag) < 50:
                        tags.append(tag)
            except:
                continue
        
        return tags[:10]  # Ограничиваем количество тегов

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> dict:
        """Извлекает метаданные статьи"""
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
        
        # Определяем тип документа по URL
        if '/news/' in url:
            metadata['document_type'] = 'news'
        elif '/press/' in url:
            metadata['document_type'] = 'press_release'
        elif '/announcement/' in url:
            metadata['document_type'] = 'announcement'
        else:
            metadata['document_type'] = 'unknown'
        
        # Определяем язык (MOEX обычно русский)
        metadata['language'] = 'ru'
        
        return metadata
