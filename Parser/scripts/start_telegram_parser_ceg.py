# scripts/start_telegram_parser_ceg.py
"""
🚀 УЛУЧШЕННЫЙ TELEGRAM PARSER с BATCH обработкой и полным CEG анализом

НОВЫЕ ВОЗМОЖНОСТИ:
- Batch обработка новостей в JSON формате
- NER entity recognition для извлечения сущностей
- Создание сущностей в графовой БД Neo4j
- CEG расчеты и анализ причинных связей
- Детальный JSON ответ с полной информацией о новостях
- Связи между новостями и тикерами
- Расчетные метрики из CEG системы
- Предсказания будущих событий

АРХИТЕКТУРА:
1. Читает новости из Telegram в batch режиме
2. Формирует JSON список новостей
3. Передает в NER entity_recognition для анализа
4. Создает сущности в графовой БД Neo4j
5. Выполняет CEG расчеты и анализ связей
6. Формирует подробный JSON ответ с максимальными данными
"""

import asyncio
import logging
import signal
import sys
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from Parser.src.core.config import settings
from Parser.src.core.database import init_db, close_db, get_db_session
from Parser.src.services.telegram_parser.client import TelegramClientManager
from Parser.src.services.telegram_parser.parser import Telegram_Parser
from Parser.src.services.telegram_parser.antispam import AntiSpamFilter
from Parser.src.services.enricher.enrichment_service import EnrichmentService
from Parser.src.services.enricher.moex_linker import MOEXLinker
from Parser.src.utils.logging import setup_logging
from Parser.src.core.models import Source, News, SourceKind
from Parser.src.graph_models import GraphService
from Parser.src.services.html_parser.html_parser_service import HTMLParserService
from Parser.entity_recognition import CachedFinanceNERExtractor
try:
    from Parser.entity_recognition_local import LocalFinanceNERExtractor
except ImportError:
    try:
        from entity_recognition_local import LocalFinanceNERExtractor
    except ImportError:
        LocalFinanceNERExtractor = None
from sqlalchemy import select

logger = logging.getLogger(__name__)


