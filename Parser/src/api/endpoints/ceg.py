#Parser.src/api/endpoints/ceg.py
"""
CEG (Causal Event Graph) API endpoints
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from Parser.src.core.database import get_session
from Parser.src.core.models import Event
from Parser.src.graph_models import GraphService
from Parser.src.core.config import settings

router = APIRouter(prefix="/ceg", tags=["ceg"])


class EventResponse(BaseModel):
    """Ответ с событием"""
    id: str
    news_id: str
    event_type: str
    title: str
    ts: datetime
    attrs: dict
    is_anchor: bool
    confidence: float

    class Config:
        from_attributes = True


class CausalLinkResponse(BaseModel):
    """Ответ с причинной связью"""
    cause_id: str
    effect_id: str
    kind: str
    sign: str
    expected_lag: str
    conf_total: float


class CausalChainResponse(BaseModel):
    """Ответ с причинной цепочкой"""
    event_ids: List[str]
    depth: int
    chain_confidence: float


# Dependency: GraphService
async def get_graph_service():
    """Получить GraphService"""
    graph = GraphService(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    try:
        yield graph
    finally:
        await graph.close()


@router.get("/events", response_model=List[EventResponse])
async def list_events(
    event_type: Optional[str] = Query(None, description="Фильтр по типу события"),
    is_anchor: Optional[bool] = Query(None, description="Только якорные события"),
    date_from: Optional[datetime] = Query(None, description="Начало периода"),
    date_to: Optional[datetime] = Query(None, description="Конец периода"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session)
):
    """Получить список событий"""
    stmt = select(Event)

    if event_type:
        stmt = stmt.where(Event.event_type == event_type)

    if is_anchor is not None:
        stmt = stmt.where(Event.is_anchor == is_anchor)

    if date_from:
        stmt = stmt.where(Event.ts >= date_from)

    if date_to:
        stmt = stmt.where(Event.ts <= date_to)

    stmt = stmt.order_by(Event.ts.desc()).limit(limit).offset(offset)

    result = await session.execute(stmt)
    events = result.scalars().all()

    return [
        EventResponse(
            id=str(event.id),
            news_id=str(event.news_id),
            event_type=event.event_type,
            title=event.title,
            ts=event.ts,
            attrs=event.attrs,
            is_anchor=event.is_anchor,
            confidence=event.confidence
        )
        for event in events
    ]


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """Получить событие по ID"""
    stmt = select(Event).where(Event.id == event_id)
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventResponse(
        id=str(event.id),
        news_id=str(event.news_id),
        event_type=event.event_type,
        title=event.title,
        ts=event.ts,
        attrs=event.attrs,
        is_anchor=event.is_anchor,
        confidence=event.confidence
    )


@router.get("/events/{event_id}/causal-context")
async def get_event_causal_context(
    event_id: str,
    graph: GraphService = Depends(get_graph_service)
):
    """Получить причинный контекст события (предшественники и последователи)"""
    context = await graph.get_event_causal_context(event_id)

    if not context:
        raise HTTPException(status_code=404, detail="Event not found in graph")

    return {
        "event_id": event_id,
        "predecessors": context["predecessors"],
        "successors": context["successors"],
        "impacts": context["impacts"]
    }


@router.get("/events/{event_id}/causal-chains", response_model=List[CausalChainResponse])
async def get_causal_chains(
    event_id: str,
    max_depth: int = Query(3, ge=1, le=5, description="Максимальная глубина цепочки"),
    graph: GraphService = Depends(get_graph_service)
):
    """Получить причинные цепочки от события"""
    chains = await graph.find_causal_chain(event_id, max_depth=max_depth)

    return [
        CausalChainResponse(
            event_ids=chain["event_ids"],
            depth=chain["depth"],
            chain_confidence=chain["chain_confidence"]
        )
        for chain in chains
    ]


@router.get("/events/{event_id}/similar", response_model=List[EventResponse])
async def get_similar_events(
    event_id: str,
    min_similarity: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(5, le=20),
    graph: GraphService = Depends(get_graph_service),
    session: AsyncSession = Depends(get_session)
):
    """Получить похожие события"""
    similar = await graph.find_similar_events(event_id, min_similarity=min_similarity, limit=limit)

    # Загружаем полные данные из PostgreSQL
    event_ids = [record["e2"]["id"] for record in similar]

    if not event_ids:
        return []

    stmt = select(Event).where(Event.id.in_(event_ids))
    result = await session.execute(stmt)
    events = result.scalars().all()

    return [
        EventResponse(
            id=str(event.id),
            news_id=str(event.news_id),
            event_type=event.event_type,
            title=event.title,
            ts=event.ts,
            attrs=event.attrs,
            is_anchor=event.is_anchor,
            confidence=event.confidence
        )
        for event in events
    ]


@router.get("/anchor-events", response_model=List[EventResponse])
async def get_anchor_events(
    event_type: Optional[str] = Query(None, description="Фильтр по типу"),
    limit: int = Query(5, le=20),
    graph: GraphService = Depends(get_graph_service),
    session: AsyncSession = Depends(get_session)
):
    """Получить якорные события для CMNLN"""
    anchors = await graph.find_anchor_events(event_type=event_type, limit=limit)

    # Загружаем полные данные из PostgreSQL
    event_ids = [record["e"]["id"] for record in anchors]

    if not event_ids:
        return []

    stmt = select(Event).where(Event.id.in_(event_ids))
    result = await session.execute(stmt)
    events = result.scalars().all()

    return [
        EventResponse(
            id=str(event.id),
            news_id=str(event.news_id),
            event_type=event.event_type,
            title=event.title,
            ts=event.ts,
            attrs=event.attrs,
            is_anchor=event.is_anchor,
            confidence=event.confidence
        )
        for event in events
    ]


@router.get("/stats")
async def get_ceg_stats(
    session: AsyncSession = Depends(get_session),
    graph: GraphService = Depends(get_graph_service)
):
    """Получить статистику CEG"""
    # PostgreSQL stats
    total_events = await session.scalar(select(Event).count())
    anchor_events = await session.scalar(select(Event).where(Event.is_anchor == True).count())

    # Neo4j stats (можно добавить запросы для подсчета связей)
    # TODO: добавить подсчет CAUSES, IMPACTS relationships

    return {
        "total_events": total_events,
        "anchor_events": anchor_events,
        "event_types": {},  # TODO: group by event_type
        # "causal_links": 0,  # TODO: count CAUSES relationships
        # "impacts": 0  # TODO: count IMPACTS relationships
    }


@router.get("/evidence-analysis/{cause_event_id}/{effect_event_id}", response_model=Dict[str, Any])
async def analyze_evidence_between_events(
    cause_event_id: UUID,
    effect_event_id: UUID,
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Анализ Evidence Events между двумя событиями
    """
    
    # Получаем события
    cause_event_result = await session.execute(
        select(Event).where(Event.id == cause_event_id)
    )
    cause_event = cause_event_result.scalar_one_or_none()
    
    effect_event_result = await session.execute(
        select(Event).where(Event.id == effect_event_id)
    )
    effect_event = effect_event_result.scalar_one_or_none()
    
    if not cause_event or not effect_event:
        raise HTTPException(
            status_code=404, 
            detail=f"Events not found: {cause_event_id}, {effect_event_id}"
        )
    
    # Анализируем Evidence Events если доступен Enhanced Evidence Engine
    if hasattr(ceg.cmnln, 'enhanced_evidence_engine') and ceg.cmnln.enhanced_evidence_engine:
        evidence_analysis = await ceg.cmnln.enhanced_evidence_engine.find_enhanced_evidence_events(
            cause_event, effect_event, max_evidence_count=10
        )
        
        return {
            "cause_event": {
                "id": str(cause_event.id),
                "type": cause_event.event_type,
                "title": cause_event.title,
                "timestamp": cause_event.ts.isoformat()
            },
            "effect_event": {
                "id": str(effect_event.id),
                "type": effect_event.event_type,
                "title": effect_event.title,
                "timestamp": effect_event.ts.isoformat()
            },
            "evidence_analysis": evidence_analysis,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }
    else:
        # Простой fallback анализ
        return {
            "cause_event": {
                "id": str(cause_event.id),
                "type": cause_event.event_type,
                "title": cause_event.title
            },
            "effect_event": {
                "id": str(effect_event.id),
                "type": effect_event.event_type,
                "title": effect_event.title
            },
            "message": "Enhanced evidence analysis not available",
            "fallback_available": True
        }


