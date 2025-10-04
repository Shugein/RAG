# src/api/endpoints/jobs.py
"""
Background jobs endpoints
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.database import get_db, get_db_session
from src.core.config import settings
from src.core.models import Source, ParserState
from src.api.schemas import BackfillRequest, JobResponse
from src.services.telegram_parser.client import TelegramClientManager
from src.services.telegram_parser.parser import TelegramParser
from src.services.telegram_parser.antispam import AntiSpamFilter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/backfill", response_model=JobResponse)
async def start_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
) -> JobResponse:
    """Запустить backfill для источников"""
    
    # Проверяем источник если указан
    if request.source_code:
        result = await db.execute(
            select(Source).where(
                Source.code == request.source_code,
                Source.enabled == True
            )
        )
        source = result.scalar_one_or_none()
        
        if not source:
            raise HTTPException(404, f"Source {request.source_code} not found or disabled")
    
    # Создаем задачу
    job_id = str(uuid4())
    
    # Добавляем в background
    background_tasks.add_task(
        run_backfill,
        job_id=job_id,
        source_code=request.source_code,
        days_back=request.days_back,
        limit=request.limit
    )
    
    return JobResponse(
        job_id=job_id,
        status="started",
        message=f"Backfill started for {request.days_back} days",
        created_at=datetime.utcnow()
    )


async def run_backfill(
    job_id: str,
    source_code: Optional[str],
    days_back: int,
    limit: Optional[int]
):
    """Выполнение backfill в фоне"""
    logger.info(f"Starting backfill job {job_id} for source={source_code}, days_back={days_back}, limit={limit}")
    
    client_manager = None
    client = None
    
    try:
        # Initialize Telegram client
        if not settings.ENABLE_TELEGRAM:
            logger.warning("Telegram parsing is disabled")
            return
        
        client_manager = TelegramClientManager()
        client = await client_manager.initialize()
        logger.info(f"Telegram client initialized for job {job_id}")
        
        # Load anti-spam filter
        ad_rules_path = Path("config/ad_rules.yml")
        anti_spam = AntiSpamFilter(ad_rules_path) if ad_rules_path.exists() else AntiSpamFilter()
        
        # Get database session
        async with get_db_session() as session:
            # Get sources to process
            query = select(Source).where(Source.kind == "telegram", Source.enabled == True)
            
            if source_code:
                query = query.where(Source.code == source_code)
            
            result = await session.execute(query)
            sources = result.scalars().all()
            
            if not sources:
                logger.warning(f"No active Telegram sources found for job {job_id}")
                return
            
            logger.info(f"Found {len(sources)} source(s) to process for job {job_id}")
            
            # Process each source
            for source in sources:
                source_code = source.code  # Cache source code to avoid lazy loading issues
                try:
                    logger.info(f"Processing source {source_code} (job {job_id})")
                    
                    # Create parser for this source
                    parser = TelegramParser(
                        client=client,
                        db_session=session,
                        anti_spam=anti_spam
                    )
                    
                    # Update parser state to track backfill start
                    # Note: parser state will be managed inside the parse function
                    
                    # Run backfill with custom days_back
                    # Temporarily adjust min_date based on days_back parameter
                    stats = await _parse_with_custom_days(
                        parser=parser,
                        source=source,
                        days_back=days_back,
                        limit=limit
                    )
                    
                    logger.info(
                        f"Backfill completed for {source_code} (job {job_id}): "
                        f"{stats['saved_news']} news saved, "
                        f"{stats['ads_filtered']} ads filtered, "
                        f"{stats['duplicates']} duplicates, "
                        f"{stats['errors']} errors"
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing source {source_code} in job {job_id}: {e}", exc_info=True)
                    continue
        
        logger.info(f"Backfill job {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Backfill job {job_id} failed: {e}", exc_info=True)
        raise
    
    finally:
        # Cleanup
        if client_manager:
            try:
                await client_manager.disconnect()
                logger.info(f"Telegram client disconnected for job {job_id}")
            except Exception as e:
                logger.error(f"Error disconnecting client for job {job_id}: {e}")


async def _get_or_create_parser_state(session: AsyncSession, source: Source) -> ParserState:
    """Get or create parser state for source"""
    result = await session.execute(
        select(ParserState).where(ParserState.source_id == source.id)
    )
    state = result.scalar_one_or_none()
    
    if not state:
        state = ParserState(
            id=uuid4(),
            source_id=source.id,
            backfill_started_at=datetime.now(timezone.utc)
        )
        session.add(state)
        await session.flush()  # Flush immediately to avoid duplicate inserts
    
    return state


async def _parse_with_custom_days(
    parser: TelegramParser,
    source: Source,
    days_back: int,
    limit: Optional[int]
) -> dict:
    """
    Parse channel with custom days_back parameter
    Similar to parser.parse_channel but with custom date range
    """
    from datetime import datetime, timedelta, timezone
    from telethon.tl.types import Message
    
    stats = {
        "total_messages": 0,
        "saved_news": 0,
        "ads_filtered": 0,
        "duplicates": 0,
        "errors": 0
    }
    
    source_code = source.code  # Cache to avoid lazy loading issues
    source_tg_chat_id = source.tg_chat_id  # Cache to avoid lazy loading issues
    
    try:
        # Get parser state
        parser_state = await _get_or_create_parser_state(parser.session, source)
        
        # Calculate date range
        min_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        max_date = datetime.now(timezone.utc)
        
        logger.info(f"Fetching messages from {source_code} between {min_date} and {max_date}")
        
        # Fetch messages from Telegram
        try:
            channel = await parser.client.get_entity(source_tg_chat_id)
        except ValueError as e:
            # Handle invalid username/chat_id
            if "No user has" in str(e) or "username" in str(e).lower():
                logger.error(
                    f"Invalid Telegram channel for {source_code}: {source_tg_chat_id}. "
                    f"Please verify the channel exists and is accessible. Error: {e}"
                )
                raise ValueError(
                    f"Telegram channel '{source_tg_chat_id}' not found or not accessible. "
                    f"Please check the channel name in config/sources.yml"
                ) from e
            raise
        except Exception as e:
            logger.error(f"Error getting Telegram entity {source_tg_chat_id}: {e}")
            raise
        
        logger.info(f"Fetching up to {limit} messages from channel {source_tg_chat_id}")
        
        async for message in parser.client.iter_messages(
            channel,
            limit=limit
        ):
            # Check if message is within our date range
            if message.date < min_date:
                logger.debug(f"Message {message.id} is older than min_date, stopping")
                break
            
            if message.date > max_date:
                logger.debug(f"Message {message.id} is newer than max_date, skipping")
                continue
            
            stats["total_messages"] += 1
            
            # Process message using parser's method
            try:
                saved = await parser._process_message(message, source)
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
            if stats["total_messages"] % 50 == 0:
                await parser.session.commit()
                logger.info(f"Processed {stats['total_messages']} messages from {source_code}")
        
        # Final commit
        await parser.session.commit()
        
    except Exception as e:
        logger.error(f"Error in backfill for {source_code}: {e}")
        await parser.session.rollback()
        raise
    
    return stats