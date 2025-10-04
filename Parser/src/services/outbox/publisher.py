# src/services/outbox/publisher.py
"""
Event Publisher для публикации событий в RabbitMQ
Часть реализации Transactional Outbox паттерна
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType

from src.core.models import News, OutboxEvent
from src.core.config import settings

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Публикатор событий в RabbitMQ
    
    Создает события в outbox таблице при изменениях в БД.
    Фактическая публикация происходит через OutboxRelay сервис.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Инициализация publisher'а
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def publish_news_created(
        self, 
        news: News, 
        enrichment_data: Optional[Dict[str, Any]] = None
    ):
        """
        Публикация события создания новости
        
        Создает запись в outbox таблице с событием news.created
        
        Args:
            news: Объект новости
            enrichment_data: Дополнительные данные обогащения
        """
        payload = {
            "event_type": "news.created",
            "news_id": str(news.id),
            "source_id": str(news.source_id),
            "title": news.title,
            "published_at": news.published_at.isoformat() if news.published_at else None,
            "url": news.url,
            "is_ad": news.is_ad,
            "lang": news.lang,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Добавляем данные обогащения если есть
        if enrichment_data:
            payload["enrichment"] = enrichment_data
        
        # Создаем событие в outbox
        outbox_event = OutboxEvent(
            event_type="news.created",
            aggregate_id=news.id,
            payload_json=payload,
            status="pending",
            retry_count=0,
            max_retries=settings.OUTBOX_MAX_RETRIES if hasattr(settings, 'OUTBOX_MAX_RETRIES') else 3
        )
        
        self.session.add(outbox_event)
        
        logger.debug(f"Created outbox event for news {news.id}")
    
    async def publish_news_updated(
        self, 
        news: News,
        changes: Optional[Dict[str, Any]] = None
    ):
        """
        Публикация события обновления новости
        
        Args:
            news: Объект новости
            changes: Словарь изменений
        """
        payload = {
            "event_type": "news.updated",
            "news_id": str(news.id),
            "source_id": str(news.source_id),
            "title": news.title,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        if changes:
            payload["changes"] = changes
        
        outbox_event = OutboxEvent(
            event_type="news.updated",
            aggregate_id=news.id,
            payload_json=payload,
            status="pending",
            retry_count=0,
            max_retries=settings.OUTBOX_MAX_RETRIES if hasattr(settings, 'OUTBOX_MAX_RETRIES') else 3
        )
        
        self.session.add(outbox_event)
        
        logger.debug(f"Created update event for news {news.id}")
    
    async def publish_enrichment_completed(
        self,
        news: News,
        enrichment: Dict[str, Any]
    ):
        """
        Публикация события завершения обогащения
        
        Args:
            news: Объект новости
            enrichment: Результаты обогащения
        """
        payload = {
            "event_type": "news.enriched",
            "news_id": str(news.id),
            "enrichment": enrichment,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        outbox_event = OutboxEvent(
            event_type="news.enriched",
            aggregate_id=news.id,
            payload_json=payload,
            status="pending",
            retry_count=0,
            max_retries=settings.OUTBOX_MAX_RETRIES if hasattr(settings, 'OUTBOX_MAX_RETRIES') else 3
        )
        
        self.session.add(outbox_event)
        
        logger.debug(f"Created enrichment event for news {news.id}")


class RabbitMQPublisher:
    """
    Прямой публикатор событий в RabbitMQ
    
    Используется OutboxRelay сервисом для фактической отправки событий
    """
    
    def __init__(self):
        """Инициализация RabbitMQ publisher'а"""
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
    
    async def connect(self):
        """Установка соединения с RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URL,
                timeout=10
            )
            
            self.channel = await self.connection.channel()
            
            # Устанавливаем QoS - не более 10 неподтвержденных сообщений
            await self.channel.set_qos(prefetch_count=10)
            
            # Создаем или получаем exchange
            self.exchange = await self.channel.declare_exchange(
                name=settings.RABBITMQ_EXCHANGE if hasattr(settings, 'RABBITMQ_EXCHANGE') else 'news_events',
                type=ExchangeType.TOPIC,
                durable=True
            )
            
            logger.info("RabbitMQ connection established")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def disconnect(self):
        """Закрытие соединения"""
        if self.channel:
            await self.channel.close()
        
        if self.connection:
            await self.connection.close()
        
        logger.info("RabbitMQ connection closed")
    
    async def publish_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        routing_key: Optional[str] = None
    ) -> bool:
        """
        Публикация события в RabbitMQ
        
        Args:
            event_type: Тип события (news.created, news.updated, etc.)
            payload: Данные события
            routing_key: Ключ маршрутизации (по умолчанию = event_type)
            
        Returns:
            True если успешно опубликовано, False иначе
        """
        if not self.exchange:
            logger.error("RabbitMQ not connected")
            return False
        
        try:
            # Формируем сообщение
            message_body = json.dumps(payload, ensure_ascii=False, default=str)
            
            message = Message(
                body=message_body.encode('utf-8'),
                content_type='application/json',
                delivery_mode=DeliveryMode.PERSISTENT,  # Сообщение сохраняется на диск
                timestamp=datetime.utcnow(),
                headers={
                    'event_type': event_type,
                    'publisher': 'news-aggregator'
                }
            )
            
            # Публикуем в exchange
            await self.exchange.publish(
                message=message,
                routing_key=routing_key or event_type
            )
            
            logger.debug(f"Published event {event_type} to RabbitMQ")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
            return False
    
    async def publish_with_retry(
        self,
        event_type: str,
        payload: Dict[str, Any],
        max_retries: int = 3,
        routing_key: Optional[str] = None
    ) -> bool:
        """
        Публикация с retry логикой
        
        Args:
            event_type: Тип события
            payload: Данные события
            max_retries: Максимальное количество попыток
            routing_key: Ключ маршрутизации
            
        Returns:
            True если успешно, False после всех попыток
        """
        for attempt in range(max_retries):
            try:
                success = await self.publish_event(event_type, payload, routing_key)
                if success:
                    return True
                
            except Exception as e:
                logger.warning(f"Publish attempt {attempt + 1}/{max_retries} failed: {e}")
                
                # Если это не последняя попытка, переподключаемся
                if attempt < max_retries - 1:
                    try:
                        await self.disconnect()
                        await self.connect()
                    except Exception as reconnect_error:
                        logger.error(f"Reconnect failed: {reconnect_error}")
        
        logger.error(f"Failed to publish event {event_type} after {max_retries} attempts")
        return False


