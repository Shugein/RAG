#Parser.src/api/endpoints/watchers.py
"""
API endpoints for Watchers System (L0/L1/L2 monitoring)
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload

from Parser.src.core.database import get_db_session
from Parser.src.core.models import Event, TriggeredWatch, EventPrediction
from Parser.src.api.schemas import TriggeredWatchResponse, EventPredictionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watchers", tags=["watchers"])


@router.get("/active", response_model=List[TriggeredWatchResponse])
async def get_active_watches(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    watch_level: Optional[str] = Query(None, regex="^(L0|L1|L2)$"),
    db: AsyncSession = Depends(get_db_session)
) -> List[TriggeredWatchResponse]:
    """
    Получить список активных watcher'ов
    
    Args:
        limit: Количество записей для возврата
        offset: Смещение для пагинации
        watch_level: Фильтр по уровню мониторинга (L0, L1, L2)
        
    Returns:
        Список активных watcher'ов
    """
    
    query = (
        select(TriggeredWatch)
        .where(TriggeredWatch.status.in_(['triggered', 'notified']))
        .order_by(desc(TriggeredWatch.trigger_time))
    )
    
    if watch_level:
        query = query.where(TriggeredWatch.watch_level == watch_level)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    watches = result.scalars().all()
    
    responses = []
    for watch in watches:
        responses.append(TriggeredWatchResponse(
            watch_id=str(watch.id),
            rule_id=watch.rule_id,
            rule_name=watch.rule_name,
            watch_level=watch.watch_level,
            event_id=str(watch.event_id),
            trigger_time=watch.trigger_time,
            auto_expire_at=watch.auto_expire_at,
            status=watch.status,
            notifications_sent=watch.notifications_sent,
            context=watch.context or {},
            alerts=watch.alerts or [],
            notified_at=watch.notified_at
        ))
    
    return responses


@router.get("/predictions", response_model=List[EventPredictionResponse])
async def get_event_predictions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, regex="^(pending|fulfilled|expired)$"),
    db: AsyncSession = Depends(get_db_session)
) -> List[EventPredictionResponse]:
    """
    Получить список прогнозов событий
    
    Args:
        limit: Количество записей для возврата
        offset: Смещение для пагинации
        status: Фильтр по статусу прогноза
        
    Returns:
        Список прогнозов событий
    """
    
    query = (
        select(EventPrediction)
        .options(
            selectinload(EventPrediction.triggered_watch),
            selectinload(EventPrediction.base_event),
            selectinload(EventPrediction.actual_event)
        )
        .order_by(desc(EventPrediction.created_at))
    )
    
    if status:
        query = query.where(EventPrediction.status == status)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    predictions = result.scalars().all()
    
    responses = []
    for pred in predictions:
        responses.append(EventPredictionResponse(
            prediction_id=str(pred.id),
            watch_id=str(pred.watch_id),
            base_event_id=str(pred.base_event_id),
            base_event_type=pred.base_event.event_type if pred.base_event else None,
            predicted_event_type=pred.predicted_event_type,
            prediction_probability=pred.prediction_probability,
            prediction_window_days=pred.prediction_window_days,
            target_date_estimate=pred.target_date_estimate,
            description=pred.description,
            status=pred.status,
            fulfilled_at=pred.fulfilled_at,
            actual_event_id=str(pred.actual_event_id) if pred.actual_event_id else None,
            prediction_context=pred.prediction_context or {},
            created_at=pred.created_at
        ))
    
    return responses


@router.get("/statistics", response_model=Dict[str, Any])
async def get_watchers_statistics(
    period_hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Получить статистику watcher'ов
    
    Args:
        period_hours: Период для анализа (в часах)
        
    Returns:
        Статистика watcher'ов по уровням
    """
    
    since_date = datetime.utcnow() - timedelta(hours=period_hours)
    
    # Общая статистика срабатываний
    general_stats_query = (
        select(
            func.count(TriggeredWatch.id).label('total_triggers'),
            func.count(func.distinct(TriggeredWatch.event_id)).label('unique_events'),
            func.count(func.distinct(TriggeredWatch.rule_id)).label('unique_rules')
        )
        .where(TriggeredWatch.trigger_time >= since_date)
    )
    
    general_result = await db.execute(general_stats_query)
    general_stats = general_result.fetchone()
    
    # Статистика по уровням
    level_stats_query = (
        select(
            TriggeredWatch.watch_level,
            func.count(TriggeredWatch.id).label('count'),
            func.count(func.distinct(TriggeredWatch.event_id)).label('unique_events'),
            func.avg(func.cast(TriggeredWatch.notifications_sent, func.Integer)).label('notification_rate')
        )
        .where(TriggeredWatch.trigger_time >= since_date)
        .group_by(TriggeredWatch.watch_level)
        .order_by(TriggeredWatch.watch_level)
    )
    
    level_result = await db.execute(level_stats_query)
    level_stats = level_result.fetchall()
    
    level_stats_dict = {
        level: {
            'trigger_count': count,
            'unique_events': unique_events,
            'notification_rate': float(notification_rate or 0)
        }
        for level, count, unique_events, notification_rate in level_stats
    }
    
    # Статистика по правилам
    rule_stats_query = (
        select(
            TriggeredWatch.rule_id,
            TriggeredWatch.rule_name,
            TriggeredWatch.watch_level,
            func.count(TriggeredWatch.id).label('count'),
            func.max(TriggeredWatch.trigger_time).label('last_trigger')
        )
        .where(TriggeredWatch.trigger_time >= since_date)
        .group_by(TriggeredWatch.rule_id, TriggeredWatch.rule_name, TriggeredWatch.watch_level)
        .order_by(desc(func.count(TriggeredWatch.id)))
        .limit(10)
    )
    
    rule_result = await db.execute(rule_stats_query)
    rule_stats = [
        {
            'rule_id': rule_id,
            'rule_name': rule_name,
            'level': level,
            'trigger_count': count,
            'last_trigger': last_trigger.isoformat()
        }
        for rule_id, rule_name, level, count, last_trigger in rule_result.fetchall()
    ]
    
    # Статистика прогнозов
    predictions_stats_query = (
        select(
            EventPrediction.status,
            func.count(EventPrediction.id).label('count'),
            func.avg(EventPrediction.prediction_probability).label('avg_probability')
        )
        .where(EventPrediction.created_at >= since_date)
        .group_by(EventPrediction.status)
    )
    
    pred_result = await db.execute(predictions_stats_query)
    prediction_stats = {
        status: {
            'count': count,
            'avg_probability': float(avg_probability or 0)
        }
        for status, count, avg_probability in pred_result.fetchall()
    }
    
    return {
        'period_hours': period_hours,
        'general_stats': {
            'total_triggers': general_stats.total_triggers or 0,
            'unique_events': general_stats.unique_events or 0,
            'unique_rules': general_stats.unique_rules or 0
        },
        'level_stats': level_stats_dict,
        'top_rules': rule_stats,
        'prediction_stats': prediction_stats
    }


