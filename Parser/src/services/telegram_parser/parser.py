# src/services/telegram_parser/parser.py

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from uuid import uuid4

from telethon import TelegramClient
from telethon.tl.types import Message, MessageMediaPhoto, MessageMediaDocument
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.core.models import Source, News, Image, ParserState, OutboxEvent
from src.services.telegram_parser.antispam import AntiSpamFilter
from src.services.storage.news_repository import NewsRepository
from src.services.storage.image_service import ImageService
from src.services.enricher.enrichment_service import EnrichmentService

logger = logging.getLogger(__name__)


class TelegramParser:
    def __init__(
        self,
        client: TelegramClient,
        db_session: AsyncSession,
        anti_spam: Optional[AntiSpamFilter] = None,
        enricher: Optional[EnrichmentService] = None
    ):
        self.client = client
        self.session = db_session
        self.anti_spam = anti_spam or AntiSpamFilter()
        self.news_repo = NewsRepository(db_session)
        self.image_service = ImageService(db_session)
        # Используем переданный enricher или создаем новый
        self.enricher = enricher or EnrichmentService(db_session)

        # Статистика CEG (если есть ceg_service)
        self.ceg_stats = {
            "events_created": 0,
            "causal_links_created": 0,
            "impacts_calculated": 0,
            "retroactive_updates": 0
        }

    async def parse_channel(
        self,
        source: Source,
        backfill: bool = False,
        limit: Optional[int] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Parse messages from a Telegram channel

        Args:
            source: Source model instance
            backfill: If True, fetch historical messages (up to 1 year)
            limit: Maximum number of messages to fetch

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_messages": 0,
            "saved_news": 0,
            "ads_filtered": 0,
            "duplicates": 0,
            "errors": 0
        }

        try:
            # Get or create parser state
            parser_state = await self._get_or_create_parser_state(source)

            # Determine date range
            if backfill and not parser_state.backfill_completed:
                # Backfill from specified number of days ago
                min_date = datetime.now(timezone.utc) - timedelta(days=days)
                offset_id = 0
                logger.info(f"Backfill mode: loading messages from {min_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            else:
                # Get new messages since last parse
                min_date = parser_state.last_parsed_at or datetime.now(timezone.utc)
                offset_id = int(parser_state.last_external_id) if parser_state.last_external_id else 0

            # Fetch messages
            try:
                channel = await self.client.get_entity(source.tg_chat_id)
                logger.info(f"Channel entity: {channel}")
                
                # Проверяем доступность канала
                if hasattr(channel, 'left') and channel.left:
                    logger.warning(f"Channel {source.code} is left by user")
                if hasattr(channel, 'restricted') and channel.restricted:
                    logger.warning(f"Channel {source.code} is restricted")
                if hasattr(channel, 'stories_unavailable') and channel.stories_unavailable:
                    logger.info(f"Channel {source.code} stories are unavailable")
                    
            except Exception as e:
                logger.error(f"Failed to get entity for {source.tg_chat_id}: {e}")
                stats["errors"] += 1
                return stats

            # Подготавливаем параметры для iter_messages
            iter_params = {
                'limit': limit or 100,
                'offset_id': offset_id,
            }
            
            # Добавляем параметры даты в зависимости от режима
            if backfill:
                # Для backfill используем min_date как минимальную дату
                iter_params['min_id'] = 0  # Начинаем с самого начала
                iter_params['max_id'] = 0  # До текущего момента
                # Не используем offset_date для backfill, так как это ограничивает поиск
                logger.info(f"Backfill params: min_id=0, max_id=0, limit={iter_params['limit']}")
            elif not backfill and min_date:
                # Для real-time используем offset_date
                iter_params['offset_date'] = min_date
                logger.info(f"Real-time params: offset_date={min_date}")
            
            logger.info(f"iter_messages params: {iter_params}")
            
            message_count = 0
            async for message in self.client.iter_messages(channel, **iter_params):
                message_count += 1
                stats["total_messages"] += 1
                
                # Логируем первые несколько сообщений для отладки
                if message_count <= 3:
                    logger.info(f"Message {message_count}: ID={message.id}, Date={message.date}, Text={message.text[:100] if message.text else 'No text'}...")

                # Process message
                try:
                    saved = await self._process_message(message, source)
                    if saved:
                        stats["saved_news"] += 1
                    elif saved is False:
                        stats["ads_filtered"] += 1
                    else:
                        stats["duplicates"] += 1

                    # Update parser state
                    parser_state.last_external_id = str(message.id)
                    parser_state.last_parsed_at = message.date

                except Exception as e:
                    logger.error(f"Error processing message {message.id}: {e}")
                    stats["errors"] += 1

                # Commit periodically
                if stats["total_messages"] % 100 == 0:
                    await self.session.commit()
                    logger.info(f"Processed {stats['total_messages']} messages from {source.code}")
            
            logger.info(f"Finished iterating messages. Total found: {message_count}")

            # Update parser state
            if backfill:
                parser_state.backfill_completed = True
                parser_state.backfill_completed_at = datetime.now(timezone.utc)

            await self.session.commit()

        except Exception as e:
            logger.error(f"Error parsing channel {source.code}: {e}")
            await self.session.rollback()
            raise

        # Добавляем CEG статистику если есть
        if self.enricher and hasattr(self.enricher, 'ceg_service') and self.enricher.ceg_service:
            stats["ceg_stats"] = self.enricher.ceg_service.get_stats()

        return stats

    async def _process_message(self, message: Message, source: Source) -> Optional[bool]:
        """
        Process a single message

        Returns:
            True if saved, False if filtered as ad, None if duplicate
        """
        # Skip empty messages
        if not message.text and not message.message:
            return None

        # Check for ads/spam
        is_ad, ad_score, ad_reasons = await self.anti_spam.check_message(
            message,
            source.trust_level
        )

        if is_ad:
            logger.info(f"Message {message.id} filtered as ad (score: {ad_score}): {ad_reasons}")
            return False

        # Check for duplicate
        external_id = f"tg_{source.tg_chat_id}_{message.id}"
        existing = await self.session.execute(
            select(News).where(
                and_(
                    News.source_id == source.id,
                    News.external_id == external_id
                )
            )
        )
        if existing.scalar_one_or_none():
            return None

        # Extract text
        text = message.text or message.message or ""
        title = self._extract_title(text)

        # Calculate content hash for deduplication
        content_hash = hashlib.sha256(f"{title}{text}".encode()).hexdigest()

        # Check for duplicate by content hash
        duplicate = await self.session.execute(
            select(News).where(News.hash_content == content_hash)
        )
        if duplicate.scalar_one_or_none():
            logger.debug(f"Duplicate content found for message {message.id}")
            return None

        # Create news entry
        news = News(
            id=uuid4(),
            source_id=source.id,
            external_id=external_id,
            url=f"https://t.me/{source.tg_chat_id}/{message.id}",
            title=title,
            text_plain=text,
            text_html=None,  # Telegram doesn't provide HTML
            published_at=message.date,
            hash_content=content_hash,
            is_ad=False,
            ad_score=ad_score,
            ad_reasons=ad_reasons if ad_reasons else None,
            metadata={
                "message_id": message.id,
                "views": message.views,
                "forwards": message.forwards,
                "replies": message.replies.replies if message.replies else 0,
            }
        )

        self.session.add(news)

        # Process media/images
        if message.media:
            await self._process_media(message, news)

        # Обогащение новости (NER, классификация, связывание с компаниями)
        try:
            logger.info(f"Starting enrichment for news {news.id}")
            enrichment_result = await self.enricher.enrich_news(news)
            logger.info(f"Enrichment completed for news {news.id}: {enrichment_result}")
        except Exception as e:
            logger.error(f"Enrichment failed for news {news.id}: {e}")

        # Create outbox event
        outbox_event = OutboxEvent(
            id=uuid4(),
            event_type="news.created",
            aggregate_id=news.id,
            payload_json={
                "event_id": str(uuid4()),
                "type": "news.created",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "news": {
                    "id": str(news.id),
                    "source": source.code,
                    "external_id": external_id,
                    "url": news.url,
                    "title": news.title,
                    "published_at": news.published_at.isoformat(),
                    "has_images": bool(message.media)
                }
            },
            status="pending"
        )

        self.session.add(outbox_event)

        return True

    async def _process_media(self, message: Message, news: News):
        """Process and save message media"""
        try:
            if isinstance(message.media, MessageMediaPhoto):
                # Download photo
                photo_bytes = await self.client.download_media(message.media, bytes)
                if photo_bytes:
                    image = await self.image_service.save_image(
                        photo_bytes,
                        mime_type="image/jpeg",
                        news_id=news.id
                    )
                    if image:
                        news.images.append(image)

            elif isinstance(message.media, MessageMediaDocument):
                # Check if it's an image
                if message.media.document.mime_type.startswith('image/'):
                    doc_bytes = await self.client.download_media(message.media, bytes)
                    if doc_bytes:
                        image = await self.image_service.save_image(
                            doc_bytes,
                            mime_type=message.media.document.mime_type,
                            news_id=news.id
                        )
                        if image:
                            news.images.append(image)

        except Exception as e:
            logger.error(f"Error processing media for message {message.id}: {e}")

    def _extract_title(self, text: str, max_length: int = 200) -> str:
        """Extract title from message text"""
        if not text:
            return "Без заголовка"

        # Take first line or first N characters
        lines = text.split('\n')
        title = lines[0] if lines else text

        if len(title) > max_length:
            title = title[:max_length-3] + "..."

        return title.strip()

    async def _get_or_create_parser_state(self, source: Source) -> ParserState:
        """Get or create parser state for source"""
        result = await self.session.execute(
            select(ParserState).where(ParserState.source_id == source.id)
        )
        state = result.scalar_one_or_none()

        if not state:
            state = ParserState(
                id=uuid4(),
                source_id=source.id,
                backfill_started_at=datetime.now(timezone.utc)
            )
            self.session.add(state)

        return state