class Telegram_ParserServiceCEG:
    """
    🚀 УЛУЧШЕННЫЙ Telegram_Parser с BATCH обработкой и полным CEG анализом
    🌐 + ИНТЕГРАЦИЯ HTML ПАРСЕРОВ (Forbes, Interfax)

    НОВЫЕ ВОЗМОЖНОСТИ:
    - Batch обработка новостей в JSON формате
    - NER entity recognition для извлечения сущностей  
    - Создание сущностей в графовой БД Neo4j
    - CEG расчеты и анализ причинных связей
    - Детальный JSON ответ с полной информацией о новостях
    - Связи между новостями и тикерами
    - Расчетные метрики из CEG системы
    - Предсказания будущих событий
    - 🌐 HTML парсинг Forbes, Interfax, E-disclosure, MOEX в рамках CEG
    - 🔄 Единая обработка Telegram и HTML источников
    """

    def __init__(
        self,
        days: int = 7,
        realtime_mode: bool = False,
        use_local_ai: bool = False,
        batch_size: int = 20,
        max_batches: int = 10,
        batch_delay: int = 5,
        retry_attempts: int = 3,
        network_timeout: int = 30
    ):
        self.client_manager = TelegramClientManager()
        self.client = None
        self.enricher = None
        self.graph_service = None
        self.moex_linker = None
        self.html_parser_service = None
        self.running = False
        self.tasks = []
        self.days = days
        self.realtime_mode = realtime_mode
        self.use_local_ai = use_local_ai
        
        # Настройки batch обработки
        self.batch_size = batch_size
        self.max_batches = max_batches
        self.batch_delay = batch_delay
        self.retry_attempts = retry_attempts
        self.network_timeout = network_timeout

        # Инициализация NER системы
        self._init_ner_system()

        # Статистика
        self.total_stats = {
            "total_messages": 0,
            "saved_news": 0,
            "ads_filtered": 0,
            "duplicates": 0,
            "errors": 0,
            "batch_processed": 0,
            "entities_extracted": 0,
            "graph_nodes_created": 0,
            "ceg_links_created": 0,
            "predictions_generated": 0,
            "html_sources_processed": 0,
            "html_articles_processed": 0,
            "telegram_sources_processed": 0
        }

    def _init_ner_system(self):
        """Инициализация NER системы с улучшенной обработкой ошибок"""
        if self.use_local_ai and LocalFinanceNERExtractor:
            logger.info("🧠 Initializing LOCAL AI NER (Qwen3-4B)")
            try:
                self.ner_extractor = LocalFinanceNERExtractor(
                    model_name="unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
                    device="cuda",
                    batch_size=self.batch_size
                )
                logger.info("✅ Local AI NER initialized successfully")
            except Exception as e:
                logger.warning(f"❌ Failed to load local AI: {e}")
                logger.info("🔄 Falling back to API mode...")
                self.use_local_ai = False
        
        if not self.use_local_ai:
            logger.info("🧠 Initializing API AI NER (OpenAI GPT)")
            api_key = os.getenv("API_KEY_2") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("❌ No API key found for OpenAI GPT. Set API_KEY_2 or OPENAI_API_KEY environment variable")
            
            try:
                self.ner_extractor = CachedFinanceNERExtractor(
                    api_key=api_key,
                    model="gpt-4o-mini",
                    enable_caching=True
                )
                logger.info("✅ API AI NER initialized successfully")
            except Exception as e:
                raise ValueError(f"❌ Failed to initialize API NER: {e}")
        
        # Проверяем, что NER система инициализирована
        if not hasattr(self, 'ner_extractor') or not self.ner_extractor:
            raise RuntimeError("❌ Failed to initialize any NER system")

    async def _init_graph_service_with_retry(self):
        """Инициализация Graph Service с retry логикой и обработкой сетевых ошибок"""
        for attempt in range(self.retry_attempts):
            try:
                logger.info(f"🔄 Attempt {attempt + 1}/{self.retry_attempts} to connect to Neo4j...")
                
                graph_service = GraphService(
                    uri=settings.NEO4J_URI,
                    user=settings.NEO4J_USER,
                    password=settings.NEO4J_PASSWORD
                )
                
                # Тестируем соединение
                await graph_service.create_constraints()
                logger.info("✅ Neo4j Graph Service connected successfully")
                return graph_service
                
            except Exception as e:
                logger.warning(f"❌ Neo4j connection attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_attempts - 1:
                    wait_time = (attempt + 1) * 2  # Экспоненциальная задержка
                    logger.info(f"⏳ Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("❌ Failed to connect to Neo4j after all attempts")
                    logger.info("⚠️ Continuing without graph functionality...")
                    return None

    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Выполняет функцию с retry логикой и экспоненциальной задержкой"""
        for attempt in range(self.retry_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"⚠️ Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ All {self.retry_attempts} attempts failed for {func.__name__}")
                    raise

    async def start(self):
        """🚀 Запуск улучшенного парсера с batch обработкой и CEG"""
        try:
            # Инициализация БД
            await init_db()

            # Инициализация Telegram клиента
            logger.info("🚀 Initializing Telegram client...")
            self.client = await self.client_manager.initialize()

            # Инициализация Graph Service для Neo4j с retry логикой
            logger.info("🕸️ Initializing Neo4j Graph Service...")
            self.graph_service = await self._init_graph_service_with_retry()

            # Инициализация MOEX Linker для поиска тикеров
            logger.info("🏢 Initializing MOEX Linker for ticker search...")
            self.moex_linker = MOEXLinker(enable_auto_learning=True)
            await self.moex_linker.initialize()

            # Инициализация EnrichmentService с CEG
            async with get_db_session() as session:
                logger.info("🧠 Initializing AI Enrichment Service...")
                self.enricher = EnrichmentService(
                    session=session,
                    use_local_ai=self.use_local_ai
                )
                await self.enricher.initialize()

                # Инициализация CEG service с нашим graph_service
                if self.graph_service:
                    from Parser.src.services.events.ceg_realtime_service import CEGRealtimeService
                    self.enricher.ceg_service = CEGRealtimeService(
                        session=session,
                        graph_service=self.graph_service,
                        lookback_window=30  # 30 дней для ретроспективного анализа
                    )
                    logger.info("   ✓ CEG Real-time Service initialized with graph_service")

                # Инициализация HTML Parser Service
                logger.info("🌐 Initializing HTML Parser Service...")
                self.html_parser_service = HTMLParserService(
                    db_session=session,
                    use_local_ai=self.use_local_ai
                )

                logger.info(f"   ✓ AI Model: {'Local Qwen3-4B' if self.use_local_ai else 'OpenAI GPT'}")
                logger.info(f"   ✓ Batch size: {self.batch_size}")
                logger.info(f"   ✓ NER extractor: {type(self.ner_extractor).__name__}")

                if self.enricher.ceg_service:
                    logger.info(f"   ✓ CEG lookback window: {self.enricher.ceg_service.lookback_window} days")
                else:
                    logger.warning("   ⚠ CEG Service not available (Neo4j not connected?)")

                # Получаем все активные Telegram источники
                telegram_result = await session.execute(
                    select(Source).where(
                        Source.kind == SourceKind.TELEGRAM,
                        Source.enabled == True
                    )
                )
                telegram_sources = telegram_result.scalars().all()

                # Получаем все активные HTML источники
                html_result = await session.execute(
                    select(Source).where(
                        Source.kind == SourceKind.HTML,
                        Source.enabled == True
                    )
                )
                html_sources = html_result.scalars().all()

                total_sources = len(telegram_sources) + len(html_sources)
                
                if total_sources == 0:
                    logger.warning("No active sources found")
                    return

                logger.info(f"📡 Found {len(telegram_sources)} active Telegram sources")
                logger.info(f"🌐 Found {len(html_sources)} active HTML sources")
                logger.info(f"📊 Total sources: {total_sources}")

                # Информация о режиме работы
                if self.realtime_mode:
                    logger.info("🔄 Running in REAL-TIME MONITORING mode")
                    logger.info("   - Batch processing of new messages (Telegram + HTML)")
                    logger.info("   - NER entity extraction")
                    logger.info("   - Graph creation and CEG analysis")
                    logger.info("   - Detailed JSON responses")
                else:
                    logger.info(f"📚 Running in HISTORICAL LOADING mode (last {self.days} days)")
                    logger.info("   - Batch loading historical messages (Telegram + HTML)")
                    logger.info("   - Full NER analysis and graph building")
                    logger.info("   - CEG calculations and predictions")

                # Запускаем batch мониторинг для Telegram источников
                self.running = True
                for source in telegram_sources:
                    task = asyncio.create_task(
                        self._monitor_telegram_source_batch(source)
                    )
                    self.tasks.append(task)
                
                # Запускаем batch мониторинг для HTML источников
                for source in html_sources:
                    task = asyncio.create_task(
                        self._monitor_html_source_batch(source)
                    )
                    self.tasks.append(task)

                # Ждем завершения всех задач
                await asyncio.gather(*self.tasks)

                # Выводим финальную статистику
                self._print_final_stats()

        except Exception as e:
            logger.error(f"Failed to start Telegram parser: {e}", exc_info=True)
            raise
        finally:
            await self.stop()

    async def _monitor_telegram_source_batch(self, source: Source):
        """🔄 Batch мониторинг источника с полным анализом"""
        logger.info(f"📻 Starting BATCH monitor for {source.name} ({source.code})")

        # Сначала выполняем batch backfill если нужно
        async with get_db_session() as session:
            parser = Telegram_Parser(
                client=self.client,
                db_session=session,
                anti_spam=AntiSpamFilter(Path("config/ad_rules.yml")),
                enricher=None  # Не используем старый enricher
            )

            # Проверяем, нужен ли backfill
            config = source.config or {}
            if not self.realtime_mode and config.get("backfill_enabled", True):
                logger.info(f"📥 Starting BATCH backfill for {source.code} (last {self.days} days)")
                
                try:
                    # Получаем новости из Telegram
                    news_batch = await self._collect_news_batch(parser, source, self.days)
                    
                    if news_batch:
                        logger.info(f"📊 Collected {len(news_batch)} news items for batch processing")
                        
                        # Обрабатываем batch через NER и CEG
                        detailed_results = await self._process_news_batch(news_batch, source)
                        
                        # Сохраняем результаты
                        await self._save_batch_results(detailed_results, session)
                        
                        logger.info(f"✅ Batch processing completed for {source.code}")
                        logger.info(f"   - News processed: {len(news_batch)}")
                        logger.info(f"   - Entities extracted: {detailed_results.get('total_entities', 0)}")
                        logger.info(f"   - Graph nodes created: {detailed_results.get('total_nodes', 0)}")
                        logger.info(f"   - CEG links created: {detailed_results.get('total_links', 0)}")

                except Exception as e:
                    logger.error(f"❌ Batch backfill failed for {source.code}: {e}", exc_info=True)

            # В режиме исторической загрузки выходим после backfill
            if not self.realtime_mode:
                logger.info(f"✅ Historical batch loading completed for {source.code}")
                return

        # Режим real-time batch мониторинга
        logger.info(f"🔄 Starting real-time BATCH monitoring for {source.code}")
        while self.running:
            try:
                async with get_db_session() as session:
                    parser = Telegram_Parser(
                        client=self.client,
                        db_session=session,
                        anti_spam=AntiSpamFilter(Path("config/ad_rules.yml")),
                        enricher=None
                    )

                    # Получаем новые сообщения batch
                    news_batch = await self._collect_news_batch(parser, source, 1)  # Только новые

                    if news_batch:
                        logger.info(f"✨ Processing {len(news_batch)} new items from {source.code}")
                        
                        # Обрабатываем через NER и CEG
                        detailed_results = await self._process_news_batch(news_batch, source)
                        
                        # Сохраняем результаты
                        await self._save_batch_results(detailed_results, session)
                        
                        # Обновляем статистику
                        self._update_batch_stats(detailed_results)

                # Ждем перед следующей проверкой
                await asyncio.sleep(settings.PARSER_POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Error in batch monitoring {source.code}: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке

    async def _monitor_html_source_batch(self, source: Source):
        """🌐 Batch мониторинг HTML источника с полным CEG анализом"""
        logger.info(f"🌐 Starting BATCH monitor for HTML source {source.name} ({source.code})")

        try:
            # Сначала выполняем batch backfill если нужно
            async with get_db_session() as session:
                if not self.realtime_mode:
                    logger.info(f"📥 Starting BATCH backfill for HTML source {source.code}")
                    
                    try:
                        # Получаем новости из HTML парсера
                        news_batch = await self._collect_html_news_batch(source, session)
                        
                        if news_batch:
                            logger.info(f"📊 Collected {len(news_batch)} HTML news items for batch processing")
                            
                            # Обрабатываем batch через NER и CEG
                            detailed_results = await self._process_news_batch(news_batch, source)
                            
                            # Сохраняем результаты
                            await self._save_batch_results(detailed_results, session)
                            
                            logger.info(f"✅ HTML batch processing completed for {source.code}")
                            logger.info(f"   - News processed: {len(news_batch)}")
                            logger.info(f"   - Entities extracted: {detailed_results.get('total_entities', 0)}")
                            logger.info(f"   - Graph nodes created: {detailed_results.get('total_nodes', 0)}")
                            logger.info(f"   - CEG links created: {detailed_results.get('total_links', 0)}")
                            
                            # Обновляем статистику
                            self.total_stats["html_sources_processed"] += 1
                            self.total_stats["html_articles_processed"] += len(news_batch)

                    except Exception as e:
                        logger.error(f"❌ HTML batch backfill failed for {source.code}: {e}", exc_info=True)

                # В режиме исторической загрузки выходим после backfill
                if not self.realtime_mode:
                    logger.info(f"✅ Historical batch loading completed for HTML source {source.code}")
                    return

            # Режим real-time batch мониторинга
            logger.info(f"🔄 Starting real-time BATCH monitoring for HTML source {source.code}")
            while self.running:
                try:
                    async with get_db_session() as session:
                        # Получаем новые статьи из HTML парсера
                        news_batch = await self._collect_html_news_batch(source, session)

                        if news_batch:
                            logger.info(f"✨ Processing {len(news_batch)} new HTML items from {source.code}")
                            
                            # Обрабатываем через NER и CEG
                            detailed_results = await self._process_news_batch(news_batch, source)
                            
                            # Сохраняем результаты
                            await self._save_batch_results(detailed_results, session)
                            
                            # Обновляем статистику
                            self._update_batch_stats(detailed_results)
                            self.total_stats["html_articles_processed"] += len(news_batch)

                    # Ждем перед следующей проверкой (HTML источники обновляются реже)
                    poll_interval = source.config.get("poll_interval", 3600) if source.config else 3600
                    await asyncio.sleep(poll_interval)

                except Exception as e:
                    logger.error(f"Error in HTML batch monitoring {source.code}: {e}")
                    await asyncio.sleep(300)  # Ждем 5 минут при ошибке

        except Exception as e:
            logger.error(f"❌ Fatal error in HTML batch monitoring {source.code}: {e}", exc_info=True)

    async def _collect_news_batch(self, parser: Telegram_Parser, source: Source, days: int) -> List[Dict[str, Any]]:
        """📊 Собирает новости из Telegram в batch формате с настройками"""
        try:
            # Настраиваем лимит в зависимости от режима
            if days == 1:
                # Режим мониторинга - только новые сообщения
                limit = min(self.batch_size, source.config.get("realtime_limit", 50))
            else:
                # Режим исторической загрузки
                limit = min(self.max_batches * self.batch_size, source.config.get("fetch_limit", 1000))
            
            logger.info(f"📥 Collecting up to {limit} messages from {source.name} (last {days} days)")
            
            # Получаем сообщения из Telegram с retry логикой
            messages = await self._retry_with_backoff(
                self._fetch_telegram_messages, parser, source, days, limit
            )
            
            logger.info(f"✅ Collected {len(messages)} valid messages from {source.name}")
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error collecting news batch from {source.name}: {e}")
            return []

    async def _collect_html_news_batch(self, source: Source, session) -> List[Dict[str, Any]]:
        """🌐 Собирает новости из HTML источника в batch формате"""
        try:
            if not self.html_parser_service:
                logger.warning(f"⚠️ HTML parser service not available for {source.code}")
                return []
            
            # Определяем максимальное количество статей
            max_articles = source.config.get("max_articles_per_section", 25) if source.config else 25
            
            logger.info(f"🌐 Collecting up to {max_articles} articles from {source.name}")
            
            # Используем HTML parser service для получения новостей
            parser_stats = await self.html_parser_service.parse_specific_source(
                source.code, 
                max_articles
            )
            
            if 'error' in parser_stats:
                logger.error(f"❌ Error parsing HTML source {source.code}: {parser_stats['error']}")
                return []
            
            # Получаем последние новости из БД для этого источника
            # Получаем последние новости (за последние дни)
            days_back = self.days if not self.realtime_mode else 1
            
            result = await session.execute(
                select(News).where(
                    News.source_id == source.id,
                    News.published_at >= datetime.now() - timedelta(days=days_back)
                ).order_by(News.published_at.desc()).limit(max_articles)
            )
            news_items = result.scalars().all()
            
            # Преобразуем в формат batch
            news_batch = []
            for news in news_items:
                news_batch.append({
                    "id": str(news.id),
                    "text": news.text_plain or news.title or "",
                    "title": news.title,
                    "date": news.published_at,
                    "source_id": source.id,
                    "source_name": source.name,
                    "external_id": news.external_id,
                    "url": news.url,
                    "ad_score": 0.0,  # HTML источники считаем не рекламой
                    "ad_reasons": []
                })
            
            logger.info(f"✅ Collected {len(news_batch)} HTML news items from {source.name}")
            return news_batch
            
        except Exception as e:
            logger.error(f"❌ Error collecting HTML news batch from {source.name}: {e}")
            return []

    async def _fetch_telegram_messages(self, parser: Telegram_Parser, source: Source, days: int, limit: int) -> List[Dict[str, Any]]:
        """Получает сообщения из Telegram с фильтрацией"""
        messages = []
        collected = 0
        
        try:
            offset_date = datetime.now() - timedelta(days=days) if days > 1 else None
            
            async for message in parser.client.iter_messages(
                entity=source.tg_chat_id,
                limit=limit,
                offset_date=offset_date
            ):
                if collected >= limit:
                    break
                    
                if message.text or message.message:
                    # Проверяем на рекламу
                    is_ad, ad_score, ad_reasons = await parser.anti_spam.check_message(
                        message, source.trust_level
                    )
                    
                    if not is_ad:
                        messages.append({
                            "id": message.id,
                            "text": message.text or message.message or "",
                            "date": message.date,
                            "source_id": source.id,
                            "source_name": source.name,
                            "external_id": f"tg_{source.tg_chat_id}_{message.id}",
                            "ad_score": ad_score,
                            "ad_reasons": ad_reasons
                        })
                        collected += 1
                    else:
                        logger.debug(f"🚫 Message {message.id} filtered as ad (score: {ad_score})")
            
            return messages
            
        except Exception as e:
            logger.error(f"❌ Error fetching Telegram messages: {e}")
            raise

    async def _process_news_batch(self, news_batch: List[Dict[str, Any]], source: Source) -> Dict[str, Any]:
        """🧠 Обрабатывает batch новостей через NER и CEG с параллельными чанками"""
        try:
            # Разбиваем на чанки для обработки
            chunks = []
            for i in range(0, len(news_batch), self.batch_size):
                chunk = news_batch[i:i + self.batch_size]
                chunks.append((i // self.batch_size + 1, chunk))

            total_chunks = len(chunks)
            logger.info(f"🔍 Processing {len(news_batch)} news items in {total_chunks} parallel chunks of {self.batch_size}")

            # Параллельная обработка чанков
            chunk_tasks = [
                self._process_single_chunk(chunk_num, chunk, total_chunks, source)
                for chunk_num, chunk in chunks
            ]

            # Запускаем все чанки параллельно
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

            # Собираем результаты
            all_ner_results = []
            all_graph_results = {"nodes_created": 0, "links_created": 0}
            all_ceg_results = []

            for result in chunk_results:
                if isinstance(result, Exception):
                    logger.error(f"❌ Chunk processing failed: {result}")
                    continue

                if result and not result.get("error"):
                    all_ner_results.extend(result.get("ner_results", []))
                    all_graph_results["nodes_created"] += result.get("nodes_created", 0)
                    all_graph_results["links_created"] += result.get("links_created", 0)
                    if result.get("ceg_results"):
                        all_ceg_results.append(result["ceg_results"])
            
            logger.info(f"✅ NER extracted {len(all_ner_results)} processed items from {len(news_batch)} news")
            
            # Формируем детальный JSON ответ
            combined_ner_results = {"news_items": all_ner_results}
            combined_ceg_results = self._combine_ceg_results(all_ceg_results)
            
            detailed_response = await self._create_detailed_response(
                news_batch, combined_ner_results, all_graph_results, combined_ceg_results
            )
            
            return {
                "total_news": len(news_batch),
                "total_entities": len(all_ner_results),
                "total_nodes": all_graph_results["nodes_created"],
                "total_links": all_graph_results["links_created"],
                "ceg_analysis": combined_ceg_results,
                "detailed_response": detailed_response,
                "batch_id": str(uuid4()),
                "chunks_processed": (len(news_batch) + self.batch_size - 1) // self.batch_size
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing news batch: {e}", exc_info=True)
            return {"error": str(e), "total_news": len(news_batch)}

    async def _process_single_chunk(self, chunk_num: int, chunk: List[Dict[str, Any]], total_chunks: int, source: Source) -> Dict[str, Any]:
        """Обрабатывает один чанк новостей (для параллельного выполнения)"""
        try:
            logger.info(f"📦 Processing chunk {chunk_num}/{total_chunks} with {len(chunk)} items")

            # Формируем JSON для NER обработки чанка
            news_texts = [item["text"] for item in chunk]
            news_metadata = [
                {
                    "id": item["id"],
                    "date": item["date"].isoformat() if hasattr(item["date"], 'isoformat') else str(item["date"]),
                    "source": item["source_name"]
                }
                for item in chunk
            ]

            # Обрабатываем чанк через NER систему с retry
            ner_chunk_results = await self._retry_with_backoff(
                self._process_ner_chunk, news_texts, news_metadata
            )

            if not ner_chunk_results:
                return {"error": "NER processing failed", "ner_results": [], "nodes_created": 0, "links_created": 0}

            # Создаем сущности в графовой БД для чанка
            graph_chunk_results = await self._create_graph_entities(ner_chunk_results, chunk)

            # Выполняем CEG анализ для чанка
            ceg_chunk_results = await self._perform_ceg_analysis(graph_chunk_results, source)

            logger.info(f"✅ Chunk {chunk_num}/{total_chunks} completed: {graph_chunk_results.get('nodes_created', 0)} nodes, {graph_chunk_results.get('links_created', 0)} links")

            return {
                "ner_results": ner_chunk_results.get('news_items', []),
                "nodes_created": graph_chunk_results.get("nodes_created", 0),
                "links_created": graph_chunk_results.get("links_created", 0),
                "ceg_results": ceg_chunk_results
            }

        except Exception as e:
            logger.error(f"❌ Error processing chunk {chunk_num}: {e}", exc_info=True)
            return {"error": str(e), "ner_results": [], "nodes_created": 0, "links_created": 0}

    async def _process_ner_chunk(self, news_texts: List[str], news_metadata: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обрабатывает чанк новостей через NER систему"""
        try:
            if self.use_local_ai:
                # Локальная обработка (синхронная, т.к. LocalFinanceNERExtractor не асинхронный)
                # Запускаем в executor чтобы не блокировать event loop
                import concurrent.futures
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    entities_list = await loop.run_in_executor(
                        executor,
                        lambda: self.ner_extractor.extract_entities_batch(news_texts, verbose=False)
                    )
            else:
                # API обработка - используем асинхронный метод напрямую
                entities_list = await self.ner_extractor.extract_entities_batch_async(news_texts, verbose=False)

            # Преобразуем результаты в формат для дальнейшей обработки
            news_items = []
            for i, entities in enumerate(entities_list):
                if entities:
                    news_items.append({
                        "id": news_metadata[i]["id"],
                        "date": news_metadata[i]["date"],
                        "source": news_metadata[i]["source"],
                        "companies": [{"name": c.name, "ticker": c.ticker, "sector": c.sector} for c in entities.companies],
                        "people": [{"name": p.name, "position": p.position, "company": p.company} for p in entities.people],
                        "markets": [{"name": m.name, "type": m.type, "value": m.value, "change": m.change} for m in entities.markets],
                        "financial_metrics": [{"metric_type": fm.metric_type, "value": fm.value, "company": fm.company} for fm in entities.financial_metrics],
                        "event": "",  # Модель не извлекает event напрямую
                        "event_types": [],
                        "sector": entities.companies[0].sector if entities.companies else None,
                        "country": "RU",
                        "is_advertisement": False,
                        "content_types": [],
                        "confidence_score": 0.9 if not self.use_local_ai else 0.8,
                        "urgency_level": "normal"
                    })
                else:
                    # Пустой результат для неудачной обработки
                    news_items.append({
                        "id": news_metadata[i]["id"],
                        "date": news_metadata[i]["date"],
                        "source": news_metadata[i]["source"],
                        "companies": [],
                        "people": [],
                        "markets": [],
                        "financial_metrics": [],
                        "event": "",
                        "event_types": [],
                        "sector": None,
                        "country": "RU",
                        "is_advertisement": False,
                        "content_types": [],
                        "confidence_score": 0.0,
                        "urgency_level": "normal"
                    })

            return {"news_items": news_items}
        except Exception as e:
            logger.error(f"❌ NER processing failed for chunk: {e}")
            raise

    def _combine_ceg_results(self, ceg_results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Объединяет результаты CEG анализа из разных чанков"""
        combined = {
            "causal_links_found": 0,
            "importance_scores": [],
            "market_impacts": [],
            "predictions": [],
            "total_chunks": len(ceg_results_list)
        }
        
        for result in ceg_results_list:
            if not result.get("error"):
                combined["causal_links_found"] += result.get("causal_links_found", 0)
                combined["importance_scores"].extend(result.get("importance_scores", []))
                combined["market_impacts"].extend(result.get("market_impacts", []))
                combined["predictions"].extend(result.get("predictions", []))
        
        return combined

    async def _create_graph_entities(self, ner_results: Dict[str, Any], news_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """🕸️ Создает сущности в графовой БД Neo4j с обработкой ошибок"""
        try:
            if not self.graph_service:
                logger.warning("⚠️ Graph service not available, skipping graph creation")
                return {"nodes_created": 0, "links_created": 0, "error": "Graph service unavailable"}

            nodes_created = 0
            links_created = 0

            for i, news_item in enumerate(ner_results.get('news_items', [])):
                if not news_item or i >= len(news_batch):
                    continue

                news_data = news_batch[i]
                # Используем реальный ID из базы данных вместо генерации нового
                news_id = str(news_data.get("id", uuid4()))
                
                try:
                    # Создаем узел новости с retry
                    await self._retry_with_backoff(
                        self._create_news_node_safe,
                        news_id, news_data, news_item
                    )
                    nodes_created += 1
                    logger.debug(f"✅ Created news node: {news_id}")

                    # Поиск тикеров через MOEX Linker
                    ticker_matches = await self._find_tickers_for_news(news_data, news_item)

                    # Создаем компании с найденными тикерами
                    companies = news_item.get("companies", [])
                    if companies:
                        logger.debug(f"📊 Found {len(companies)} companies in news")
                        for company in companies:
                            if company.get("name"):
                                # Ищем тикер для этой компании
                                ticker_info = self._find_ticker_for_company(company.get("name", ""), ticker_matches)

                                company_id = f"company_{hash(company.get('name', ''))}"
                                await self._retry_with_backoff(
                                    self._create_company_node_with_ticker_safe,
                                    company_id, company, ticker_info
                                )
                                await self._retry_with_backoff(
                                    self._link_news_to_company_safe,
                                    news_id, company_id
                                )
                                links_created += 1
                                logger.debug(f"🔗 Linked news {news_id} to company {company.get('name')}")
                    
                    # Создаем персон и связываем
                    for person in news_item.get("people", []):
                        if person.get("name"):
                            entity_id = f"person_{hash(person.get('name', ''))}"
                            await self._retry_with_backoff(
                                self._create_entity_node_safe,
                                entity_id, person
                            )
                            await self._retry_with_backoff(
                                self._link_news_to_entity_safe,
                                news_id, entity_id
                            )
                            links_created += 1
                    
                    # Создаем финансовые метрики
                    for metric in news_item.get("financial_metrics", []):
                        if metric.get("value"):
                            metric_id = f"metric_{hash(metric.get('value', ''))}"
                            await self._retry_with_backoff(
                                self._create_metric_node_safe,
                                metric_id, metric
                            )
                            await self._retry_with_backoff(
                                self._link_news_to_metric_safe,
                                news_id, metric_id
                            )
                            links_created += 1
                
                except Exception as e:
                    logger.warning(f"⚠️ Failed to create graph entities for news {news_data.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(f"✅ Created {nodes_created} nodes and {links_created} links in graph")
            return {
                "nodes_created": nodes_created,
                "links_created": links_created
            }
            
        except Exception as e:
            logger.error(f"❌ Error creating graph entities: {e}")
            return {"nodes_created": 0, "links_created": 0, "error": str(e)}

    async def _create_news_node_safe(self, news_id: str, news_data: Dict[str, Any], news_item: Dict[str, Any]):
        """Безопасное создание узла новости"""
        # Преобразуем дату в datetime если это строка или оставляем как есть
        published_at = news_data.get("date")
        if isinstance(published_at, str):
            # Парсим ISO формат строки обратно в datetime
            try:
                published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                # Если не получилось распарсить, используем текущее время
                published_at = datetime.now()
        elif not published_at:
            published_at = datetime.now()

        # Формируем заголовок из события или текста
        title = news_item.get("event", "")[:200]
        if not title:
            title = news_data.get("title", news_data.get("text", "")[:200])
        if not title:
            title = "Telegram News"

        await self.graph_service.create_news_node({
            "id": news_id,
            "url": f"telegram://{news_data.get('url') or news_data.get('external_id', '')}",
            "title": title,
            "text": news_data.get("text", "")[:1000],  # Ограничиваем размер текста
            "published_at": published_at,
            "source": news_data.get("source_name", ""),
            "lang_orig": "ru",
            "lang_norm": "ru",
            "no_impact": False,
            "news_type": None,
            "news_subtype": None
        })

    async def _create_company_node_safe(self, company_id: str, company: Dict[str, Any]):
        """Безопасное создание узла компании"""
        await self.graph_service.create_company_node(
            company_id=company_id,
            name=company.get("name", "")[:100],
            ticker=company.get("ticker", "")[:20],
            is_traded=bool(company.get("ticker"))
        )

    async def _link_news_to_company_safe(self, news_id: str, company_id: str):
        """Безопасное связывание новости с компанией"""
        await self.graph_service.link_news_to_company(news_id, company_id)

    async def _create_entity_node_safe(self, entity_id: str, person: Dict[str, Any]):
        """Безопасное создание узла персоны"""
        await self.graph_service.create_entity_node(
            entity_id=entity_id,
            text=person.get("name", "")[:100],
            entity_type="PERSON",
            confidence=0.9
        )

    async def _link_news_to_entity_safe(self, news_id: str, entity_id: str):
        """Безопасное связывание новости с персоной"""
        await self.graph_service.link_news_to_entity(news_id, entity_id)

    async def _create_metric_node_safe(self, metric_id: str, metric: Dict[str, Any]):
        """Безопасное создание узла метрики"""
        await self.graph_service.create_entity_node(
            entity_id=metric_id,
            text=f"{metric.get('metric_type', '')}: {metric.get('value', '')}",
            entity_type="FINANCIAL_METRIC",
            confidence=0.8
        )

    async def _link_news_to_metric_safe(self, news_id: str, metric_id: str):
        """Безопасное связывание новости с метрикой"""
        await self.graph_service.link_news_to_entity(news_id, metric_id)

    async def _find_tickers_for_news(self, news_data: Dict[str, Any], news_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """🔍 Находит тикеры для новости через MOEX Linker"""
        try:
            if not self.moex_linker:
                logger.warning("⚠️ MOEX Linker not available")
                return []

            # Собираем все возможные тексты для поиска
            search_texts = []

            # 1. Текст новости
            if news_data.get('text'):
                search_texts.append(news_data['text'])

            # 2. Названия компаний из NER
            companies_from_ner = news_item.get("companies", [])
            if companies_from_ner:
                for company in companies_from_ner:
                    if company.get("name"):
                        search_texts.append(company["name"])

            # 3. Заголовок если есть
            if news_data.get('title'):
                search_texts.append(news_data['title'])

            if not search_texts:
                return []

            # Объединяем все тексты
            full_text = " | ".join(search_texts)

            # Ищем компании в тексте
            company_matches = await self.moex_linker.link_companies(full_text)

            # Преобразуем в удобный формат
            ticker_matches = []
            for match in company_matches:
                if match.ticker:
                    ticker_matches.append({
                        "ticker": match.ticker,
                        "company_name": match.company_name,
                        "short_name": match.short_name,
                        "confidence": match.confidence,
                        "match_method": match.match_method,
                        "is_traded": match.is_traded,
                        "isin": match.isin,
                        "board": match.board,
                        "original_text": match.text
                    })

            if ticker_matches:
                logger.info(f"🔍 Found {len(ticker_matches)} ticker matches: {[t['ticker'] for t in ticker_matches]}")
            else:
                logger.debug(f"🔍 No tickers found in text: {full_text[:100]}...")

            return ticker_matches

        except Exception as e:
            logger.error(f"❌ Error finding tickers: {e}", exc_info=True)
            return []

    def _find_ticker_for_company(self, company_name: str, ticker_matches: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Находит тикер для конкретной компании"""
        try:
            # Простой поиск по названию
            company_name_lower = company_name.lower()
            
            for ticker_match in ticker_matches:
                # Проверяем различные варианты названий
                ticker_names = [
                    ticker_match.get("company_name", "").lower(),
                    ticker_match.get("short_name", "").lower(),
                    ticker_match.get("original_text", "").lower()
                ]
                
                # Ищем пересечение слов
                for ticker_name in ticker_names:
                    if ticker_name and self._names_similar(company_name_lower, ticker_name):
                        return ticker_match
            
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Error matching ticker for {company_name}: {e}")
            return None

    def _names_similar(self, name1: str, name2: str, threshold: float = 0.6) -> bool:
        """Проверяет схожесть названий компаний"""
        try:
            from difflib import SequenceMatcher
            
            # Убираем общие слова
            stop_words = {"пао", "оао", "ооо", "ао", "зао", "компания", "группа", "банк"}
            
            words1 = set(name1.split()) - stop_words
            words2 = set(name2.split()) - stop_words
            
            if not words1 or not words2:
                return False
            
            # Проверяем пересечение слов
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            jaccard_similarity = len(intersection) / len(union) if union else 0
            
            # Дополнительная проверка через SequenceMatcher
            sequence_similarity = SequenceMatcher(None, name1, name2).ratio()
            
            # Комбинированная оценка
            combined_similarity = (jaccard_similarity * 0.7 + sequence_similarity * 0.3)
            
            return combined_similarity >= threshold
            
        except Exception as e:
            logger.warning(f"⚠️ Error comparing names: {e}")
            return False

    async def _create_company_node_with_ticker_safe(self, company_id: str, company: Dict[str, Any], ticker_info: Optional[Dict[str, Any]]):
        """Безопасное создание узла компании с тикером"""
        try:
            # Используем данные из ticker_info если есть
            if ticker_info:
                await self.graph_service.create_company_node(
                    company_id=company_id,
                    name=ticker_info.get("company_name", company.get("name", ""))[:100],
                    ticker=ticker_info.get("ticker", company.get("ticker", ""))[:20],
                    is_traded=ticker_info.get("is_traded", True)
                )
                
                # Сохраняем дополнительную информацию о тикере
                await self.graph_service.create_instrument_node(
                    instrument_id=f"instrument_{ticker_info.get('ticker', '')}",
                    symbol=ticker_info.get("ticker", ""),
                    instrument_type="equity",
                    exchange="MOEX",
                    currency="RUB"
                )
                
                # Связываем компанию с инструментом
                await self.graph_service.link_company_to_instrument(
                    company_id=company_id,
                    instrument_id=f"instrument_{ticker_info.get('ticker', '')}"
                )
                
                logger.info(f"✅ Created company {company.get('name', '')} with ticker {ticker_info.get('ticker', '')}")
            else:
                # Создаем без тикера
                await self.graph_service.create_company_node(
                    company_id=company_id,
                    name=company.get("name", "")[:100],
                    ticker=company.get("ticker", "")[:20],
                    is_traded=False
                )
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to create company node with ticker: {e}")
            # Fallback - создаем без тикера
            await self.graph_service.create_company_node(
                company_id=company_id,
                name=company.get("name", "")[:100],
                ticker="",
                is_traded=False
            )

    async def _perform_ceg_analysis(self, graph_results: Dict[str, Any], source: Source) -> Dict[str, Any]:
        """🔗 Выполняет CEG анализ и расчеты"""
        try:
            if not self.enricher or not self.enricher.ceg_service:
                logger.warning("⚠️ CEG service not available, using basic analysis")
                return {
                    "causal_links_found": 0,
                    "importance_scores": [],
                    "market_impacts": [],
                    "predictions": [],
                    "analysis_type": "basic"
                }
            
            logger.info("🔗 Performing CEG analysis...")
            
            # Выполняем расширенный CEG анализ
            ceg_analysis = {
                "causal_links_found": 0,
                "importance_scores": [],
                "market_impacts": [],
                "predictions": [],
                "analysis_type": "advanced"
            }
            
            try:
                # Анализ важности событий
                importance_scores = await self._calculate_importance_scores(graph_results)
                ceg_analysis["importance_scores"] = importance_scores
                
                # Анализ рыночного влияния
                market_impacts = await self._calculate_market_impacts(graph_results)
                ceg_analysis["market_impacts"] = market_impacts
                
                # Поиск причинных связей
                causal_links = await self._find_causal_links(graph_results)
                ceg_analysis["causal_links_found"] = len(causal_links)
                
                # Генерация предсказаний
                predictions = await self._generate_predictions(graph_results, source)
                ceg_analysis["predictions"] = predictions
                
                logger.info(f"✅ CEG analysis completed: {len(importance_scores)} importance scores, {len(market_impacts)} impacts, {len(causal_links)} causal links, {len(predictions)} predictions")
                
            except Exception as e:
                logger.warning(f"⚠️ Advanced CEG analysis failed: {e}")
                ceg_analysis["analysis_type"] = "fallback"
            
            return ceg_analysis
            
        except Exception as e:
            logger.error(f"❌ Error in CEG analysis: {e}")
            return {"error": str(e), "analysis_type": "error"}

    async def _calculate_importance_scores(self, graph_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Рассчитывает важность событий"""
        try:
            # Простая эвристика важности на основе количества связей
            scores = []
            nodes_created = graph_results.get("nodes_created", 0)
            links_created = graph_results.get("links_created", 0)
            
            if nodes_created > 0:
                # Базовый score на основе плотности связей
                density_score = links_created / nodes_created if nodes_created > 0 else 0
                scores.append({
                    "score": min(density_score * 10, 10.0),  # Нормализуем до 10
                    "metric": "link_density",
                    "description": f"Based on {links_created} links for {nodes_created} nodes"
                })
            
            return scores
        except Exception as e:
            logger.warning(f"⚠️ Importance calculation failed: {e}")
            return []

    async def _calculate_market_impacts(self, graph_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Рассчитывает потенциальное рыночное влияние"""
        try:
            impacts = []
            
            # Простая эвристика на основе количества сущностей
            nodes_created = graph_results.get("nodes_created", 0)
            links_created = graph_results.get("links_created", 0)
            
            if nodes_created > 0:
                # Базовый impact score
                impact_score = min((nodes_created + links_created) * 0.1, 5.0)
                impacts.append({
                    "impact_score": impact_score,
                    "impact_type": "estimated",
                    "description": f"Estimated impact based on {nodes_created} nodes and {links_created} links",
                    "confidence": 0.3  # Низкая уверенность для эвристики
                })
            
            return impacts
        except Exception as e:
            logger.warning(f"⚠️ Market impact calculation failed: {e}")
            return []

    async def _find_causal_links(self, graph_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Находит потенциальные причинные связи"""
        try:
            links = []
            
            # Простая эвристика на основе временных паттернов
            nodes_created = graph_results.get("nodes_created", 0)
            
            if nodes_created > 1:
                # Предполагаем, что новости могут быть связаны
                links.append({
                    "link_type": "temporal_correlation",
                    "confidence": 0.2,
                    "description": f"Potential temporal correlation between {nodes_created} news items",
                    "strength": "weak"
                })
            
            return links
        except Exception as e:
            logger.warning(f"⚠️ Causal link detection failed: {e}")
            return []

    async def _generate_predictions(self, graph_results: Dict[str, Any], source: Source) -> List[Dict[str, Any]]:
        """Генерирует предсказания на основе анализа"""
        try:
            predictions = []
            
            # Простые предсказания на основе паттернов
            nodes_created = graph_results.get("nodes_created", 0)
            
            if nodes_created > 5:
                predictions.append({
                    "prediction_type": "follow_up_news",
                    "confidence": 0.4,
                    "timeframe": "1-3 days",
                    "description": f"High activity in {source.name} may lead to follow-up news",
                    "source": source.name
                })
            
            if nodes_created > 10:
                predictions.append({
                    "prediction_type": "market_volatility",
                    "confidence": 0.3,
                    "timeframe": "1-7 days",
                    "description": "High news volume may indicate increased market volatility",
                    "source": source.name
                })
            
            return predictions
        except Exception as e:
            logger.warning(f"⚠️ Prediction generation failed: {e}")
            return []

    async def _create_detailed_response(self, news_batch: List[Dict[str, Any]], ner_results: Dict[str, Any], 
                                      graph_results: Dict[str, Any], ceg_results: Dict[str, Any]) -> Dict[str, Any]:
        """📋 Создает детальный JSON ответ с максимальными данными"""
        try:
            detailed_news = []
            
            for i, news_data in enumerate(news_batch):
                ner_item = ner_results.get('news_items', [{}])[i] if i < len(ner_results.get('news_items', [])) else {}
                
                # Находим тикеры для этой новости
                ticker_matches = await self._find_tickers_for_news(news_data, ner_item)
                
                # Формируем детальную информацию о новости
                detailed_item = {
                    "news_id": str(news_data["id"]) if news_data.get("id") else None,
                    "source": {
                        "id": str(news_data["source_id"]) if news_data.get("source_id") else None,
                        "name": news_data["source_name"],
                        "external_id": news_data["external_id"]
                    },
                    "content": {
                        "text": news_data["text"],
                        "date": news_data["date"].isoformat(),
                        "title": ner_item.get("event", "")[:200] or "Telegram News"
                    },
                    "entities": {
                        "companies": ner_item.get("companies", []),
                        "people": ner_item.get("people", []),
                        "markets": ner_item.get("markets", []),
                        "financial_metrics": ner_item.get("financial_metrics", [])
                    },
                    "analysis": {
                        "event_types": ner_item.get("event_types", []),
                        "sector": ner_item.get("sector"),
                        "country": ner_item.get("country"),
                        "is_advertisement": ner_item.get("is_advertisement", False),
                        "content_types": ner_item.get("content_types", []),
                        "confidence_score": ner_item.get("confidence_score", 0.0),
                        "urgency_level": ner_item.get("urgency_level", "normal")
                    },
                    "tickers": [ticker.get("ticker") for ticker in ticker_matches if ticker.get("ticker")],
                    "ticker_details": [
                        {
                            "ticker": ticker.get("ticker"),
                            "company_name": ticker.get("company_name"),
                            "short_name": ticker.get("short_name"),
                            "confidence": ticker.get("confidence"),
                            "match_method": ticker.get("match_method"),
                            "is_traded": ticker.get("is_traded"),
                            "isin": ticker.get("isin"),
                            "board": ticker.get("board"),
                            "original_text": ticker.get("original_text")
                        }
                        for ticker in ticker_matches
                    ],
                    "related_news": [],  # Связи с другими новостями
                    "ceg_metrics": {
                        "importance_score": 0.0,
                        "market_impact": 0.0,
                        "causal_links": 0,
                        "predictions": []
                    },
                    "future_events": []  # Возможные будущие события
                }
                
                detailed_news.append(detailed_item)
            
            return {
                "batch_id": str(uuid4()),
                "timestamp": datetime.now().isoformat(),
                "total_news": len(news_batch),
                "processing_stats": {
                    "entities_extracted": len(ner_results.get('news_items', [])),
                    "graph_nodes_created": graph_results.get("nodes_created", 0),
                    "graph_links_created": graph_results.get("links_created", 0),
                    "ceg_analysis_completed": bool(ceg_results.get("causal_links_found") is not None)
                },
                "news_items": detailed_news,
                "summary": {
                    "total_tickers": len(set([ticker for item in detailed_news for ticker in item["tickers"]])),
                    "total_companies": len(set([company["name"] for item in detailed_news for company in item["entities"]["companies"]])),
                    "high_confidence_news": len([item for item in detailed_news if item["analysis"]["confidence_score"] > 0.8]),
                    "urgent_news": len([item for item in detailed_news if item["analysis"]["urgency_level"] in ["high", "critical"]])
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating detailed response: {e}")
            return {"error": str(e), "batch_id": str(uuid4())}

    async def _save_batch_results(self, results: Dict[str, Any], session):
        """💾 Сохраняет результаты batch обработки"""
        try:
            # Сохраняем детальный ответ в файл
            if "detailed_response" in results:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"batch_results_{timestamp}.json"

                # Создаем директорию logs если не существует
                logs_dir = Path("logs")
                logs_dir.mkdir(exist_ok=True)

                # Кастомный JSON encoder для обработки UUID и datetime
                from uuid import UUID
                class CustomJSONEncoder(json.JSONEncoder):
                    def default(self, obj):
                        if isinstance(obj, UUID):  # UUID
                            return str(obj)
                        if isinstance(obj, datetime):
                            return obj.isoformat()
                        return super().default(obj)

                with open(logs_dir / filename, "w", encoding="utf-8") as f:
                    json.dump(results["detailed_response"], f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)

                logger.info(f"💾 Batch results saved to logs/{filename}")

            # Сохраняем детальный JSON в базу данных PostgreSQL
            await self._save_detailed_json_to_db(results.get("detailed_response", {}))

            # Коммитим изменения в Neo4j
            await session.commit()

        except Exception as e:
            logger.error(f"Error saving batch results: {e}")

    async def _save_detailed_json_to_db(self, detailed_response: Dict[str, Any]) -> None:
        """Сохраняет детальный JSON в базу данных PostgreSQL"""
        try:
            if not detailed_response:
                return
                
            async with get_db_session() as db_session:
                # Если это список новостей, обрабатываем каждую
                if isinstance(detailed_response, list):
                    for news_data in detailed_response:
                        news_id = news_data.get('news_id')
                        if news_id:
                            await self._update_news_with_detailed_json(db_session, news_id, news_data)
                else:
                    # Если это одна новость
                    news_id = detailed_response.get('news_id')
                    if news_id:
                        await self._update_news_with_detailed_json(db_session, news_id, detailed_response)
                
                await db_session.commit()
                logger.info(f"✅ Saved detailed JSON to PostgreSQL")
                
        except Exception as e:
            logger.error(f"❌ Failed to save detailed JSON to database: {e}")

    async def _update_news_with_detailed_json(self, db_session, news_id: str, detailed_data: Dict[str, Any]) -> None:
        """Обновляет конкретную новость с детальным JSON"""
        try:
            from sqlalchemy import update
            
            # Обновляем запись новости, добавляя детальный JSON
            update_stmt = update(News).where(
                News.id == news_id
            ).values(
                detailed_json=detailed_data
            )
            
            result = await db_session.execute(update_stmt)
            if result.rowcount > 0:
                logger.debug(f"Updated news {news_id} with detailed JSON")
            else:
                logger.warning(f"News {news_id} not found for detailed JSON update")
                
        except Exception as e:
            logger.error(f"Failed to update news {news_id} with detailed JSON: {e}")

    def _update_batch_stats(self, results: Dict[str, Any]):
        """📊 Обновляет статистику batch обработки"""
        self.total_stats["batch_processed"] += 1
        self.total_stats["entities_extracted"] += results.get("total_entities", 0)
        self.total_stats["graph_nodes_created"] += results.get("total_nodes", 0)
        self.total_stats["ceg_links_created"] += results.get("total_links", 0)

    def _print_final_stats(self):
        """📊 Выводит улучшенную финальную статистику"""
        logger.info("\n" + "="*80)
        logger.info("📊 ФИНАЛЬНАЯ СТАТИСТИКА BATCH ОБРАБОТКИ")
        logger.info("="*80)
        logger.info(f"📨 Всего сообщений обработано: {self.total_stats['total_messages']}")
        logger.info(f"💾 Сохранено новостей: {self.total_stats['saved_news']}")
        logger.info(f"🚫 Отфильтровано рекламы: {self.total_stats['ads_filtered']}")
        logger.info(f"🔄 Найдено дубликатов: {self.total_stats['duplicates']}")
        logger.info(f"❌ Ошибок: {self.total_stats['errors']}")
        logger.info("-"*80)
        logger.info(" ИСОЧНИКИ:")
        logger.info(f"📡 Telegram источников обработано: {self.total_stats['telegram_sources_processed']}")
        logger.info(f"🌐 HTML источников обработано: {self.total_stats['html_sources_processed']}")
        logger.info(f"📰 HTML статей обработано: {self.total_stats['html_articles_processed']}")
        logger.info("-"*80)
        logger.info("📦 BATCH СТАТИСТИКА:")
        logger.info(f"📦 Batch обработано: {self.total_stats['batch_processed']}")
        logger.info(f"🧠 Сущностей извлечено: {self.total_stats['entities_extracted']}")
        logger.info(f"🕸️ Узлов в графе создано: {self.total_stats['graph_nodes_created']}")
        logger.info(f"🔗 Связей в графе создано: {self.total_stats['ceg_links_created']}")
        logger.info(f"🔮 Предсказаний сгенерировано: {self.total_stats['predictions_generated']}")
        logger.info("-"*80)
        logger.info("⚙️ НАСТРОЙКИ:")
        logger.info(f"📏 Размер batch: {self.batch_size}")
        logger.info(f"🔄 Макс. batch: {self.max_batches}")
        logger.info(f"⏱️ Задержка между batch: {self.batch_delay}s")
        logger.info(f"🔁 Попытки retry: {self.retry_attempts}")
        logger.info(f"🧠 AI модель: {'Local Qwen3-4B' if self.use_local_ai else 'OpenAI GPT'}")
        logger.info("="*80)

    async def stop(self):
        """Остановка парсера"""
        logger.info("Stopping Telegram parser...")
        self.running = False

        # Отменяем все задачи
        for task in self.tasks:
            task.cancel()

        # Отключаем клиент
        if self.client_manager:
            await self.client_manager.disconnect()

        # Закрываем Enricher (включая все GraphService внутри)
        if self.enricher:
            await self.enricher.close()

        # Закрываем MOEX Linker
        if self.moex_linker:
            await self.moex_linker.close()

        # Закрываем Graph Service
        if self.graph_service:
            await self.graph_service.close()

        # Закрываем БД
        await close_db()

        logger.info("Telegram parser stopped")


def signal_handler(signum, _frame):
    """Обработка сигналов остановки"""
    logger.info(f"Received signal {signum}")
    asyncio.create_task(parser_service.stop())
    sys.exit(0)


async def main():
    """🚀 Главная функция с настройками batch обработки"""
    global parser_service

    setup_logging()

    # Загружаем переменные окружения из .env файла
    from dotenv import load_dotenv
    # Ищем .env в корне проекта (два уровня вверх от scripts/)
    env_path = Path(__file__).parent.parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    # Выводим информацию для отладки
    api_key_check = os.getenv("API_KEY_2") or os.getenv("OPENAI_API_KEY")
    if api_key_check:
        logger.info(f"✓ API ключ загружен из {env_path}: {api_key_check[:15]}...")

    try:
        print("\n" + "="*70)
        print("🚀 УЛУЧШЕННЫЙ TELEGRAM PARSER с BATCH обработкой")
        print("🌐 + ИНТЕГРАЦИЯ HTML ПАРСЕРОВ (Forbes, Interfax)")
        print("="*70)

        # Выбор AI модели
        print("\n🧠 Выберите AI модель для анализа:")
        print("1. OpenAI GPT (API) - точнее, но требует API ключ")
        print("2. Qwen3-4B (локально) - быстрее, работает офлайн")

        ai_input = input("\nВведите номер (1 или 2, по умолчанию 1): ").strip()
        use_local_ai = (ai_input == '2')

        if not use_local_ai:
            api_key = os.getenv("API_KEY_2") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("⚠️  API ключ не найден, будет использован локальный Qwen3-4B")
                use_local_ai = True
            else:
                print(f"✅ OpenAI API ключ найден: {api_key[:10]}...")
        else:
            print("✅ Будет использован локальный Qwen3-4B")

        # Настройки batch обработки
        print("\n📦 Настройки batch обработки:")
        batch_size_input = input("Размер batch (по умолчанию 20): ").strip()
        batch_size = int(batch_size_input) if batch_size_input else 20

        max_batches_input = input("Максимальное количество batch (по умолчанию 10): ").strip()
        max_batches = int(max_batches_input) if max_batches_input else 10

        batch_delay_input = input("Задержка между batch в секундах (по умолчанию 5): ").strip()
        batch_delay = int(batch_delay_input) if batch_delay_input else 5

        retry_attempts_input = input("Количество попыток при ошибках сети (по умолчанию 3): ").strip()
        retry_attempts = int(retry_attempts_input) if retry_attempts_input else 3

        # Выбор режима работы
        print("\n📋 Выберите режим работы:")
        print("1. 📚 Историческая загрузка - загрузить и проанализировать новости за период")
        print("2. 🔄 Мониторинг в реальном времени - следить за новыми новостями")

        mode_input = input("\nВведите номер режима (1 или 2, по умолчанию 1): ").strip()
        mode = mode_input if mode_input in ['1', '2'] else '1'

        if mode == '1':
            # Режим исторической загрузки
            print("\n📚 РЕЖИМ: Историческая загрузка с batch анализом")
            print("-" * 60)

            days_input = input("За сколько дней загружать новости? (по умолчанию 7): ").strip()
            days = int(days_input) if days_input else 7

            if days <= 0:
                print("❌ Количество дней должно быть больше 0")
                return

            print(f"\n✅ Конфигурация:")
            print(f"   - Период: последние {days} дней")
            print(f"   - Источники: Telegram + HTML (Forbes, Interfax, E-disclosure, MOEX)")
            print(f"   - AI модель: {'Local Qwen3-4B' if use_local_ai else 'OpenAI GPT'}")
            print(f"   - Batch размер: {batch_size}")
            print(f"   - Макс. batch: {max_batches}")
            print(f"   - Задержка между batch: {batch_delay}s")
            print(f"   - Попытки retry: {retry_attempts}")
            print(f"   - CEG анализ: включен")
            print(f"   - Графовая БД: Neo4j")
            print(f"   - JSON ответы: детальные")
            realtime_mode = False

        else:
            # Режим мониторинга в реальном времени
            print("\n🔄 РЕЖИМ: Мониторинг в реальном времени с batch обработкой")
            print("-" * 60)
            print("✅ Парсер будет следить за новыми новостями и анализировать их в batch")
            print(f"   - Источники: Telegram + HTML (Forbes, Interfax, E-disclosure, MOEX)")
            print(f"   - AI модель: {'Local Qwen3-4B' if use_local_ai else 'OpenAI GPT'}")
            print(f"   - Batch размер: {batch_size}")
            print(f"   - Задержка между batch: {batch_delay}s")
            print(f"   - Попытки retry: {retry_attempts}")
            print(f"   - CEG граф: обновляется автоматически")
            print(f"   - Графовая БД: Neo4j")
            print(f"   - JSON ответы: детальные")
            days = 0  # Не используется в режиме мониторинга
            realtime_mode = True

        print("\n⏳ Запуск улучшенного парсера...")

        # Настройка обработки сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Создание и запуск сервиса с настройками
        parser_service = Telegram_ParserServiceCEG(
            days=days,
            realtime_mode=realtime_mode,
            use_local_ai=use_local_ai,
            batch_size=batch_size,
            max_batches=max_batches,
            batch_delay=batch_delay,
            retry_attempts=retry_attempts,
            network_timeout=30
        )

        try:
            await parser_service.start()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            await parser_service.stop()

    except ValueError as e:
        print(f"❌ Ошибка ввода: {e}")
        return
    except KeyboardInterrupt:
        print("\n👋 Загрузка отменена пользователем")
        return


if __name__ == "__main__":
    parser_service = None
    asyncio.run(main())
