"""
Real-time триггер для обработки новостей из Telegram
Публикует в RabbitMQ согласно архитектуре RADAR AI
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4

from telethon import TelegramClient, events
from telethon.tl.types import Message
import aio_pika
from aio_pika import Message as AMQPMessage, ExchangeType

from src.core.config import settings
from src.graph_models import News, NewsType
from src.services.telegram_parser.antispam import AntiSpamFilter
from src.utils.text_utils import calculate_content_hash, detect_language

logger = logging.getLogger(__name__)


class NewsTriggerService:
    """
    Real-time триггер для Telegram новостей
    Согласно Project Charter: детект -> нормализация -> RabbitMQ
    """
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.rabbit_connection = None
        self.rabbit_channel = None
        self.exchange = None
        self.anti_spam = AntiSpamFilter()
        self.running = False
        
        # Kafka topics согласно архитектуре
        self.topics = {
            "raw": "news.raw",
            "normalized": "news.norm",
            "scored": "news.scored",
            "alerts": "alerts"
        }
    
    async def start(self):
        """Запуск real-time мониторинга"""
        try:
            # Инициализация Telegram клиента
            await self._init_telegram()
            
            # Инициализация RabbitMQ
            await self._init_rabbitmq()
            
            # Регистрация обработчиков
            await self._setup_handlers()
            
            self.running = True
            logger.info("News trigger service started")
            
            # Держим сервис активным
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to start trigger service: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """Остановка сервиса"""
        self.running = False
        
        if self.client:
            await self.client.disconnect()
        
        if self.rabbit_connection:
            await self.rabbit_connection.close()
        
        logger.info("News trigger service stopped")
    
    async def _init_telegram(self):
        """Инициализация Telegram клиента"""
        self.client = TelegramClient(
            f"sessions/{settings.TELETHON_SESSION_NAME}_trigger",
            settings.TELETHON_API_ID,
            settings.TELETHON_API_HASH
        )
        await self.client.start(phone=settings.TELETHON_PHONE)
        logger.info("Telegram client initialized for trigger service")
    
    async def _init_rabbitmq(self):
        """Инициализация RabbitMQ"""
        self.rabbit_connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            client_properties={
                "connection_name": "news-trigger",
                "product": "radar-ai"
            }
        )
        
        self.rabbit_channel = await self.rabbit_connection.channel()
        await self.rabbit_channel.set_qos(prefetch_count=10)
        
        # Создаем exchange для новостей
        self.exchange = await self.rabbit_channel.declare_exchange(
            "radar.news",
            type=ExchangeType.TOPIC,
            durable=True
        )
        
        logger.info("RabbitMQ initialized for trigger service")
    
    async def _setup_handlers(self):
        """Настройка обработчиков новых сообщений"""
        
        # Получаем whitelist каналов из конфига
        whitelist_channels = await self._get_whitelisted_channels()
        
        @self.client.on(events.NewMessage(chats=whitelist_channels))
        async def handle_new_message(event):
            """Обработчик новых сообщений"""
            try:
                # SLA: 2-5 минут от детекта до алерта
                start_time = datetime.utcnow()
                
                message = event.message
                chat = await event.get_chat()
                
                logger.info(f"New message detected from {chat.title}: {message.text[:50]}...")
                
                # Быстрая проверка на спам
                is_ad, ad_score, _ = await self.anti_spam.check_message(
                    message, 
                    trust_level=9  # Whitelist = высокий trust
                )
                
                if is_ad and ad_score > 10:  # Очень высокий порог для whitelist
                    logger.debug(f"Message filtered as ad (score: {ad_score})")
                    return
                
                # Создаем событие для RabbitMQ
                news_event = await self._create_news_event(message, chat)
                
                # Публикуем в топик news.raw
                await self._publish_to_rabbit(
                    self.topics["raw"],
                    news_event
                )
                
                # Логируем время обработки
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                logger.info(f"Message processed in {processing_time:.2f}s")
                
            except Exception as e:
                logger.error(f"Error handling message: {e}")
        
        logger.info(f"Registered handler for {len(whitelist_channels)} channels")
    
    async def _get_whitelisted_channels(self):
        """Получить whitelist каналов из конфига"""
        # В реальности - из БД или конфига
        # Здесь - примерный список финансовых каналов
        return [
            "@interfaxonline",
            "@rbc_news",
            "@vedomosti",
            "@kommersant",
            "@tass_agency",
            "@forbes_russia",
            "@bloombergru",
            "@reuters_ru",
            "@cbonds_news",
            "@moex_official"
        ]
    
    async def _create_news_event(self, message: Message, chat) -> Dict[str, Any]:
        """Создать событие новости для публикации"""
        
        # Генерируем ID на основе URL
        message_url = f"https://t.me/{chat.username}/{message.id}" if chat.username else f"tg://message?id={message.id}"
        news_id = News.generate_id(message_url)
        
        # Определяем язык
        text = message.text or message.message or ""
        lang = detect_language(text)
        
        # Базовое событие
        event = {
            "id": news_id,
            "url": message_url,
            "title": self._extract_title(text),
            "text": text,
            "lang_orig": lang,
            "lang_norm": "ru",  # Будет нормализован в следующем сервисе
            "published_at": message.date.isoformat(),
            "source": f"telegram:{chat.username or chat.id}",
            "source_name": chat.title,
            "channel_id": chat.id,
            "message_id": message.id,
            "has_media": message.media is not None,
            "detected_at": datetime.utcnow().isoformat(),
            "content_hash": calculate_content_hash("", text)
        }
        
        # Добавляем метаданные если есть
        if message.views:
            event["views"] = message.views
        if message.forwards:
            event["forwards"] = message.forwards
        
        return event
    
    def _extract_title(self, text: str, max_length: int = 100) -> str:
        """Извлечь заголовок из текста"""
        if not text:
            return "Без заголовка"
        
        # Берем первую строку или первые N символов
        lines = text.split('\n')
        title = lines[0] if lines else text
        
        if len(title) > max_length:
            title = title[:max_length-3] + "..."
        
        return title.strip()
    
    async def _publish_to_rabbit(self, topic: str, event: Dict[str, Any]):
        """Публикация события в RabbitMQ"""
        
        message_body = json.dumps(event, ensure_ascii=False)
        
        message = AMQPMessage(
            body=message_body.encode('utf-8'),
            content_type="application/json",
            delivery_mode=2,  # Persistent
            message_id=event["id"],
            timestamp=datetime.utcnow(),
            headers={
                "source": event["source"],
                "lang": event["lang_orig"],
                "has_media": event.get("has_media", False)
            }
        )
        
        # Routing key в формате news.raw.telegram
        routing_key = f"{topic}.telegram"
        
        await self.exchange.publish(
            message,
            routing_key=routing_key
        )
        
        logger.debug(f"Published event {event['id']} to {routing_key}")

