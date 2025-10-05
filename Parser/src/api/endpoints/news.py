#Parser.src/api/endpoints/news.py
"""
News endpoints
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.orm import selectinload

from Parser.src.core.database import get_db
from Parser.src.core.models import News, Source, Entity, LinkedCompany, Topic, Image
from Parser.src.api.schemas import (
    NewsSearchRequest,
    NewsResponse,
    NewsListResponse,
    NewsListItemResponse,
    StatsResponse,
    EnrichmentData,
    EntityResponse,
    CompanyResponse,
    TopicResponse,
    ImageResponse
)

router = APIRouter()


@router.get("", response_model=NewsListResponse)
async def search_news(
    query: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    ticker: Optional[str] = None,
    topic: Optional[str] = None,
    include_ads: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
) -> NewsListResponse:
    """Поиск новостей с фильтрацией"""
    
    # Build query
    stmt = select(News).options(
        selectinload(News.source),
        selectinload(News.entities),
        selectinload(News.linked_companies),
        selectinload(News.topics),
        selectinload(News.images)
    )
    
    # Filters
    filters = []
    
    if not include_ads:
        filters.append(News.is_ad == False)
    
    if source:
        stmt = stmt.join(Source)
        filters.append(Source.code == source)
    
    if date_from:
        filters.append(News.published_at >= date_from)
    
    if date_to:
        filters.append(News.published_at <= date_to)
    
    if ticker:
        stmt = stmt.join(News.linked_companies)
        filters.append(LinkedCompany.secid == ticker.upper())
    
    if topic:
        stmt = stmt.join(News.topics)
        filters.append(Topic.topic == topic)
    
    if query:
        # Simple text search
        search_filter = or_(
            News.title.ilike(f"%{query}%"),
            News.text_plain.ilike(f"%{query}%")
        )
        filters.append(search_filter)
    
    if filters:
        stmt = stmt.where(and_(*filters))
    
    # Get total count
    count_stmt = select(func.count()).select_from(News)
    if filters:
        count_stmt = count_stmt.where(and_(*filters))
    
    result = await db.execute(count_stmt)
    total = result.scalar_one()
    
    # Get paginated results
    stmt = stmt.order_by(desc(News.published_at)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    news_items = result.scalars().all()
    
    # Convert to response model
    items = []
    for news in news_items:
        enrichment = None
        if news.entities or news.linked_companies or news.topics:
            enrichment = EnrichmentData(
                entities=[
                    EntityResponse(
                        type=e.type,
                        text=e.text,
                        normalized=e.norm,
                        confidence=e.confidence
                    ) for e in news.entities
                ],
                companies=[
                    CompanyResponse(
                        secid=c.secid,
                        isin=c.isin,
                        board=c.board,
                        name=c.name,
                        confidence=c.confidence,
                        is_traded=c.is_traded
                    ) for c in news.linked_companies
                ],
                topics=[
                    TopicResponse(
                        topic=t.topic,
                        confidence=t.confidence
                    ) for t in news.topics
                ]
            )
        
        items.append(NewsListItemResponse(
            id=str(news.id),
            source=news.source.code,
            source_name=news.source.name,
            external_id=news.external_id,
            url=news.url,
            title=news.title,
            summary=news.summary,
            published_at=news.published_at,
            detected_at=news.detected_at,
            has_images=len(news.images) > 0,
            enrichment=enrichment
        ))
    
    return NewsListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total
    )


@router.get("/{news_id}", response_model=NewsResponse)
async def get_news(
    news_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> NewsResponse:
    """Получить детальную информацию о новости"""
    
    stmt = select(News).options(
        selectinload(News.source),
        selectinload(News.entities),
        selectinload(News.linked_companies),
        selectinload(News.topics),
        selectinload(News.images)
    ).where(News.id == news_id)
    
    result = await db.execute(stmt)
    news = result.scalar_one_or_none()
    
    if not news:
        raise HTTPException(status_code=404, detail="News not found")
    
    # Build enrichment data
    enrichment = None
    if news.entities or news.linked_companies or news.topics:
        enrichment = EnrichmentData(
            entities=[
                EntityResponse(
                    type=e.type,
                    text=e.text,
                    normalized=e.norm,
                    confidence=e.confidence
                ) for e in news.entities
            ],
            companies=[
                CompanyResponse(
                    secid=c.secid,
                    isin=c.isin,
                    board=c.board,
                    name=c.name,
                    confidence=c.confidence,
                    is_traded=c.is_traded
                ) for c in news.linked_companies
            ],
            topics=[
                TopicResponse(
                    topic=t.topic,
                    confidence=t.confidence
                ) for t in news.topics
            ]
        )
    
    # Build image responses
    images = [
        ImageResponse(
            id=str(img.id),
            mime_type=img.mime_type,
            width=img.width,
            height=img.height,
            size=img.file_size,
            url=f"/api/images/{img.id}"
        ) for img in news.images
    ]
    
    return NewsResponse(
        id=str(news.id),
        source=news.source.code,
        source_name=news.source.name,
        external_id=news.external_id,
        url=news.url,
        title=news.title,
        summary=news.summary,
        text_html=news.text_html,
        text_plain=news.text_plain,
        published_at=news.published_at,
        detected_at=news.detected_at,
        is_updated=news.is_updated,
        enrichment=enrichment,
        images=images,
        metadata=news.meta
    )


@router.get("/stats/summary", response_model=StatsResponse)
async def get_stats(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
) -> StatsResponse:
    """Получить статистику по новостям"""
    
    # Base query
    filters = []
    if date_from:
        filters.append(News.published_at >= date_from)
    if date_to:
        filters.append(News.published_at <= date_to)
    
    # Total count
    total_stmt = select(func.count()).select_from(News)
    if filters:
        total_stmt = total_stmt.where(and_(*filters))
    
    result = await db.execute(total_stmt)
    total = result.scalar_one()
    
    # Ads filtered
    ads_stmt = select(func.count()).select_from(News).where(News.is_ad == True)
    if filters:
        ads_stmt = ads_stmt.where(and_(*filters))
    
    result = await db.execute(ads_stmt)
    ads_filtered = result.scalar_one()
    
    # With images
    images_stmt = select(func.count(func.distinct(News.id))).select_from(News).join(News.images)
    if filters:
        images_stmt = images_stmt.where(and_(*filters))
    
    result = await db.execute(images_stmt)
    with_images = result.scalar_one()
    
    # By source
    by_source_stmt = select(
        Source.code,
        Source.name,
        func.count(News.id).label('count')
    ).join(News).group_by(Source.code, Source.name)
    
    if filters:
        by_source_stmt = by_source_stmt.where(and_(*filters))
    
    result = await db.execute(by_source_stmt)
    by_source = [
        {"code": row.code, "name": row.name, "count": row.count}
        for row in result
    ]
    
    return StatsResponse(
        total=total,
        ads_filtered=ads_filtered,
        with_images=with_images,
        by_source=by_source,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None
    )

