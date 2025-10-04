# src/services/storage/image_service.py
"""
Сервис для работы с изображениями
"""

import logging
import hashlib
from io import BytesIO
from typing import Optional, Tuple
from uuid import UUID, uuid4

from PIL import Image as PILImage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.models import Image
from src.core.config import settings

logger = logging.getLogger(__name__)


class ImageService:
    """Сервис для сохранения и обработки изображений"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def save_image(
        self,
        image_bytes: bytes,
        mime_type: str,
        news_id: Optional[UUID] = None,
        create_thumbnail: bool = True
    ) -> Optional[Image]:
        """
        Сохранение изображения с дедупликацией
        
        Args:
            image_bytes: Байты изображения
            mime_type: MIME тип
            news_id: ID новости (опционально)
            create_thumbnail: Создавать ли превью
            
        Returns:
            Объект Image или None при ошибке
        """
        try:
            # Проверяем размер
            size_mb = len(image_bytes) / (1024 * 1024)
            if size_mb > settings.IMAGE_MAX_SIZE_MB:
                logger.warning(f"Image too large: {size_mb:.2f} MB")
                return None
            
            # Проверяем MIME тип
            if mime_type not in settings.IMAGE_ALLOWED_TYPES:
                logger.warning(f"Invalid image type: {mime_type}")
                return None
            
            # Вычисляем SHA-256 для дедупликации
            sha256 = hashlib.sha256(image_bytes).hexdigest()
            
            # Проверяем, существует ли уже
            result = await self.session.execute(
                select(Image).where(Image.sha256 == sha256)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.debug(f"Image already exists: {sha256}")
                return existing
            
            # Получаем размеры изображения
            width, height = self._get_image_dimensions(image_bytes)
            
            # Создаем thumbnail если нужно
            thumbnail = None
            if create_thumbnail and width and height:
                thumbnail = self._create_thumbnail(image_bytes)
            
            # Сохраняем в БД
            image = Image(
                id=uuid4(),
                sha256=sha256,
                mime_type=mime_type,
                bytes=image_bytes,
                width=width,
                height=height,
                file_size=len(image_bytes),
                thumbnail=thumbnail
            )
            
            self.session.add(image)
            
            logger.info(f"Saved image: {sha256[:8]}... ({size_mb:.2f} MB)")
            return image
            
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            return None
    
    def _get_image_dimensions(self, image_bytes: bytes) -> Tuple[Optional[int], Optional[int]]:
        """Получить размеры изображения"""
        try:
            with PILImage.open(BytesIO(image_bytes)) as img:
                return img.size
        except Exception as e:
            logger.error(f"Failed to get image dimensions: {e}")
            return None, None
    
    def _create_thumbnail(self, image_bytes: bytes) -> Optional[bytes]:
        """Создать превью изображения"""
        try:
            with PILImage.open(BytesIO(image_bytes)) as img:
                # Конвертируем в RGB если нужно
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                
                # Создаем thumbnail
                img.thumbnail(settings.IMAGE_THUMBNAIL_SIZE, PILImage.Resampling.LANCZOS)
                
                # Сохраняем в байты
                output = BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                return output.getvalue()
                
        except Exception as e:
            logger.error(f"Failed to create thumbnail: {e}")
            return None
    
    async def get_by_sha256(self, sha256: str) -> Optional[Image]:
        """Получить изображение по хешу"""
        result = await self.session.execute(
            select(Image).where(Image.sha256 == sha256)
        )
        return result.scalar_one_or_none()
    
    async def cleanup_orphaned(self):
        """Удалить изображения без связей с новостями"""
        # TODO: Реализовать очистку неиспользуемых изображений
        pass