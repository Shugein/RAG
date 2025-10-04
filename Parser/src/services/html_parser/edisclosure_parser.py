# src/services/html_parser/edisclosure_parser.py
"""
Парсер для E-disclosure.ru, интегрированный в систему
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Source
from src.services.enricher.enrichment_service import EnrichmentService
from .base_html_parser import BaseHTMLParser

logger = logging.getLogger(__name__)


class EDisclosureParser(BaseHTMLParser):
    """Парсер для E-disclosure.ru"""

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
        """Получить список URL статей из E-disclosure"""
        try:
            logger.info(f"Getting article URLs from E-disclosure (max: {max_articles})")
            
            # Получаем URL со страницы всех новостей
            news_list_url = f"{self.base_url}/vse-novosti"
            
            response = self.session.get(news_list_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            article_urls = set()
            
            # Ищем ссылки на новости
            news_links = soup.find_all('a', href=True)
            
            for link in news_links:
                href = link.get('href', '').strip()
                
                if not href:
                    continue
                
                # Проверяем, что это ссылка на новость
                if self._is_news_url(href):
                    full_url = urljoin(self.base_url, href)
                    article_urls.add(full_url)
                    
                    if len(article_urls) >= max_articles:
                        break
            
            # Дополнительный поиск по селекторам
            news_selectors = [
                'a.blacklink',
                '.news-item a',
                '.listitem a',
                '[href*="/news/"]'
            ]
            
            for selector in news_selectors:
                try:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href', '').strip()
                        if href and self._is_news_url(href):
                            full_url = urljoin(self.base_url, href)
                            article_urls.add(full_url)
                            
                            if len(article_urls) >= max_articles:
                                break
                    
                    if len(article_urls) >= max_articles:
                        break
                        
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            urls_list = list(article_urls)[:max_articles]
            logger.info(f"Found {len(urls_list)} article URLs from E-disclosure")
            
            return urls_list
            
        except Exception as e:
            logger.error(f"Error getting article URLs from E-disclosure: {e}")
            return []

    def _is_news_url(self, url: str) -> bool:
        """Проверяет, является ли URL ссылкой на новость E-disclosure"""
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
        
        # Ищем паттерны новостей E-disclosure
        news_patterns = [
            r'/news/',
            r'/event/',
            r'/message/',
            r'/disclosure/',
            r'/report/',
            r'/announcement/',
            r'/press-release/'
        ]
        
        for pattern in news_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        
        return False

    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        """Парсить отдельную статью E-disclosure"""
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
            
            # Извлекаем метаданные
            metadata = self._extract_metadata(soup, url)
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': 'e-disclosure.ru',
                'date': publish_date,
                'parser': 'edisclosure',
                'metadata': metadata
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
        content_selectors = [
            '.news-content',
            '.article-content',
            '.content',
            '.news-text',
            '.article-text',
            'div[class*="content"]',
            'div[class*="text"]',
            '.main-content p',
            'article p',
            'main p'
        ]
        
        for selector in content_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    texts = []
                    for elem in elements:
                        text = elem.get_text(strip=True)
                        if text and len(text) > 20:
                            texts.append(text)
                    
                    if texts:
                        full_content = '\n\n'.join(texts)
                        if len(full_content) > 100:
                            return full_content
            except:
                continue
        
        # Fallback - ищем все параграфы
        try:
            paragraphs = soup.find_all('p')
            texts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50:
                    texts.append(text)
            
            if texts:
                return '\n\n'.join(texts)
        except:
            pass
        
        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Извлекает дату публикации"""
        date_selectors = [
            'time[datetime]',
            '.date',
            '.publish-date',
            '.news-date',
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
        elif '/event/' in url:
            metadata['document_type'] = 'event'
        elif '/message/' in url:
            metadata['document_type'] = 'message'
        elif '/disclosure/' in url:
            metadata['document_type'] = 'disclosure'
        else:
            metadata['document_type'] = 'unknown'
        
        # Извлекаем теги/категории
        tags = []
        tag_selectors = ['.tags a', '.categories a', '.keywords a', '[class*="tag"] a']
        for selector in tag_selectors:
            try:
                tag_elements = soup.select(selector)
                for elem in tag_elements:
                    tag = elem.get_text(strip=True)
                    if tag and tag not in tags:
                        tags.append(tag)
            except:
                continue
        
        if tags:
            metadata['tags'] = tags[:10]  # Ограничиваем количество тегов
        
        return metadata
