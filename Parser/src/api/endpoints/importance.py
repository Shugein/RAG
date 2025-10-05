#Parser.src/api/endpoints/importance.py
"""
API endpoints for Event Importance Score
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload

from Parser.src.core.database import get_db_session
from Parser.src.core.models import Event, EventImportance, News
from Parser.src.api.schemas import EventImportanceResponse, EventImportanceSummaryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/importance", tags=["importance"])


@router.get("/events/{event_id}", response_model=EventImportanceResponse)
async def get_event_importance(
    event_id: UUID,
    db: AsyncSession = Depends(get_db_session)
) -> EventImportanceResponse:
    """
    Получить оценку важности события
    
    Args:
        event_id: ID события
        
    Returns:
        Данные о важности события
    """
    
    # Получаем событие с данными о важности
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.importance_scores))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(404, f"Event {event_id} not found")
    
    # Получаем последнюю оценку важности
    latest_importance = None
    if event.importance_scores:
        latest_importance = max(event.importance_scores, key=lambda x: x.calculation_timestamp)
    
    return EventImportanceResponse(
        event_id=event.id,
        event_type=event.event_type,
        event_title=event.title,
        event_timestamp=event.ts,
        importance_score=latest_importance.importance_score if latest_importance else None,
        novelty=latest_importance.novelty if latest_importance else None,
        burst=latest_importance.burst if latest_importance else None,
        credibility=latest_importance.credibility if latest_importance else None,
        breadth=latest_importance.breadth if latest_importance else None,
        price_impact=latest_importance.price_impact if latest_importance else None,
        components_details=latest_importance.components_details if latest_importance else {},
        calculation_timestamp=latest_importance.calculation_timestamp if latest_importance else None,
        weights_version=latest_importance.weights_version if latest_importance else None
    )


@router.get("/events", response_model=List[EventImportanceResponse])
async def list_events_by_importance(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    min_importance: float = Query(0.0, ge=0.0, le=1.0),
    event_type: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db_session)
) -> List[EventImportanceResponse]:
    """
    Получить список событий отсортированных по важности
    
    Args:
        limit: Количество событий для возврата
        offset: Смещение для пагинации
        min_importance: Минимальный балл важности
        event_type: Фильтр по типу события
        since: Фильтр по времени (с какого момента)
        
    Returns:
        Список событий с оценками важности
    """
    
    # Базовый запрос с важностью
    query = (
        select(Event, EventImportance)
        .join(EventImportance, Event.id == EventImportance.event_id)
        .where(EventImportance.importance_score >= min_importance)
    )
    
    # Применяем фильтры
    if event_type:
        query = query.where(Event.event_type == event_type)
    
    if since:
        query = query.where(Event.ts >= since)
    
    # Сортируем по важности и добавляем пагинацию
    query = (
        query.order_by(desc(EventImportance.importance_score))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    rows = result.fetchall()
    
    responses = []
    for event, importance in rows:
        responses.append(EventImportanceResponse(
            event_id=event.id,
            event_type=event.event_type,
            event_title=event.title,
            event_timestamp=event.ts,
            importance_score=importance.importance_score,
            novelty=importance.novelty,
            burst=importance.burst,
            credibility=importance.credibility,
            breadth=importance.breadth,
            price_impact=importance.price_impact,
            components_details=importance.components_details or {},
            calculation_timestamp=importance.calculation_timestamp,
            weights_version=importance.weights_version
        ))
    
    return responses


@router.get("/summary", response_model=EventImportanceSummaryResponse)
async def get_importance_summary(
    period_hours: int = Query(24, ge=1, le=168),  # максимум неделя
    db: AsyncSession = Depends(get_db_session)
) -> EventImportanceSummaryResponse:
    """
    Получить сводную статистику по важности событий
    
    Args:
        period_hours: Период для анализа (в часах)
        
    Returns:
        Сводная статистика важности событий
    """
    
    # Временной фильтр
    since_date = datetime.utcnow() - timedelta(hours=period_hours)
    
    # Статистика по важности
    stats_query = (
        select(
            func.count(EventImportance.id).label('total_events'),
            func.avg(EventImportance.importance_score).label('avg_importance'),
            func.max(EventImportance.importance_score).label('max_importance'),
            func.min(EventImportance.importance_score).label('min_importance'),
            func.stddev(EventImportance.importance_score).label('stddev_importance'),
            func.avg(EventImportance.novelty).label('avg_novelty'),
            func.avg(EventImportance.burst).label('avg_burst'),
            func.avg(EventImportance.credibility).label('avg_credibility'),
            func.avg(EventImportance.breadth).label('avg_breadth'),
            func.avg(EventImportance.price_impact).label('avg_price_impact')
        )
        .select_from(EventImportance)
        .join(Event, EventImportance.event_id == Event.id)
        .where(Event.ts >= since_date)
    )
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.fetchone()
    
    # Топ события по важности
    top_events_query = (
        select(Event, EventImportance)
        .join(EventImportance, Event.id == EventImportance.event_id)
        .where(Event.ts >= since_date)
        .order_by(desc(EventImportance.importance_score))
        .limit(10)
    )
    
    top_result = await db.execute(top_events_query)
    top_rows = top_result.fetchall()
    
    top_events = []
    for event, importance in top_rows:
        top_events.append({
            'event_id': str(event.id),
            'event_type': event.event_type,
            'title': event.title,
            'importance_score': importance.importance_score,
            'timestamp': event.ts.isoformat()
        })
    
    # Статистика по типам событий
    event_type_stats_query = (
        select(
            Event.event_type,
            func.count(EventImportance.id).label('count'),
            func.avg(EventImportance.importance_score).label('avg_importance')
        )
        .select_from(EventImportance)
        .join(Event, EventImportance.event_id == Event.id)
        .where(Event.ts >= since_date)
        .group_by(Event.event_type)
        .order_by(desc(func.avg(EventImportance.importance_score)))
        .limit(10)
    )
    
    type_stats_result = await db.execute(event_type_stats_query)
    type_stats_rows = type_stats_result.fetchall()
    
    event_type_stats = {
        event_type: {
            'count': count,
            'avg_importance': float(avg_importance)
        }
        for event_type, count, avg_importance in type_stats_rows
    }
    
    return EventImportanceSummaryResponse(
        period_hours=period_hours,
        total_events=stats.total_events or 0,
        avg_importance=float(stats.avg_importance or 0),
        max_importance=float(stats.max_importance or 0),
        min_importance=float(stats.min_importance or 0),
        stddev_importance=float(stats.stddev_importance or 0),
        avg_novelty=float(stats.avg_novelty or 0),
        avg_burst=float(stats.avg_burst or 0),
        avg_credibility=float(stats.avg_credibility or 0) if stats.avg_credibility else 0,
        avg_breadth=float(stats.avg_breadth or 0),
        avg_price_impact=float(stats.avg_price_impact or 0) if stats.avg_price_impact else 0,
        top_events=top_events,
        event_type_stats=event_type_stats
    )


@router.get("/analytics/trends", response_model=dict)
async def get_importance_trends(
    event_type: Optional[str] = Query(None),
    period_days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Получить тренды важности событий по дням
    
    Args:
        event_type: Фильтр по типу события
        period_days: Период для анализа (в днях)
        
    Returns:
        Тренды важности по дням
    """
    
    since_date = datetime.utcnow() - timedelta(days=period_days)
    
    # Агрегация по дням
    trends_query = (
        select(
            func.date(Event.ts).label('date'),
            func.count(EventImportance.id).label('daily_count'),
            func.avg(EventImportance.importance_score).label('daily_avg_importance'),
            func.max(EventImportance.importance_score).label('daily_max_importance')
        )
        .select_from(EventImportance)
        .join(Event, EventImportance.event_id == Event.id)
        .where(Event.ts >= since_date)
    )
    
    if event_type:
        trends_query = trends_query.where(Event.event_type == event_type)
    
    trends_query = (
        trends_query.group_by(func.date(Event.ts))
        .order_by(func.date(Event.ts))
    )
    
    trends_result = await db.execute(trends_query)
    trends_rows = trends_result.fetchall()
    
    trends = []
    for row in trends_rows:
        trends.append({
            'date': row.date.isoformat(),
            'event_count': row.daily_count,
            'avg_importance': float(row.daily_avg_importance or 0),
            'max_importance': float(row.daily_max_importance or 0)
        })
    
    return {
        'event_type': event_type,
        'period_days': period_days,
        'trends': trends
    }


