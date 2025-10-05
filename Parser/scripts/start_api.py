# scripts/start_api.py
"""
Скрипт запуска REST API сервера
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корень проекта в PATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from Parser.src.core.config import settings
from Parser.src.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def main():
    """Запуск FastAPI сервера"""
    setup_logging()
    logger.info("Starting News Aggregator API")
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "formatter": "json" if settings.LOG_FORMAT == "json" else "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout"
                }
            },
            "root": {
                "level": settings.LOG_LEVEL,
                "handlers": ["default"]
            }
        }
    )


if __name__ == "__main__":
    main()