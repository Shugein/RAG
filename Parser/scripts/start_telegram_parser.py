# scripts/start_telegram_parser.py
"""
Скрипт запуска Telegram парсера
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.database import init_db, close_db, get_db_session
from src.services.telegram_parser.client import TelegramClientManager
from src.services.telegram_parser.parser import TelegramParser
from src.services.telegram_parser.antispam import AntiSpamFilter
from src.services.enricher.enrichment_service import EnrichmentService
from src.utils.logging import setup_logging
from src.core.models import Source
from sqlalchemy import select

logger = logging.getLogger(__name__)


class TelegramParserService:
    def __init__(self, days: int = 7, realtime_mode: bool = False):
        self.client_manager = TelegramClientManager()
        self.client = None
        self.parser = None
        self.enricher = None
        self.running = False
        self.tasks = []
        self.days = days
        self.realtime_mode = realtime_mode
    
    async def start(self):
        """Запуск парсера"""
        try:
            # Инициализация БД
            await init_db()
            
            # Инициализация Telegram клиента
            logger.info("Initializing Telegram client...")
            self.client = await self.client_manager.initialize()
            
            # Создание компонентов
            anti_spam = AntiSpamFilter(Path("config/ad_rules.yml"))
            
            async with get_db_session() as session:
                self.parser = TelegramParser(
                    client=self.client,
                    db_session=session,
                    anti_spam=anti_spam
                )
                
                # Инициализация enricher если включен
                if settings.ENABLE_ENRICHMENT:
                    self.enricher = EnrichmentService(session)
                
                # Получаем все активные Telegram источники
                result = await session.execute(
                    select(Source).where(
                        Source.kind == "telegram",
                        Source.enabled == True
                    )
                )
                sources = result.scalars().all()
                
                if not sources:
                    logger.warning("No active Telegram sources found")
                    return
                
                logger.info(f"Found {len(sources)} active Telegram sources")
                
                # Информация о режиме работы
                if self.realtime_mode:
                    logger.info("🔄 Running in REAL-TIME MONITORING mode")
                else:
                    logger.info(f"📚 Running in HISTORICAL LOADING mode (last {self.days} days)")
                
                # Запускаем мониторинг для каждого источника
                self.running = True
                for source in sources:
                    task = asyncio.create_task(
                        self._monitor_source(source)
                    )
                    self.tasks.append(task)
                
                # Ждем завершения всех задач
                await asyncio.gather(*self.tasks)
                
        except Exception as e:
            logger.error(f"Failed to start Telegram parser: {e}")
            raise
        finally:
            await self.stop()
    
    async def _monitor_source(self, source: Source):
        """Мониторинг одного источника"""
        logger.info(f"Starting monitor for {source.name} ({source.code})")
        
        # Сначала выполняем backfill если нужно
        async with get_db_session() as session:
            parser = TelegramParser(
                client=self.client,
                db_session=session,
                anti_spam=AntiSpamFilter()
            )
            
            # Проверяем, нужен ли backfill (только в режиме исторической загрузки)
            config = source.config or {}
            if not self.realtime_mode and config.get("backfill_enabled", True):
                logger.info(f"Starting backfill for {source.code} (last {self.days} days)")
                try:
                    stats = await parser.parse_channel(
                        source=source,
                        backfill=True,
                        limit=config.get("fetch_limit", 1000),
                        days=self.days
                    )
                    logger.info(f"Backfill stats for {source.code}: {stats}")
                except Exception as e:
                    logger.error(f"Backfill failed for {source.code}: {e}")
            
            # В режиме исторической загрузки выходим после backfill
            if not self.realtime_mode:
                logger.info(f"Historical loading completed for {source.code}")
                return
        
        # Режим real-time мониторинга
        logger.info(f"Starting real-time monitoring for {source.code}")
        while self.running:
            try:
                async with get_db_session() as session:
                    parser = TelegramParser(
                        client=self.client,
                        db_session=session,
                        anti_spam=AntiSpamFilter()
                    )
                    
                    # Получаем новые сообщения
                    stats = await parser.parse_channel(
                        source=source,
                        backfill=False,
                        limit=10  # Только последние сообщения
                    )
                    
                    if stats["saved_news"] > 0:
                        logger.info(f"Processed {stats['saved_news']} new items from {source.code}")
                
                # Ждем перед следующей проверкой
                await asyncio.sleep(settings.PARSER_POLL_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error monitoring {source.code}: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке
    
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
        
        # Закрываем БД
        await close_db()
        
        logger.info("Telegram parser stopped")


def signal_handler(signum, frame):
    """Обработка сигналов остановки"""
    logger.info(f"Received signal {signum}")
    asyncio.create_task(parser_service.stop())
    sys.exit(0)


async def main():
    """Главная функция"""
    global parser_service
    
    setup_logging()
    logger.info("Starting Telegram Parser Service")
    
    # Запрашиваем параметры у пользователя
    print("\n" + "="*60)
    print("🔍 НАСТРОЙКА ПАРСЕРА НОВОСТЕЙ")
    print("="*60)
    
    try:
        # Выбор режима работы
        print("\n📋 Выберите режим работы:")
        print("1. 📚 Историческая загрузка - загрузить новости за определенный период")
        print("2. 🔄 Мониторинг в реальном времени - следить за новыми новостями")
        
        mode_input = input("\nВведите номер режима (1 или 2, по умолчанию 1): ").strip()
        mode = mode_input if mode_input in ['1', '2'] else '1'
        
        if mode == '1':
            # Режим исторической загрузки
            print("\n📚 РЕЖИМ: Историческая загрузка")
            print("-" * 40)
            
            days_input = input("За сколько дней загружать новости? (по умолчанию 7): ").strip()
            days = int(days_input) if days_input else 7
            
            if days <= 0:
                print("❌ Количество дней должно быть больше 0")
                return
                
            print(f"✅ Будет загружено новостей за последние {days} дней")
            realtime_mode = False
            
        else:
            # Режим мониторинга в реальном времени
            print("\n🔄 РЕЖИМ: Мониторинг в реальном времени")
            print("-" * 40)
            print("✅ Парсер будет следить за новыми новостями и загружать их по мере появления")
            days = 0  # Не используется в режиме мониторинга
            realtime_mode = True
        
        # Настройка обработки сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Создание и запуск сервиса
        parser_service = TelegramParserService(days=days, realtime_mode=realtime_mode)
        
        try:
            await parser_service.start()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            await parser_service.stop()
            
    except ValueError:
        print("❌ Введите корректное число дней")
        return
    except KeyboardInterrupt:
        print("\n👋 Загрузка отменена пользователем")
        return


if __name__ == "__main__":
    parser_service = None
    asyncio.run(main())