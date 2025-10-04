
"""
Репозиторий для работы с новостями
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from src.core.models import News, Source, Image, Entity, LinkedCompany, Topic

logger = logging.getLogger(__name__)


class NewsRepository:
    """Репозиторий для CRUD операций с новостями"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, news_id: UUID) -> Optional[News]:
        """Получить новость по ID"""
        result = await self.session.execute(
            select(News)
            .options(
                selectinload(News.source),
                selectinload(News.images),
                selectinload(News.entities),
                selectinload(News.linked_companies),
                selectinload(News.topics)
            )
            .where(News.id == news_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_external_id(self, source_id: UUID, external_id: str) -> Optional[News]:
        """Получить новость по внешнему ID"""
        result = await self.session.execute(
            select(News).where(
                and_(
                    News.source_id == source_id,
                    News.external_id == external_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_hash(self, content_hash: str) -> Optional[News]:
        """Получить новость по хешу контента (для дедупликации)"""
        result = await self.session.execute(
            select(News).where(News.hash_content == content_hash)
        )
        return result.scalar_one_or_none()
    
    async def search(
        self,
        query: Optional[str] = None,
        source_code: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        ticker: Optional[str] = None,
        topic: Optional[str] = None,
        exclude_ads: bool = True,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[News], int]:
        """
        Поиск новостей с фильтрами
        
        Returns:
            Tuple (список новостей, общее количество)
        """
        # Базовый запрос
        stmt = select(News).options(
            selectinload(News.source)
        )
        
        # Фильтры
        filters = []
        
        if exclude_ads:
            filters.append(News.is_ad == False)
        
        if source_code:
            stmt = stmt.join(Source)
            filters.append(Source.code == source_code)
        
        if date_from:
            filters.append(News.published_at >= date_from)
        
        if date_to:
            filters.append(News.published_at <= date_to)
        
        if query:
            # Полнотекстовый поиск
            search_filter = or_(
                News.title.ilike(f"%{query}%"),
                News.text_plain.ilike(f"%{query}%")
            )
            filters.append(search_filter)
        
        if ticker:
            stmt = stmt.join(LinkedCompany)
            filters.append(LinkedCompany.secid == ticker.upper())
        
        if topic:
            stmt = stmt.join(Topic)
            filters.append(Topic.topic == topic)
        
        # Применяем фильтры
        if filters:
            stmt = stmt.where(and_(*filters))
        
        # Получаем общее количество
        count_stmt = select(func.count()).select_from(News)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar()
        
        # Сортировка и пагинация
        stmt = stmt.order_by(desc(News.published_at))
        stmt = stmt.limit(limit).offset(offset)
        
        # Выполняем запрос
        result = await self.session.execute(stmt)
        news_list = result.scalars().unique().all()
        
        return news_list, total
    
    async def get_latest(
        self,
        source_id: Optional[UUID] = None,
        limit: int = 10
    ) -> List[News]:
        """Получить последние новости"""
        stmt = select(News).options(
            selectinload(News.source),
            selectinload(News.images)
        )
        
        if source_id:
            stmt = stmt.where(News.source_id == source_id)
        
        stmt = stmt.where(News.is_ad == False)
        stmt = stmt.order_by(desc(News.published_at))
        stmt = stmt.limit(limit)
        
        result = await self.session.execute(stmt)
        return result.scalars().unique().all()
    
    async def get_statistics(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Получить статистику по новостям"""
        
        # Базовые фильтры
        filters = []
        if date_from:
            filters.append(News.published_at >= date_from)
        if date_to:
            filters.append(News.published_at <= date_to)
        
        # Общее количество
        count_stmt = select(func.count(News.id))
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        
        total_result = await self.session.execute(count_stmt)
        total_count = total_result.scalar()
        
        # Количество по источникам
        sources_stmt = (
            select(
                Source.code,
                Source.name,
                func.count(News.id).label('count')
            )
            .join(News)
            .group_by(Source.id, Source.code, Source.name)
        )
        
        if filters:
            sources_stmt = sources_stmt.where(and_(*filters))
        
        sources_result = await self.session.execute(sources_stmt)
        sources_stats = [
            {"source": row.code, "name": row.name, "count": row.count}
            for row in sources_result
        ]
        
        # Количество рекламы
        ads_stmt = select(func.count(News.id)).where(News.is_ad == True)
        if filters:
            ads_stmt = ads_stmt.where(and_(*filters))
        
        ads_result = await self.session.execute(ads_stmt)
        ads_count = ads_result.scalar()
        
        # Количество с изображениями
        with_images_stmt = (
            select(func.count(func.distinct(News.id)))
            .join(News.images)
        )
        if filters:
            with_images_stmt = with_images_stmt.where(and_(*filters))
        
        images_result = await self.session.execute(with_images_stmt)
        with_images_count = images_result.scalar()
        
        return {
            "total": total_count,
            "ads_filtered": ads_count,
            "with_images": with_images_count,
            "by_source": sources_stats,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None
        }