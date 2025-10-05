# ================================================================
# scripts/start_enricher.py
"""
Скрипт запуска сервиса обогащения
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from Parser.src.core.config import settings
from Parser.src.core.database import init_db, close_db, get_db_session
from Parser.src.services.enricher.enrichment_service import EnrichmentService
from Parser.src.utils.logging import setup_logging
from Parser.src.core.models import News, Entity, LinkedCompany, Topic
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class EnricherWorker:
    def __init__(self):
        self.running = False
        self.enricher = None
    
    async def start(self):
        """Запуск воркера обогащения"""
        try:
            await init_db()
            self.running = True
            
            while self.running:
                # Обрабатываем необогащенные новости
                await self._process_batch()
                
                # Ждем перед следующей итерацией
                await asyncio.sleep(5)
                
        except Exception as e:
            logger.error(f"Enricher error: {e}")
        finally:
            await self.stop()
    
    async def _process_batch(self):
        """Обработка батча новостей"""
        async with get_db_session() as session:
            # Получаем необогащенные новости
            result = await session.execute(
                select(News)
                .outerjoin(Entity)
                .where(Entity.id.is_(None))
                .limit(settings.ENRICHER_BATCH_SIZE)
            )
            news_items = result.scalars().all()
            
            if not news_items:
                return
            
            logger.info(f"Processing {len(news_items)} news for enrichment")
            
            # Создаем сервис обогащения
            enricher = EnrichmentService(session)
            
            for news in news_items:
                try:
                    await enricher.enrich_news(news)
                    await session.commit()
                    logger.debug(f"Enriched news {news.id}")
                except Exception as e:
                    logger.error(f"Failed to enrich news {news.id}: {e}")
                    await session.rollback()
    
    async def stop(self):
        """Остановка воркера"""
        self.running = False
        await close_db()
        logger.info("Enricher stopped")


async def main():
    setup_logging()
    logger.info("Starting Enricher Service")
    
    worker = EnricherWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())