@router.get("/rules", response_model=List[Dict[str, Any]])
async def get_watcher_rules(
    db: AsyncSession = Depends(get_db_session)
) -> List[Dict[str, Any]]:
    """
    Получить список правил мониторинга
    
    Returns:
        Список всех доступных правил watcher'ов
    """
    
    # Этот endpoint должен читать правила из конфигурации watcher'ов
    # Пока возвращаем статичный список правил
    
    rules = [
        {
            "id": "critical_sanctions",
            "name": "Критические санкции",
            "level": "L0",
            "description": "Новые санкции против банковского/энергетического/оборонного секторов",
            "priority": "high",
            "event_types": ["sanctions"],
            "sectors": ["banks", "energy", "defense"],
            "importance_threshold": 0.8
        },
        {
            "id": "default_events",
            "name": "Дефолты компаний",
            "level": "L0",
            "description": "Объявления о дефолтах или банкротствах",
            "priority": "critical",
            "event_types": ["default", "bankruptcy"],
            "importance_threshold": 0.9
        },
        
        {
            "id": "central_bank_rates",
            "name": "Политика ЦБ",
            "level": "L0",
            "description": "Изменения ключевой ставки ЦБ РФ",
            "priority": "high",
            "event_types": ["rate_hike", "rate_cut"],
            "companies": ["ЦБ РФ", "Bank of Russia"],
            "sectors": ["monetary"],
            "importance_threshold": 0.7
        },
        
        {
            "id": "sanctions_market_pattern",
            "name": "Паттерн санкции→рынок",
            "level": "L1",
            "description": "Санкции с последующим анализом рыночной реакции",
            "priority": "medium",
            "event_types": ["sanctions"],
            "pattern_type": "causal_chain",
            "importance_threshold": 0.7
        },
        
        {
            "id": "sanctions_consequence_prediction",
            "name": "Прогноз последствий санкций",
            "level": "L2",
            "description": "Предсказывает рыночную реакцию на новые санкции",
            "priority": "medium",
            "event_types": ["sanctions"],
            "prediction_window_days": 14,
            "importance_threshold": 0.8
        }
    ]
    
    return rules


