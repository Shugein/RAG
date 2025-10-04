# src/services/outbox/relay.py
"""
Outbox Relay Service - реализация Transactional Outbox паттерна
Читает события из outbox таблицы и публикует их в RabbitMQ
"""

import asyncio
import logging
from typing import List, Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from src.core.models import OutboxEvent
from src.core.database import get_db_session
from src.services.outbox.publisher import RabbitMQPublisher
from src.core.config import settings

logger = logging.getLogger(__name__)


class OutboxRelay:
    """
    Outbox Relay сервис
    
    Периодически читает pending события из outbox таблицы 
    и публикует их в RabbitMQ с retry логикой
    """
    
    def __init__(
        self,
        poll_interval: int = 5,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay_seconds: int = 60
    ):
        """
        Инициализация relay сервиса
        
        Args:
            poll_interval: Интервал polling в секундах
            batch_size: Размер батча событий для обработки
            max_retries: Максимальное количество попыток
            retry_delay_seconds: Базовая задержка между retry
        """
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        
        self.publisher: Optional[RabbitMQPublisher] = None
        self.running = False
    
    async def start(self):
        """Запуск relay сервиса"""
        try:
            # Инициализация RabbitMQ publisher
            self.publisher = RabbitMQPublisher()
            await self.publisher.connect()
            
            self.running = True
            logger.info("Outbox Relay started")
            
            # Основной цикл обработки
            while self.running:
                try:
                    await self._process_batch()
                except Exception as e:
                    logger.error(f"Error processing batch: {e}", exc_info=True)
                
                # Ждем перед следующей итерацией
                await asyncio.sleep(self.poll_interval)
                
        except Exception as e:
            logger.error(f"Outbox Relay failed to start: {e}", exc_info=True)
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Остановка relay сервиса"""
        self.running = False
        
        if self.publisher:
            await self.publisher.disconnect()
        
        logger.info("Outbox Relay stopped")
    
    async def _process_batch(self):
        """
        Обработка батча событий
        
        1. Читает pending события или события готовые к retry
        2. Публикует их в RabbitMQ
        3. Обновляет статус в БД
        """
        async with get_db_session() as session:
            # Получаем события для обработки
            events = await self._fetch_pending_events(session)
            
            if not events:
                logger.debug("No pending events to process")
                return
            
            logger.info(f"Processing {len(events)} outbox events")
            
            # Обрабатываем каждое событие
            for event in events:
                try:
                    await self._process_event(event, session)
                except Exception as e:
                    logger.error(f"Error processing event {event.id}: {e}")
                    await self._handle_event_failure(event, session, str(e))
            
            # Сохраняем изменения
            await session.commit()
    
    async def _fetch_pending_events(self, session: AsyncSession) -> List[OutboxEvent]:
        """
        Получение событий для обработки
        
        Выбирает события которые:
        - В статусе pending
        - ИЛИ в статусе failed, но не превысили max_retries и настало время retry
        
        Args:
            session: Database session
            
        Returns:
            Список событий для обработки
        """
        now = datetime.utcnow()
        
        query = select(OutboxEvent).where(
            or_(
                # Pending события
                OutboxEvent.status == 'pending',
                
                # Failed события готовые к retry
                and_(
                    OutboxEvent.status == 'failed',
                    OutboxEvent.retry_count < OutboxEvent.max_retries,
                    or_(
                        OutboxEvent.next_retry_at.is_(None),
                        OutboxEvent.next_retry_at <= now
                    )
                )
            )
        ).order_by(
            OutboxEvent.created_at
        ).limit(self.batch_size)
        
        result = await session.execute(query)
        events = result.scalars().all()
        
        return list(events)
    
    async def _process_event(self, event: OutboxEvent, session: AsyncSession):
        """
        Обработка одного события
        
        Args:
            event: Событие из outbox
            session: Database session
        """
        logger.debug(f"Processing event {event.id} (type: {event.event_type})")
        
        # Публикуем в RabbitMQ
        success = await self.publisher.publish_event(
            event_type=event.event_type,
            payload=event.payload_json,
            routing_key=event.event_type
        )
        
        if success:
            # Успешная публикация - помечаем как sent
            event.status = 'sent'
            event.processed_at = datetime.utcnow()
            event.error_message = None
            
            logger.info(f"Event {event.id} published successfully")
        else:
            # Ошибка публикации
            raise Exception("Failed to publish to RabbitMQ")
    
    async def _handle_event_failure(
        self, 
        event: OutboxEvent, 
        session: AsyncSession,
        error_message: str
    ):
        """
        Обработка ошибки публикации события
        
        Реализует exponential backoff для retry
        
        Args:
            event: Событие которое не удалось опубликовать
            session: Database session
            error_message: Сообщение об ошибке
        """
        event.retry_count += 1
        event.error_message = error_message
        
        if event.retry_count >= event.max_retries:
            # Превышено максимальное количество попыток
            event.status = 'failed'
            event.processed_at = datetime.utcnow()
            
            logger.error(
                f"Event {event.id} failed permanently after {event.retry_count} attempts: "
                f"{error_message}"
            )
        else:
            # Планируем retry с exponential backoff
            event.status = 'failed'
            
            # Exponential backoff: delay * 2^(retry_count - 1)
            delay_seconds = self.retry_delay_seconds * (2 ** (event.retry_count - 1))
            event.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            
            logger.warning(
                f"Event {event.id} failed (attempt {event.retry_count}/{event.max_retries}). "
                f"Next retry at {event.next_retry_at}. Error: {error_message}"
            )
    
    async def cleanup_old_events(self, days_to_keep: int = 7):
        """
        Очистка старых успешно отправленных событий
        
        Args:
            days_to_keep: Количество дней для хранения
        """
        async with get_db_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Удаляем старые успешные события
            from sqlalchemy import delete
            
            stmt = delete(OutboxEvent).where(
                and_(
                    OutboxEvent.status == 'sent',
                    OutboxEvent.processed_at < cutoff_date
                )
            )
            
            result = await session.execute(stmt)
            await session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"Cleaned up {deleted_count} old outbox events")
            
            return deleted_count
    
    async def get_statistics(self) -> dict:
        """
        Получение статистики outbox
        
        Returns:
            Словарь со статистикой
        """
        async with get_db_session() as session:
            from sqlalchemy import func
            
            # Подсчитываем события по статусам
            query = select(
                OutboxEvent.status,
                func.count(OutboxEvent.id).label('count')
            ).group_by(OutboxEvent.status)
            
            result = await session.execute(query)
            stats_by_status = {row.status: row.count for row in result}
            
            # Подсчитываем события с ошибками
            failed_query = select(func.count(OutboxEvent.id)).where(
                and_(
                    OutboxEvent.status == 'failed',
                    OutboxEvent.retry_count >= OutboxEvent.max_retries
                )
            )
            permanently_failed = await session.scalar(failed_query)
            
            return {
                'by_status': stats_by_status,
                'permanently_failed': permanently_failed or 0,
                'total': sum(stats_by_status.values())
            }


class OutboxRelayHealthCheck:
    """Проверка здоровья Outbox Relay сервиса"""
    
    def __init__(self, relay: OutboxRelay):
        self.relay = relay
    
    async def is_healthy(self) -> bool:
        """
        Проверка работоспособности
        
        Returns:
            True если сервис работает нормально
        """
        try:
            # Проверяем что relay запущен
            if not self.relay.running:
                logger.warning("Outbox relay is not running")
                return False
            
            # Проверяем подключение к RabbitMQ
            if not self.relay.publisher or not self.relay.publisher.connection:
                logger.warning("RabbitMQ not connected")
                return False
            
            if self.relay.publisher.connection.is_closed:
                logger.warning("RabbitMQ connection is closed")
                return False
            
            # Проверяем количество failed событий
            stats = await self.relay.get_statistics()
            permanently_failed = stats.get('permanently_failed', 0)
            
            if permanently_failed > 100:  # Threshold
                logger.warning(f"Too many permanently failed events: {permanently_failed}")
                # Не возвращаем False, только предупреждаем
            
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def get_status(self) -> dict:
        """
        Получение детального статуса
        
        Returns:
            Словарь со статусом компонентов
        """
        status = {
            'relay_running': self.relay.running,
            'rabbitmq_connected': False,
            'statistics': {}
        }
        
        try:
            if self.relay.publisher and self.relay.publisher.connection:
                status['rabbitmq_connected'] = not self.relay.publisher.connection.is_closed
            
            status['statistics'] = await self.relay.get_statistics()
            
        except Exception as e:
            status['error'] = str(e)
        
        return status


