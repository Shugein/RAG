# src/services/html_parser/html_parser_service.py
"""
Сервис для управления HTML парсерами
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.core.models import Source, SourceKind
from src.services.enricher.enrichment_service import EnrichmentService
from src.services.html_parser.forbes_parser import ForbesParser
from src.services.html_parser.interfax_parser import InterfaxParser
from src.services.html_parser.edisclosure_parser import EDisclosureParser
from src.services.html_parser.moex_parser import MOEXParser
from src.services.html_parser.edisclosure_messages_parser import EDisclosureMessagesParser

logger = logging.getLogger(__name__)


class HTMLParserService:
    """
    Сервис для управления HTML парсерами
    Координирует работу различных парсеров новостных сайтов
    """

    def __init__(self, db_session: AsyncSession, use_local_ai: bool = False):
        self.session = db_session
        self.enricher = EnrichmentService(db_session, use_local_ai=use_local_ai)
        
        # Регистр парсеров
        self.parser_registry = {
            'forbes': ForbesParser,
            'interfax': InterfaxParser,
            'edisclosure': EDisclosureParser,
            'moex': MOEXParser,
            'edisclosure_messages': EDisclosureMessagesParser,
        }
        
        # Статистика
        self.stats = {
            "sources_processed": 0,
            "total_articles_processed": 0,
            "total_articles_saved": 0,
            "total_errors": 0,
            "parser_stats": {}
        }

    async def start_parsing(self, max_articles_per_source: int = 50) -> Dict[str, Any]:
        """
        Запустить парсинг всех активных HTML источников
        
        Args:
            max_articles_per_source: Максимальное количество статей на источник
            
        Returns:
            Dict со статистикой
        """
        logger.info("Starting HTML parsing service")
        
        try:
            # Получаем все активные HTML источники
            result = await self.session.execute(
                select(Source).where(
                    Source.kind == SourceKind.HTML,
                    Source.enabled == True
                )
            )
            sources = result.scalars().all()
            
            if not sources:
                logger.warning("No active HTML sources found")
                return self.stats
            
            logger.info(f"Found {len(sources)} active HTML sources")
            
            # Обрабатываем каждый источник
            tasks = []
            for source in sources:
                task = asyncio.create_task(
                    self._process_source(source, max_articles_per_source)
                )
                tasks.append(task)
            
            # Ждем завершения всех задач
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info(f"HTML parsing completed: {self.stats}")
            return self.stats
            
        except Exception as e:
            logger.error(f"Error in HTML parsing service: {e}")
            self.stats["total_errors"] += 1
            return self.stats

    async def _process_source(self, source: Source, max_articles: int):
        """Обработать отдельный источник"""
        try:
            logger.info(f"Processing source: {source.code} ({source.name})")
            
            # Определяем тип парсера по коду источника
            parser_class = self._get_parser_class(source.code)
            if not parser_class:
                logger.warning(f"No parser found for source: {source.code}")
                return
            
            # Создаем парсер
            parser = parser_class(
                source=source,
                db_session=self.session,
                enricher=self.enricher
            )
            
            # Запускаем парсинг
            parser_stats = await parser.collect_news(max_articles)
            
            # Обновляем общую статистику
            self.stats["sources_processed"] += 1
            self.stats["total_articles_processed"] += parser_stats.get("articles_processed", 0)
            self.stats["total_articles_saved"] += parser_stats.get("articles_saved", 0)
            self.stats["total_errors"] += parser_stats.get("errors", 0)
            self.stats["parser_stats"][source.code] = parser_stats
            
            logger.info(f"Completed processing {source.code}: {parser_stats}")
            
        except Exception as e:
            logger.error(f"Error processing source {source.code}: {e}")
            self.stats["total_errors"] += 1

    def _get_parser_class(self, source_code: str):
        """Получить класс парсера по коду источника"""
        return self.parser_registry.get(source_code)

    async def parse_specific_source(self, source_code: str, max_articles: int = 50) -> Dict[str, Any]:
        """
        Парсить конкретный источник
        
        Args:
            source_code: Код источника
            max_articles: Максимальное количество статей
            
        Returns:
            Dict со статистикой
        """
        try:
            # Получаем источник
            result = await self.session.execute(
                select(Source).where(
                    Source.code == source_code,
                    Source.kind == SourceKind.HTML,
                    Source.enabled == True
                )
            )
            source = result.scalar_one_or_none()
            
            if not source:
                logger.error(f"Source not found or disabled: {source_code}")
                return {"error": f"Source not found: {source_code}"}
            
            # Определяем парсер
            parser_class = self._get_parser_class(source_code)
            if not parser_class:
                logger.error(f"No parser found for source: {source_code}")
                return {"error": f"No parser found: {source_code}"}
            
            # Создаем и запускаем парсер
            parser = parser_class(
                source=source,
                db_session=self.session,
                enricher=self.enricher
            )
            
            stats = await parser.collect_news(max_articles)
            logger.info(f"Parsed {source_code}: {stats}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error parsing source {source_code}: {e}")
            return {"error": str(e)}

    def register_parser(self, source_code: str, parser_class):
        """
        Зарегистрировать новый парсер
        
        Args:
            source_code: Код источника
            parser_class: Класс парсера
        """
        self.parser_registry[source_code] = parser_class
        logger.info(f"Registered parser for source: {source_code}")

    def get_available_parsers(self) -> List[str]:
        """Получить список доступных парсеров"""
        return list(self.parser_registry.keys())

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику работы сервиса"""
        return self.stats.copy()
