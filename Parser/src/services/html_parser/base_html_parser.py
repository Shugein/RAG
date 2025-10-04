# src/services/html_parser/base_html_parser.py
"""
Базовый класс для HTML парсеров
"""

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.core.models import Source, News, ParserState
from src.services.storage.news_repository import NewsRepository
from src.services.enricher.enrichment_service import EnrichmentService

logger = logging.getLogger(__name__)


class BaseHTMLParser(ABC):
    """
    Базовый класс для всех HTML парсеров
    Обеспечивает единообразный интерфейс и общую логику
    """

    def __init__(
        self,
        source: Source,
        db_session: AsyncSession,
        enricher: Optional[EnrichmentService] = None
    ):
        self.source = source
        self.session = db_session
        self.news_repo = NewsRepository(db_session)
        self.enricher = enricher
        
        # Статистика
        self.stats = {
            "articles_processed": 0,
            "articles_saved": 0,
            "articles_updated": 0,
            "errors": 0,
            "duplicates_skipped": 0
        }

    @abstractmethod
    async def get_article_urls(self, max_articles: int = 100) -> List[str]:
        """
        Получить список URL статей для парсинга
        
        Args:
            max_articles: Максимальное количество статей
            
        Returns:
            List[str]: Список URL статей
        """
        pass

    @abstractmethod
    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Парсить отдельную статью
        
        Args:
            url: URL статьи
            
        Returns:
            Dict с данными статьи или None при ошибке
        """
        pass

    async def collect_news(self, max_articles: int = 100) -> Dict[str, Any]:
        """
        Основной метод сбора новостей
        
        Args:
            max_articles: Максимальное количество статей
            
        Returns:
            Dict со статистикой
        """
        logger.info(f"Starting news collection for {self.source.code}")
        
        try:
            # Получаем или создаем состояние парсера
            parser_state = await self._get_or_create_parser_state()
            
            # Получаем URL статей
            article_urls = await self.get_article_urls(max_articles)
            logger.info(f"Found {len(article_urls)} article URLs")
            
            if not article_urls:
                logger.warning(f"No article URLs found for {self.source.code}")
                return self.stats
            
            # Обрабатываем каждую статью
            for url in article_urls:
                try:
                    await self._process_article(url)
                    self.stats["articles_processed"] += 1
                    
                    # Небольшая задержка между запросами
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error processing article {url}: {e}")
                    self.stats["errors"] += 1
            
            # Обновляем состояние парсера
            await self._update_parser_state(parser_state)
            
            logger.info(f"Collection completed for {self.source.code}: {self.stats}")
            return self.stats
            
        except Exception as e:
            logger.error(f"Error in collect_news for {self.source.code}: {e}")
            self.stats["errors"] += 1
            return self.stats

    async def _process_article(self, url: str):
        """Обработать отдельную статью"""
        try:
            # Парсим статью
            article_data = await self.parse_article(url)
            if not article_data:
                logger.warning(f"Failed to parse article: {url}")
                return
            
            # Создаем хеш контента для дедупликации
            content_hash = self._create_content_hash(
                article_data.get('title', ''),
                article_data.get('content', '')
            )
            
            # Проверяем на дубликаты
            existing_news = await self.news_repo.get_by_hash(content_hash)
            if existing_news:
                logger.debug(f"Duplicate article found, skipping: {url}")
                self.stats["duplicates_skipped"] += 1
                return
            
            # Создаем или обновляем новость
            news = await self._create_or_update_news(article_data, content_hash)
            if news:
                self.stats["articles_saved"] += 1
                
                # Обогащаем новость если включен enricher
                if self.enricher:
                    try:
                        await self.enricher.enrich_news(news)
                    except Exception as e:
                        logger.error(f"Error enriching news {news.id}: {e}")
            
        except Exception as e:
            logger.error(f"Error processing article {url}: {e}")
            raise

    async def _create_or_update_news(
        self, 
        article_data: Dict[str, Any], 
        content_hash: str
    ) -> Optional[News]:
        """Создать или обновить новость в БД"""
        try:
            # Проверяем существование по external_id (URL)
            existing_news = await self.news_repo.get_by_external_id(
                self.source.id, 
                article_data['url']
            )
            
            # Парсим дату публикации
            published_at = self._parse_publish_date(
                article_data.get('date', article_data.get('publish_date'))
            )
            
            if existing_news:
                # Обновляем существующую новость
                existing_news.title = article_data.get('title', existing_news.title)
                existing_news.text_plain = article_data.get('content', existing_news.text_plain)
                existing_news.hash_content = content_hash
                existing_news.is_updated = True
                existing_news.detected_at = datetime.now(timezone.utc)
                
                await self.session.commit()
                self.stats["articles_updated"] += 1
                return existing_news
            else:
                # Создаем новую новость
                news = News(
                    id=uuid4(),
                    source_id=self.source.id,
                    external_id=article_data['url'],
                    url=article_data['url'],
                    title=article_data.get('title', ''),
                    summary=article_data.get('summary', ''),
                    text_plain=article_data.get('content', ''),
                    lang='ru',
                    published_at=published_at,
                    detected_at=datetime.now(timezone.utc),
                    hash_content=content_hash,
                    meta=article_data.get('metadata', {})
                )
                
                self.session.add(news)
                await self.session.commit()
                return news
                
        except Exception as e:
            logger.error(f"Error creating/updating news: {e}")
            await self.session.rollback()
            return None

    def _create_content_hash(self, title: str, content: str) -> str:
        """Создать хеш контента для дедупликации"""
        combined = f"{title}|{content}"
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def _parse_publish_date(self, date_str: Optional[str]) -> datetime:
        """Парсить дату публикации"""
        if not date_str:
            return datetime.now(timezone.utc)
        
        try:
            # Пробуем разные форматы дат
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d',
                '%d.%m.%Y %H:%M',
                '%d.%m.%Y',
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%SZ'
            ]
            
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    if parsed_date.tzinfo is None:
                        parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                    return parsed_date
                except ValueError:
                    continue
            
            # Если ничего не подошло, возвращаем текущую дату
            logger.warning(f"Could not parse date: {date_str}")
            return datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return datetime.now(timezone.utc)

    async def _get_or_create_parser_state(self) -> ParserState:
        """Получить или создать состояние парсера"""
        result = await self.session.execute(
            select(ParserState).where(ParserState.source_id == self.source.id)
        )
        parser_state = result.scalar_one_or_none()
        
        if not parser_state:
            parser_state = ParserState(
                id=uuid4(),
                source_id=self.source.id,
                last_parsed_at=datetime.now(timezone.utc)
            )
            self.session.add(parser_state)
            await self.session.commit()
        
        return parser_state

    async def _update_parser_state(self, parser_state: ParserState):
        """Обновить состояние парсера"""
        parser_state.last_parsed_at = datetime.now(timezone.utc)
        parser_state.error_count = self.stats["errors"]
        await self.session.commit()