@router.get("/analytics/distribution", response_model=dict)
async def get_importance_distribution(
    period_hours: int = Query(168, ge=1, le=720),  # максимум месяц
    bins: int = Query(10, ge=5, le=20),
    db: AsyncSession = Depends(get_db_session)
) -> dict:
    """
    Получить распределение важности событий
    
    Args:
        period_hours: Период для анализа (в часах)
        bins: Количество бинов для гистограммы
        
    Returns:
        Распределение важности событий
    """
    
    since_date = datetime.utcnow() - timedelta(hours=period_hours)
    
    # Статистики для создания бинов
    stats_query = (
        select(
            func.min(EventImportance.importance_score).label('min_score'),
            func.max(EventImportance.importance_score).label('max_score')
        )
        .select_from(EventImportance)
        .join(Event, EventImportance.event_id == Event.id)
        .where(Event.ts >= since_date)
    )
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.fetchone()
    
    if not stats or stats.min_score is None:
        return {'bins': [], 'distribution': []}
    
    min_score = float(stats.min_score)
    max_score = float(stats.max_score)
    bin_size = (max_score - min_score) / bins
    
    distribution = []
    
    for i in range(bins):
        bin_start = min_score + (i * bin_size)
        bin_end = min_score + ((i + 1) * bin_size)
        
        # Подсчитываем события в бине
        count_query = (
            select(func.count(EventImportance.id))
            .select_from(EventImportance)
            .join(Event, EventImportance.event_id == Event.id)
            .where(
                and_(
                    Event.ts >= since_date,
                    EventImportance.importance_score >= bin_start if i == 0 else EventImportance.importance_score > bin_start,
                    EventImportance.importance_score <= bin_end
                )
            )
        )
        
        count_result = await db.execute(count_query)
        count = count_result.scalar() or 0
        
        distribution.append({
            'bin_start': bin_start,
            'bin_end': bin_end,
            'count': count,
            'percentage': 0  # Будет рассчитано после подсчета total
        })
    
    # Рассчитываем проценты
    total_events = sum(bin_data['count'] for bin_data in distribution)
    if total_events > 0:
        for bin_data in distribution:
            bin_data['percentage'] = (bin_data['count'] / total_events) * 100
    
    return {
        'period_hours': period_hours,
        'total_events': total_events,
        'min_score': min_score,
        'max_score': max_score,
        'bin_size': bin_size,
        'distribution': distribution
    }
