# services/aggregator/storage/__init__.py
"""
Storage module for aggregator services
"""

from .news_repository import NewsRepository
from .image_service import ImageService

__all__ = ['NewsRepository', 'ImageService']
