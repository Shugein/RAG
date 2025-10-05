# scripts/start_html_parser.py
"""
Скрипт для запуска HTML парсеров (Forbes, Interfax и др.)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from Parser.src.core.database import init_db, close_db, get_db_session
from Parser.src.services.html_parser.html_parser_service import HTMLParserService
from Parser.src.core.config import settings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/html_parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

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
            logger.error(f"Error in HTML parser worker: {e}")
            raise
        finally:
            await close_db()

    async def stop(self):
        """Остановка воркера"""
        self.running = False
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
            logger.error(f"Error parsing source {source_code}: {e}")
            return {"error": str(e)}
        finally:
            await close_db()


async def main():
    """Основная функция"""
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
    
    worker = HTMLParserWorker(
        max_articles_per_source=args.max_articles,
        use_local_ai=args.local_ai
    )
    
    try:
        if args.source:
            # Парсим конкретный источник
            await worker.parse_specific_source(args.source, args.max_articles)
        else:
            # Парсим все источники
            await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
