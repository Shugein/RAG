# src/services/html_parser/forbes_parser.py
"""
Парсер для Forbes.ru, интегрированный в систему
"""

import logging
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Source
from src.services.enricher.enrichment_service import EnrichmentService
from .base_html_parser import BaseHTMLParser

logger = logging.getLogger(__name__)


class ForbesParser(BaseHTMLParser):
    """Парсер для Forbes.ru"""

    def __init__(
        self,
        source: Source,
        db_session: AsyncSession,
        enricher: Optional[EnrichmentService] = None
    ):
        super().__init__(source, db_session, enricher)
        
        self.base_url = "https://www.forbes.ru"
        self.session = requests.Session()
        
        # Специальные headers для обхода защиты Forbes
        mobile_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/120.0 Firefox/120.0',
            'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        ]
        
        self.current_agent = mobile_agents[0]
        self.mobile_agents = mobile_agents
        
        self.session.headers.update({
            'User-Agent': self.current_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
        
        # Доступные разделы
        self.sections = {
            'biznes': {
                'url': '/biznes/',
                'name': 'Бизнес'
            },
            'investicii': {
                'url': '/investicii/', 
                'name': 'Инвестиции'
            }
        }

    async def get_article_urls(self, max_articles: int = 100) -> List[str]:
        """Получить список URL статей из всех доступных разделов"""
        all_urls = []
        articles_per_section = max_articles // len(self.sections)
        
        for section_name in self.sections.keys():
            section_urls = await self._get_section_urls(section_name, articles_per_section)
            all_urls.extend(section_urls)
            
            if len(all_urls) >= max_articles:
                break
        
        return all_urls[:max_articles]

    async def _get_section_urls(self, section_name: str, max_articles: int = 50) -> List[str]:
        """Получить URL статей из указанного раздела"""
        if section_name not in self.sections:
            logger.error(f"Unknown section: {section_name}")
            return []
        
        section_info = self.sections[section_name]
        section_url = self.base_url + section_info['url']
        
        logger.info(f"Collecting URLs from {section_info['name']}: {section_url}")
        
        try:
            # Пробуем несколько раз с разными user-agent
            response = None
            
            for attempt in range(len(self.mobile_agents)):
                self.session.headers['User-Agent'] = self.mobile_agents[attempt]
                
                logger.debug(f"Attempt {attempt + 1} with agent: {self.mobile_agents[attempt][:50]}...")
                
                time.sleep(2)  # Пауза перед запросом
                
                response = self.session.get(section_url, timeout=20)
                
                logger.debug(f"Status: {response.status_code}, size: {len(response.content)} bytes")
                
                if response.status_code == 200:
                    content_lower = response.text.lower()
                    if ('captcha' not in content_lower and 
                        'yandex' not in content_lower and 
                        len(response.content) > 20000):
                        logger.info(f"Successful request on attempt {attempt + 1}")
                        break
                    else:
                        logger.warning("Captcha or blocking detected")
                        response = None
                else:
                    logger.warning(f"Status error: {response.status_code}")
                    response = None
            
            if not response or response.status_code != 200:
                logger.error(f"Could not access {section_url} after all attempts")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Поиск ссылок на статьи
            article_urls = set()
            
            # Ищем все ссылки
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '').strip()
                text = link.get_text(strip=True)
                
                if not href or not text or len(text) < 10:
                    continue
                
                # Преобразуем относительные ссылки в абсолютные
                if href.startswith('/'):
                    href = self.base_url + href
                elif not href.startswith('http'):
                    continue
                
                # Фильтруем по паттернам Forbes статей
                if self._is_article_url(href):
                    article_urls.add(href)
                    
                    if len(article_urls) >= max_articles:
                        break
            
            # Дополнительный поиск по специфичным селекторам
            article_selectors = [
                'article a[href*="/"]',
                '.article-item a[href*="/"]',
                '.news-item a[href*="/"]',
                '.story-item a[href*="/"]',
                '[class*="article"] a[href*="/"]',
                '[class*="story"] a[href*="/"]'
            ]
            
            for selector in article_selectors:
                try:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href', '').strip()
                        
                        if href.startswith('/'):
                            href = self.base_url + href
                        
                        if self._is_article_url(href):
                            article_urls.add(href)
                            
                            if len(article_urls) >= max_articles:
                                break
                                
                    if len(article_urls) >= max_articles:
                        break
                        
                except Exception as e:
                    continue
            
            urls_list = list(article_urls)[:max_articles]
            logger.info(f"Found {len(urls_list)} article URLs in {section_info['name']}")
            
            return urls_list
            
        except Exception as e:
            logger.error(f"Error getting URLs from section {section_name}: {e}")
            return []

    def _is_article_url(self, url: str) -> bool:
        """Проверяет, является ли URL ссылкой на статью Forbes"""
        if not url or 'forbes.ru' not in url:
            return False
            
        # Исключаем служебные страницы
        exclude_patterns = [
            '/forbes-heroes',
            '/sustainability/',
            '/about',
            '/contacts',
            '/advertising',
            '/subscription',
            '/rss',
            '/sitemap',
            '/privacy',
            '/terms'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False
        
        # Ищем паттерны статей Forbes
        article_patterns = [
            r'/[a-z-]+/\d+',  # /biznes/547083-...
            r'/article/',
            r'/news/',
            r'/story/',
            r'/post/'
        ]
        
        for pattern in article_patterns:
            if re.search(pattern, url):
                return True
        
        # Дополнительная проверка: URL должен содержать цифры (ID статьи)
        if re.search(r'/\d{4,}', url):
            return True
            
        return False

    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        """Парсить отдельную статью Forbes"""
        try:
            # Пробуем разные user-agent для статьи
            response = None
            
            for attempt in range(len(self.mobile_agents)):
                self.session.headers['User-Agent'] = self.mobile_agents[attempt]
                
                time.sleep(2)  # Пауза между запросами
                
                response = self.session.get(url, timeout=20)
                
                if response.status_code == 200:
                    content_lower = response.text.lower()
                    if ('captcha' not in content_lower and 
                        'yandex' not in content_lower and 
                        len(response.content) > 10000):
                        break
                    else:
                        response = None
                        
                time.sleep(1)
            
            if not response or response.status_code != 200:
                logger.warning(f"Could not access article: {url}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            date = self._extract_date(soup)
            
            if not title or not content:
                return None
            
            source_url = urlparse(url).netloc
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': source_url,
                'date': date,
                'parser': 'forbes'
            }
            
        except Exception as e:
            logger.error(f"Error parsing article {url}: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок статьи"""
        title_selectors = [
            'h1',
            '.article-title',
            '.headline',
            '.title',
            '[class*="title"]',
            'title'
        ]
        
        for selector in title_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True)
                    if title and len(title) > 10:
                        return title
            except:
                continue
        
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлекает основной текст статьи Forbes"""
        content_selectors = [
            '.article-content p',
            '.article-body p',
            '.content p',
            '.text p',
            'article p',
            '.article p',
            '[class*="content"] p',
            '[class*="text"] p',
            '[class*="body"] p',
            '.story-content p',
            '.post-content p'
        ]
        
        for selector in content_selectors:
            try:
                paragraphs = soup.select(selector)
                if paragraphs:
                    content_parts = []
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 20:
                            content_parts.append(text)
                    
                    if content_parts:
                        full_content = ' '.join(content_parts)
                        if len(full_content) > 100:
                            return full_content
            except:
                continue
        
        try:
            # Удаляем ненужные элементы
            for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                unwanted.decompose()
            
            # Ищем все параграфы
            all_paragraphs = soup.find_all('p')
            content_parts = []
            
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 30:
                    content_parts.append(text)
            
            if content_parts:
                return ' '.join(content_parts)
                
        except:
            pass
        
        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Извлекает дату публикации"""
        date_selectors = [
            'time[datetime]',
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
                    datetime_attr = element.get('datetime')
                    if datetime_attr:
                        return datetime_attr
                    
                    date_text = element.get_text(strip=True)
                    if date_text and len(date_text) < 50:
                        return date_text
            except:
                continue
        
        return datetime.now().strftime('%Y-%m-%d')
