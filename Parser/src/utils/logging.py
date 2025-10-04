# src/utils/logging.py
"""
Настройка логирования для всего приложения
"""

import logging
import sys
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import structlog
from src.core.config import settings


def setup_logging():
    """Настройка структурированного логирования"""
    
    # Создаем директорию для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Определяем уровень логирования
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Создаем файловые хендлеры
    file_handler = logging.FileHandler(
        log_dir / f"news_parser_{datetime.now().strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    
    # Создаем консольный хендлер
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Настройка форматирования
    if settings.LOG_FORMAT == "json":
        # JSON формат для production
        file_formatter = logging.Formatter('%(message)s')
        console_formatter = logging.Formatter('%(message)s')
        
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Человеко-читаемый формат для разработки
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter('%(message)s')
        
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    
    # Настройка стандартного логгера Python
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Очищаем существующие хендлеры
    root_logger.handlers.clear()
    
    # Добавляем хендлеры
    file_handler.setFormatter(file_formatter)
    console_handler.setFormatter(console_formatter)
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Отключаем лишние логи от библиотек
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Включаем SQL логи только в DEBUG режиме
    if settings.DEBUG:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    
    # Логируем информацию о запуске
    logger = structlog.get_logger()
    logger.info("Logging initialized", 
                log_file=str(file_handler.baseFilename),
                log_level=settings.LOG_LEVEL)
    
    return logger