# workers/html_parser_worker.py
"""
HTML Parser Worker - Парсинг новостей с HTML сайтов (Forbes, Interfax, MOEX и др.)
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Добавляем корень проекта в PATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database.config import settings
from core.database.database import init_db, close_db, get_db_session
from services.aggregator.html.html_parser_service import HTMLParserService
from core.utils.logging import setup_logging

logger = logging.getLogger(__name__)


class HTMLParserWorker:
    """Воркер для HTML парсеров"""

    def __init__(self, max_articles_per_source: int = 50, use_local_ai: bool = False):
        self.max_articles_per_source = max_articles_per_source
        self.use_local_ai = use_local_ai
        self.running = False
        self.service = None

    async def start(self):
        """Запуск воркера"""
        logger.info("Starting HTML parser worker")

        try:
            # Инициализация БД
            await init_db()

            async with get_db_session() as session:
                # Создаем сервис парсеров
                self.service = HTMLParserService(
                    db_session=session,
                    use_local_ai=self.use_local_ai
                )

                self.running = True
                logger.info(f"HTML parser service initialized (local_ai={self.use_local_ai})")

                # Запускаем парсинг
                stats = await self.service.start_parsing(self.max_articles_per_source)

                logger.info("HTML parsing completed:")
                logger.info(f"  Sources processed: {stats['sources_processed']}")
                logger.info(f"  Total articles processed: {stats['total_articles_processed']}")
                logger.info(f"  Total articles saved: {stats['total_articles_saved']}")
                logger.info(f"  Total errors: {stats['total_errors']}")

                # Детальная статистика по парсерам
                for parser_code, parser_stats in stats['parser_stats'].items():
                    logger.info(f"  {parser_code}: {parser_stats}")

        except Exception as e:
            logger.error(f"Error in HTML parser worker: {e}", exc_info=True)
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Остановка воркера"""
        self.running = False
        await close_db()
        logger.info("HTML parser worker stopped")

    async def parse_specific_source(self, source_code: str, max_articles: int = 50):
        """Парсить конкретный источник"""
        logger.info(f"Parsing specific source: {source_code}")

        try:
            await init_db()

            async with get_db_session() as session:
                service = HTMLParserService(session, use_local_ai=self.use_local_ai)
                stats = await service.parse_specific_source(source_code, max_articles)

                if 'error' in stats:
                    logger.error(f"Error parsing {source_code}: {stats['error']}")
                else:
                    logger.info(f"Parsed {source_code}: {stats}")

                return stats

        except Exception as e:
            logger.error(f"Error parsing source {source_code}: {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            await close_db()


# Глобальная переменная для signal handler
html_parser_worker: HTMLParserWorker = None


def signal_handler(signum, frame):
    """Обработка сигналов остановки"""
    logger.info(f"Received signal {signum}")
    if html_parser_worker:
        asyncio.create_task(html_parser_worker.stop())
    sys.exit(0)


async def main():
    """Основная функция"""
    global html_parser_worker

    import argparse

    parser = argparse.ArgumentParser(description="HTML Parser Worker")
    parser.add_argument(
        '--source',
        type=str,
        help='Parse specific source (forbes, interfax)'
    )
    parser.add_argument(
        '--max-articles',
        type=int,
        default=50,
        help='Max articles per source'
    )
    parser.add_argument(
        '--local-ai',
        action='store_true',
        help='Use local AI instead of OpenAI API'
    )

    args = parser.parse_args()

    setup_logging()
    logger.info("=" * 60)
    logger.info("Starting HTML Parser Worker")
    logger.info("=" * 60)

    # Настройка обработки сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    html_parser_worker = HTMLParserWorker(
        max_articles_per_source=args.max_articles,
        use_local_ai=args.local_ai
    )

    try:
        if args.source:
            # Парсим конкретный источник
            await html_parser_worker.parse_specific_source(args.source, args.max_articles)
        else:
            # Парсим все источники
            await html_parser_worker.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await html_parser_worker.stop()


if __name__ == "__main__":
    # Проверка настроек
    if not hasattr(settings, 'DATABASE_URL') or not settings.DATABASE_URL:
        logger.error("DATABASE_URL not configured in settings")
        sys.exit(1)

    logger.info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")

    # Запуск
    asyncio.run(main())