@router.get("/evidence-engine/stats", response_model=Dict[str, Any])
async def get_evidence_engine_stats(
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Получить статистику Enhanced Evidence Engine
    """
    
    if not hasattr(ceg.cmnln, 'enhanced_evidence_engine') or not ceg.cmnln.enhanced_evidence_engine:
        return {"error": "Enhanced Evidence Engine not available"}
    
    stats = ceg.cmnln.enhanced_evidence_engine.get_statistics()
    
    return {
        "engine_status": "operational",
        "statistics": stats,
        "capabilities": [
            "temporal_proximity_analysis",
            "semantic_relevance_calculation",
            "entity_overlap_detection", 
            "source_trust_evaluation",
            "importance_score_integration",
            "graph_context_analysis"
        ]
    }


@router.get("/causal-chains/{root_event_id}", response_model=Dict[str, Any])
async def discover_causal_chains(
    root_event_id: UUID,
    direction: str = Query("bidirectional", regex="^(forward|backward|bidirectional)$"),
    max_depth: int = Query(3, ge=1, le=10),
    min_confidence: float = Query(0.3, ge=0.0, le=1.0),
    time_window_hours: int = Query(168, ge=1, le=720),  # от 1 часа до 30 дней
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Обнаружить причинные цепочки для корневого события
    """
    
    chains_result = await ceg.cmnln.discover_causal_chains(
        root_event_id=str(root_event_id),
        direction=direction,
        max_depth=max_depth,
        min_confidence=min_confidence,
        time_window_hours=time_window_hours
    )
    
    return chains_result


@router.get("/causal-chains/stats", response_model=Dict[str, Any])
async def get_causal_chains_statistics(
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Получить статистики движка причинных цепочек
    """
    
    stats = ceg.cmnln.get_causal_chains_statistics()
    
    return {
        "engine_status": "operational",
        "statistics": stats,
        "available_directions": ["forward", "backward", "bidirectional"],
        "algorithm_capabilities": [
            "bfs_traversal",
            "temporal_constraints",
            "confidence_filtering",
            "evidence_integration",
            "importance_scoring",
            "cache_optimization"
        ]
    }


@router.get("/chain-analysis/{event1_id}/{event2_id}", response_model=Dict[str, Any])
async def analyze_causal_relation(
    event1_id: UUID,
    event2_id: UUID,
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Анализ причинной связи между двумя событиями
    
    Находит все пути между событиями и анализирует их качество
    """
    
    # Получаем события
    event1_result = await session.execute(
        select(Event).where(Event.id == event1_id)
    )
    event1 = event1_result.scalar_one_or_none()
    
    event2_result = await session.execute(
        select(Event).where(Event.id == event2_id)
    )
    event2 = event2_result.scalar_one_or_none()
    
    if not event1 or not event2:
        raise HTTPException(
            status_code=404,
            detail=f"Events not found: {event1_id}, {event2_id}"
        )
    
    # Анализируем связь между событиями
    analysis_result = {
        "event1": {
            "id": str(event1.id),
            "type": event1.event_type,
            "title": event1.title,
            "timestamp": event1.ts.isoformat()
        },
        "event2": {
            "id": str(event2.id),
            "type": event2.event_type,
            "title": event2.title,
            "timestamp": event2.ts.isoformat()
        },
        "temporal_relation": {
            "time_diff_hours": abs((event2.ts - event1.ts).total_seconds() / 3600),
            "event1_first": event1.ts < event2.ts,
            "is_plausible_causal_order": (event1.ts < event2.ts and 
                                        (event2.ts - event1.ts).total_seconds() <= 72*3600)
        },
        "chain_paths": [],
        "analysis_timestamp": datetime.utcnow().isoformat()
    }
    
    # Ищем цепочки от первого события ко второму
    forward_chains = await ceg.cmnln.discover_causal_chains(
        root_event_id=str(event1.id),
        direction="forward",
        max_depth=4,
        min_confidence=0.25,
        time_window_hours=168
    )
    
    # Фильтруем цепочки, которые включают второе событие
    relevant_chains = []
    if 'chains' in forward_chains:
        for chain in forward_chains['chains']:
            node_ids = [node['event_id'] for node in chain.get('nodes', [])]
            if str(event2.id) in node_ids:
                relevant_chains.append(chain)
    
    analysis_result["chain_paths"] = relevant_chains
    analysis_result["total_paths_found"] = len(relevant_chains)
    analysis_result["shortest_path_length"] = min((len(chain['nodes']) for chain in relevant_chains), default=0)
    analysis_result["strongest_path_confidence"] = max((chain.get('average_confidence', 0) for chain in relevant_chains), default=0)
    
    return analysis_result


# ============================================================================
# Historical Backfill API Endpoints
# ============================================================================

@router.post("/backfill/tasks", response_model=Dict[str, Any])
async def create_backfill_task(
    source_ids: List[str],
    start_date: datetime,
    end_date: datetime,
    priority: str = Query("medium", regex="^(high|medium|low)$"),
    quality_threshold: Optional[float] = Query(None, ge=0.0, le=1.0),
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Создать задачу исторической загрузки событий
    """
    
    from Parser.src.services.events.historical_backfill_service import HistoricalBackfillService
    
    backfill_service = HistoricalBackfillService(session, ceg.graph)
    
    task_id = await backfill_service.create_backfill_task(
        source_ids=source_ids,
        start_date=start_date,
        end_date=end_date,
        priority=priority,
        quality_threshold=quality_threshold
    )
    
    return {
        "task_id": task_id,
        "status": "created",
        "message": f"Backfill task {task_id} created successfully"
    }


@router.get("/backfill/tasks/{task_id}", response_model=Dict[str, Any])
async def get_backfill_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Получить информацию о задаче исторической загрузки
    """
    
    from Parser.src.services.events.historical_backfill_service import HistoricalBackfillService
    
    backfill_service = HistoricalBackfillService(session, ceg.graph)
    task_info = backfill_service.get_task_by_id(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return task_info


@router.post("/backfill/tasks/{task_id}/execute", response_model=Dict[str, Any])
async def execute_backfill_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Выполнить задачу исторической загрузки
    """
    
    from Parser.src.services.events.historical_backfill_service import HistoricalBackfillService
    
    backfill_service = HistoricalBackfillService(session, ceg.graph)
    
    # Проверяем, что задача существует
    if not backfill_service.get_task_by_id(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    result = await backfill_service.execute_backfill_task(task_id)
    
    return result


@router.post("/backfill/tasks/{task_id}/cancel", response_model=Dict[str, Any])
async def cancel_backfill_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Отменить задачу исторической загрузки
    """
    
    from Parser.src.services.events.historical_backfill_service import HistoricalBackfillService
    
    backfill_service = HistoricalBackfillService(session, ceg.graph)
    
    result = backfill_service.cancel_task(task_id)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/backfill/tasks", response_model=List[Dict[str, Any]])
async def get_all_backfill_tasks(
    status: Optional[str] = Query(None, regex="^(pending|running|completed|failed|cancelled)$"),
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Получить список всех задач исторической загрузки
    """
    
    from Parser.src.services.events.historical_backfill_service import HistoricalBackfillService
    
    backfill_service = HistoricalBackfillService(session, ceg.graph)
    tasks = backfill_service.get_all_tasks(status)
    
    return tasks


@router.get("/backfill/stats", response_model=Dict[str, Any])
async def get_backfill_statistics(
    session: AsyncSession = Depends(get_session),
    ceg: CEGRealtimeService = Depends(get_ceg_service)
):
    """
    Получить статистики сервиса исторической загрузки
    """
    
    from Parser.src.services.events.historical_backfill_service import HistoricalBackfillService
    
    backfill_service = HistoricalBackfillService(session, ceg.graph)
    stats = backfill_service.get_statistics()
    
    return stats