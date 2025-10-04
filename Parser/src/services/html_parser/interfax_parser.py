# src/services/html_parser/interfax_parser.py
"""
Парсер для Interfax.ru, интегрированный в систему
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Source
from src.services.enricher.enrichment_service import EnrichmentService
from .base_html_parser import BaseHTMLParser

logger = logging.getLogger(__name__)


class InterfaxParser(BaseHTMLParser):
    """Парсер для Interfax.ru"""

    def __init__(
        self,
        source: Source,
        db_session: AsyncSession,
        enricher: Optional[EnrichmentService] = None
    ):
        super().__init__(source, db_session, enricher)
        
        self.base_url = "https://www.interfax.ru"
        self.session = requests.Session()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })
        
        # Поддерживаемые категории
        self.supported_categories = {"business", "world", "russia", "culture", "all"}

    async def get_article_urls(self, max_articles: int = 100) -> List[str]:
        """Получить список URL статей за последние дни"""
        all_urls = []
        
        # Собираем за последние 3 дня
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)
        
        # Категории для сбора
        categories = ["business", "all"]  # Основные категории
        
        current_date = start_date
        while current_date <= end_date and len(all_urls) < max_articles:
            for category in categories:
                if len(all_urls) >= max_articles:
                    break
                    
                day_urls = await self._collect_day_links(
                    category, 
                    current_date, 
                    max_pages=5  # Ограничиваем количество страниц
                )
                all_urls.extend(day_urls)
            
            current_date += timedelta(days=1)
        
        # Убираем дубликаты и ограничиваем
        unique_urls = list(set(all_urls))[:max_articles]
        logger.info(f"Collected {len(unique_urls)} unique URLs from Interfax")
        
        return unique_urls

    async def _collect_day_links(
        self, 
        category: str, 
        day: datetime, 
        max_pages: int = 5
    ) -> List[str]:
        """Собрать ссылки за день"""
        if category not in self.supported_categories:
            logger.warning(f"Unsupported category: {category}")
            return []
        
        page = 1
        found_urls = set()
        hard_limit = 20  # Безопасный лимит
        
        while page <= max_pages and page <= hard_limit:
            try:
                # Формируем URL
                if page == 1:
                    url = self._day_list_url(category, day)
                else:
                    base = self._day_list_url(category, day).rstrip('/')
                    url = base + f"/all/page_{page}"
                
                logger.debug(f"Fetching page {page} for {category} on {day.date()}: {url}")
                
                response = self.session.get(url, timeout=20)
                
                if response.status_code != 200:
                    logger.info(f"HTTP {response.status_code} for {url}")
                    break
                
                if response.encoding == 'ISO-8859-1':
                    response.encoding = 'windows-1251'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                links = self._extract_article_links_from_listing(soup)
                
                if not links:
                    logger.info(f"No links found on page {page}")
                    break
                
                new_count = 0
                for href, title in links:
                    full_url = self._full_url(href)
                    if full_url not in found_urls:
                        found_urls.add(full_url)
                        new_count += 1
                
                logger.debug(f"[{category}:{day.date()}] page {page}: found {len(links)}, new {new_count}, total {len(found_urls)}")
                
                page += 1
                time.sleep(0.4)  # Задержка между запросами
                
            except Exception as e:
                logger.error(f"Error collecting links for {category} on {day.date()}, page {page}: {e}")
                break
        
        return list(found_urls)

    def _day_list_url(self, category: str, day: datetime) -> str:
        """Сформировать URL списка новостей за день"""
        y, m, d = day.strftime('%Y'), day.strftime('%m'), day.strftime('%d')
        if category == "all":
            return f"{self.base_url}/news/{y}/{m}/{d}"
        else:
            return f"{self.base_url}/{category}/news/{y}/{m}/{d}"

    def _extract_article_links_from_listing(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """Извлечь ссылки на статьи из списка"""
        results = []
        anchors = soup.find_all('a', href=True)
        
        for a in anchors:
            href = a['href']
            if not href:
                continue
                
            # Паттерн для ссылок на статьи Interfax
            if re.search(r'^/(?:business|world|russia|culture)/\d+(?:[/?#].*)?$', href):
                title = a.get_text(strip=True) or "Без заголовка"
                results.append((href, title))
        
        return results

    def _full_url(self, href: str) -> str:
        """Преобразовать относительный URL в абсолютный"""
        if href.startswith('http://') or href.startswith('https://'):
            return href
        if not href.startswith('/'):
            href = '/' + href
        return f"{self.base_url}{href}"

    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        """Парсить отдельную статью Interfax"""
        try:
            response = self.session.get(url, timeout=25)
            
            if response.status_code != 200:
                logger.info(f"HTTP {response.status_code} for {url}")
                return None
            
            if response.encoding == 'ISO-8859-1':
                response.encoding = 'windows-1251'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Извлекаем заголовок
            h1 = soup.find('h1')
            title = h1.get_text(strip=True) if h1 else "Без заголовка"
            
            # Извлекаем контент
            content = self._extract_best_content(soup)
            if not content:
                logger.warning(f"No content found for {url}")
                return None
            
            # Извлекаем дату
            publish_date = self._extract_best_datetime(soup, response.text)
            
            # Извлекаем теги
            tags = self._extract_all_tags(soup)
            
            # Извлекаем финансовые сущности
            entities = self._extract_financial_entities(content)
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': 'interfax.ru',
                'date': publish_date,
                'parser': 'interfax',
                'metadata': {
                    'tags': tags,
                    'entities': entities
                }
            }
            
        except Exception as e:
            logger.error(f"Error parsing article {url}: {e}")
            return None

    def _extract_best_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Извлечь лучший контент статьи"""
        # Пробуем найти article тег
        article = soup.find('article')
        if article:
            for tag in article.find_all(['script', 'style', 'noscript', 'aside']):
                tag.decompose()
            text = article.get_text(separator='\n', strip=True)
            if len(text) > 120:
                return self._clean_content(text)
        
        # Пробуем все параграфы
        paragraphs = []
        for p in soup.find_all('p'):
            t = p.get_text(strip=True)
            if len(t) > 25 and not any(x in t.lower() for x in [
                'читайте также', 'подписаться', 'материалы по теме', 'реклама', '©', 'загрузить еще', 'выбрать дату'
            ]):
                paragraphs.append(t)
        
        if paragraphs:
            content = '\n\n'.join(paragraphs)
            if len(content) > 120:
                return self._clean_content(content)
        
        return None

    def _clean_content(self, text: str) -> str:
        """Очистить контент от лишних элементов"""
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        lines = [ln.strip() for ln in text.split('\n')]
        cleaned = []
        
        for ln in lines:
            if len(ln) > 10 and not any(x in ln.lower() for x in [
                'загрузить еще', 'подписаться на новости', 'самое читаемое', 'фотогалереи', 'выбор редакции'
            ]):
                cleaned.append(ln)
        
        return '\n'.join(cleaned)

    def _extract_all_tags(self, soup: BeautifulSoup) -> List[str]:
        """Извлечь все теги"""
        tags = set()
        selectors = [
            '.tags a', '.article-tags a', '[rel="tag"]',
            'a[href*="/tags/"]', 'a[href*="/company/"]',
            '.related a', '.keywords a'
        ]
        
        for css in selectors:
            for el in soup.select(css):
                t = el.get_text(strip=True)
                if t and 2 <= len(t) <= 50:
                    tags.add(t)
        
        return list(tags)[:25]

    def _extract_best_datetime(self, soup: BeautifulSoup, html_text: str) -> Optional[str]:
        """Извлечь лучшую дату публикации"""
        # Ищем time теги с datetime
        for time_elem in soup.find_all('time'):
            dt = time_elem.get('datetime')
            if dt:
                return dt
        
        # Пробуем паттерны в тексте
        patterns = [
            r'(\d{2}:\d{2}),?\s*(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})',
            r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}',
        ]
        
        for pat in patterns:
            m = re.search(pat, html_text)
            if m:
                return m.group()
        
        return None

    def _extract_financial_entities(self, text: str) -> List[str]:
        """Извлечь финансовые сущности из текста"""
        if not text:
            return []
        
        entities = set()
        patterns = [
            r'(?:ПАО|АО|ООО|ОАО|ЗАО)\s+"[^"]{3,40}"',
            r'(?:Сбербанк|Газпром|Роснефт|ВТБ|Лукойл|Новатэк|НЛМК|Северсталь|Ростех|Росатом|МТС)',
            r'(?:ЦБ РФ|Банк России|Минфин|Минэкономразвития|ФНС|Роскомнадзор)',
            r'[А-Я][А-Яёа-яё]{2,15}\s+(?:банк|группа|холдинг|компания|корпорация)',
            r'\d+(?:,\d+)?\s*(?:млрд|млн|тыс\.?)*\s*(?:рублей|долларов|евро)',
            r'(?:доллар США|евро|рубль|юань)',
            r'(?:ключевая ставка|инфляция|ВВП|курс валют|биржа)'
        ]
        
        for pat in patterns:
            for m in re.findall(pat, text, re.IGNORECASE):
                s = m.strip()
                if len(s) > 2:
                    entities.add(s)
        
        return list(entities)[:20]
