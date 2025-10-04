# scripts/start_outbox_relay.py
"""
Скрипт запуска Outbox Relay сервиса
Читает события из outbox таблицы и публикует их в RabbitMQ
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Добавляем корень проекта в PATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.core.database import init_db, close_db
from src.services.outbox.relay import OutboxRelay, OutboxRelayHealthCheck
from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class OutboxRelayService:
    """Сервис для запуска Outbox Relay"""
    
    def __init__(self):
        self.relay: OutboxRelay = None
        self.health_check: OutboxRelayHealthCheck = None
        self.cleanup_task = None
        self.running = False
    
    async def start(self):
        """Запуск сервиса"""
        try:
            # Инициализация БД
            await init_db()
            logger.info("Database initialized")
            
            # Создание Outbox Relay
            self.relay = OutboxRelay(
                poll_interval=getattr(settings, 'OUTBOX_POLL_INTERVAL', 5),
                batch_size=getattr(settings, 'OUTBOX_BATCH_SIZE', 100),
                max_retries=getattr(settings, 'OUTBOX_MAX_RETRIES', 3),
                retry_delay_seconds=getattr(settings, 'OUTBOX_RETRY_DELAY', 60)
            )
            
            self.health_check = OutboxRelayHealthCheck(self.relay)
            
            logger.info("Starting Outbox Relay...")
            
            # Запускаем периодическую очистку старых событий
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            
            # Запускаем основной relay
            self.running = True
            await self.relay.start()
            
        except Exception as e:
            logger.error(f"Failed to start Outbox Relay: {e}", exc_info=True)
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Остановка сервиса"""
        logger.info("Stopping Outbox Relay Service...")
        self.running = False
        
        # Отменяем cleanup task
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Останавливаем relay
        if self.relay:
            await self.relay.stop()
        
        # Закрываем БД
        await close_db()
        
        logger.info("Outbox Relay Service stopped")
    
    async def _periodic_cleanup(self):
        """
        Периодическая очистка старых событий
        Запускается раз в день
        """
        cleanup_interval = 86400  # 24 часа
        days_to_keep = getattr(settings, 'OUTBOX_KEEP_DAYS', 7)
        
        while self.running:
            try:
                await asyncio.sleep(cleanup_interval)
                
                if self.relay:
                    logger.info("Running outbox cleanup...")
                    deleted = await self.relay.cleanup_old_events(days_to_keep)
                    logger.info(f"Cleanup completed, deleted {deleted} events")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}", exc_info=True)
    
    async def get_health_status(self) -> dict:
        """Получение статуса здоровья сервиса"""
        if self.health_check:
            return await self.health_check.get_status()
        return {'status': 'not_initialized'}


# Глобальная переменная для signal handler
relay_service: OutboxRelayService = None


def signal_handler(signum, frame):
    """Обработка сигналов остановки"""
    logger.info(f"Received signal {signum}")
    if relay_service:
        asyncio.create_task(relay_service.stop())
    sys.exit(0)


async def main():
    """Главная функция"""
    global relay_service
    
    setup_logging()
    logger.info("=" * 60)
    logger.info("Starting Outbox Relay Service")
    logger.info("=" * 60)
    
    # Настройка обработки сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Создание и запуск сервиса
    relay_service = OutboxRelayService()
    
    try:
        await relay_service.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await relay_service.stop()


if __name__ == "__main__":
    # Проверка настроек
    if not hasattr(settings, 'RABBITMQ_URL') or not settings.RABBITMQ_URL:
        logger.error("RABBITMQ_URL not configured in settings")
        sys.exit(1)
    
    if not hasattr(settings, 'DATABASE_URL') or not settings.DATABASE_URL:
        logger.error("DATABASE_URL not configured in settings")
        sys.exit(1)
    
    logger.info(f"RabbitMQ URL: {settings.RABBITMQ_URL}")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")
    
    # Запуск
    asyncio.run(main())