@router.get("/alerts/recent", response_model=List[Dict[str, Any]])
async def get_recent_alerts(
    limit: int = Query(20, ge=1, le=100),
    priority: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    db: AsyncSession = Depends(get_db_session)
) -> List[Dict[str, Any]]:
    """
    Получить список недавних алертов
    
    Args:
        limit: Количество алертов
        priority: Фильтр по приоритету
        
    Returns:
        Список недавних алертов
    """
    
    # Получаем недавние срабатывания watcher'ов с контекстом
    query = (
        select(TriggeredWatch)
        .options(selectinload(TriggeredWatch.event))
        .where(TriggeredWatch.status == 'triggered')
        .order_by(desc(TriggeredWatch.trigger_time))
        .limit(limit)
    )
    
    result = await db.execute(query)
    watches = result.scalars().all()
    
    alerts = []
    for watch in watches:
        # Извлекаем информацию о событии
        context = watch.context or {}
        importance_score = context.get('importance_score', 0)
        
        # Определяем приоритет на основе важности
        alert_priority = "medium"
        if importance_score >= 0.9:
            alert_priority = "critical"
        elif importance_score >= 0.7:
            alert_priority = "high"
        elif importance_score >= 0.5:
            alert_priority = "medium"
        else:
            alert_priority = "low"
        
        # Фильтруем по приоритету если указан
        if priority and alert_priority != priority:
            continue
        
        alert = {
            "alert_id": str(watch.id),
            "rule_name": watch.rule_name,
            "level": watch.watch_level,
            "priority": alert_priority,
            "event_id": str(watch.event_id),
            "event_type": watch.event.event_type if watch.event else None,
            "event_title": watch.event.title if watch.event else "Unknown event",
            "triggered_at": watch.trigger_time.isoformat(),
            "importance_score": importance_score,
            "companies": context.get('companies', []),
            "tickers": context.get('tickers', []),
            "context_summary": {
                "burst_count": context.get('burst_count', 0),
                "trigger_type": context.get('trigger_type', 'unknown'),
                "importance_details": context.get('importance_details', {})
            }
        }
        
        alerts.append(alert)
    
    return alerts


@router.get("/prediction/{prediction_id}/status", response_model=Dict[str, Any])
async def get_prediction_status(
        prediction_id: UUID,
        db: AsyncSession = Depends(get_db_session)
    ) -> Dict[str, Any]:
        """
        Получить статус конкретного прогноза
        
        Args:
            prediction_id: ID прогноза
            
        Returns:
            Детальная информация о прогнозе
        """
        
        result = await db.execute(
            select(EventPrediction)
            .options(
                selectinload(EventPrediction.triggered_watch),
                selectinload(EventPrediction.base_event),
                selectinload(EventPrediction.actual_event)
            )
            .where(EventPrediction.id == prediction_id)
        )
        
        prediction = result.scalar_one_or_none()
        
        if not prediction:
            raise HTTPException(404, f"Prediction {prediction_id} not found")
        
        response = {
            "prediction_id": str(prediction.id),
            "watch_id": str(prediction.watch_id),
            "base_event": {
                "id": str(prediction.base_event_id),
                "type": prediction.base_event.event_type if prediction.base_event else None,
                "title": prediction.base_event.title if prediction.base_event else None,
                "timestamp": prediction.base_event.ts.isoformat() if prediction.base_event else None
            },
            "prediction": {
                "event_type": prediction.predicted_event_type,
                "probability": prediction.prediction_probability,
                "window_days": prediction.prediction_window_days,
                "target_date": prediction.target_date_estimate.isoformat(),
                "description": prediction.description
            },
            "status": {
                "current": prediction.status,
                "fulfilled_at": prediction.fulfilled_at.isoformat() if prediction.fulfilled_at else None,
                "actual_event": {
                    "id": str(prediction.actual_event_id) if prediction.actual_event_id else None,
                    "type": prediction.actual_event.event_type if prediction.actual_event else None,
                    "title": prediction.actual_event.title if prediction.actual_event else None,
                    "timestamp": prediction.actual_event.ts.isoformat() if prediction.actual_event else None
                } if prediction.actual_event else None
            },
            "accuracy": prediction.prediction_context.get('accuracy') if prediction.prediction_context else None,
            "created_at": prediction.created_at.isoformat()
        }
        
        return response


@router.post("/cleanup-expired")
async def cleanup_expired_watchers(
    max_age_hours: int = Query(168, ge=1, le=720),  # от 1 часа до 30 дней
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Очистить истекшие watcher'ы вручную
    
    Args:
        max_age_hours: Максимальный возраст watcher'а (часы)
        
    Returns:
        Статистика очистки
    """
    
    expire_threshold = datetime.utcnow() - timedelta(hours=max_age_hours)
    
    # Находим истекшие watcher'ы
    expired_query = (
        select(TriggeredWatch)
        .where(
            and_(
                TriggeredWatch.status == 'triggered',
                TriggeredWatch.trigger_time <= expire_threshold
            )
        )
    )
    
    expired_result = await db.execute(expired_query)
    expired_watches = expired_result.scalars().all()
    
    # Обновляем статус на 'expired'
    for watch in expired_watches:
        watch.status = 'expired'
    
    # Также очищаем истекшие прогнозы
    expired_predictions_query = (
        select(EventPrediction)
        .where(
            and_(
                EventPrediction.status == 'pending',
                EventPrediction.target_date_estimate <= datetime.utcnow()
            )
        )
    )
    
    expired_pred_result = await db.execute(expired_predictions_query)
    expired_predictions = expired_pred_result.scalars().all()
    
    for prediction in expired_predictions:
        prediction.status = 'expired'
    
    await db.commit()
    
    return {
        "expired_watchers": len(expired_watches),
        "expired_predictions": len(expired_predictions),
        "max_age_hours": max_age_hours,
        "cleanup_timestamp": datetime.utcnow().isoformat()
    }
