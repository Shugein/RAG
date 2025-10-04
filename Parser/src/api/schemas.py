# src/api/schemas.py
"""
Pydantic схемы для валидации данных в API
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, validator
from uuid import UUID


# ============================================================================
# Request Schemas
# ============================================================================

class NewsSearchRequest(BaseModel):
    """Запрос поиска новостей"""
    query: Optional[str] = Field(None, description="Поисковый запрос")
    source: Optional[str] = Field(None, description="Код источника")
    date_from: Optional[datetime] = Field(None, description="Дата начала")
    date_to: Optional[datetime] = Field(None, description="Дата окончания")
    ticker: Optional[str] = Field(None, description="Тикер компании")
    topic: Optional[str] = Field(None, description="Тема")
    include_ads: bool = Field(False, description="Включать рекламу")
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class BackfillRequest(BaseModel):
    """Запрос на backfill"""
    source_code: Optional[str] = Field(None, description="Код источника")
    days_back: int = Field(7, ge=1, le=365, description="Дней назад")
    limit: Optional[int] = Field(None, description="Лимит сообщений")


# ============================================================================
# Response Schemas  
# ============================================================================

class SourceResponse(BaseModel):
    """Ответ с информацией об источнике"""
    code: str
    name: str
    kind: str
    enabled: bool
    trust_level: int
    url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class EntityResponse(BaseModel):
    """Извлеченная сущность"""
    type: str
    text: str
    normalized: Optional[Any] = None
    confidence: float


class CompanyResponse(BaseModel):
    """Связанная компания"""
    secid: str
    isin: Optional[str] = None
    board: Optional[str] = None
    name: str
    confidence: float
    is_traded: bool


class TopicResponse(BaseModel):
    """Тема новости"""
    topic: str
    confidence: float


class EnrichmentData(BaseModel):
    """Данные обогащения"""
    entities: List[EntityResponse] = []
    companies: List[CompanyResponse] = []
    topics: List[TopicResponse] = []


class ImageResponse(BaseModel):
    """Информация об изображении"""
    id: str
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    size: Optional[int] = None
    url: str


class NewsResponse(BaseModel):
    """Полная информация о новости"""
    id: str
    source: str
    source_name: str
    external_id: str
    url: Optional[str] = None
    title: str
    summary: Optional[str] = None
    text_html: Optional[str] = None
    text_plain: Optional[str] = None
    published_at: datetime
    detected_at: datetime
    is_updated: bool = False
    enrichment: Optional[EnrichmentData] = None
    images: List[ImageResponse] = []
    metadata: Optional[Dict[str, Any]] = None
    detailed_json: Optional[Dict[str, Any]] = None  # Детальный JSON ответ от CEG системы
    
    model_config = ConfigDict(from_attributes=True)


class NewsListItemResponse(BaseModel):
    """Элемент списка новостей"""
    id: str
    source: str
    source_name: str
    external_id: str
    url: Optional[str] = None
    title: str
    summary: Optional[str] = None
    published_at: datetime
    detected_at: datetime
    has_images: bool = False
    enrichment: Optional[EnrichmentData] = None
    
    model_config = ConfigDict(from_attributes=True)


class NewsListResponse(BaseModel):
    """Ответ со списком новостей"""
    items: List[NewsListItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
    
    model_config = ConfigDict(from_attributes=True)


class StatsResponse(BaseModel):
    """Статистика"""
    total: int
    ads_filtered: int
    with_images: int
    by_source: List[Dict[str, Any]]
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class HealthResponse(BaseModel):
    """Статус здоровья системы"""
    status: str
    database: bool
    rabbitmq: bool
    redis: bool
    telegram: Optional[bool] = None
    timestamp: datetime
    version: str = "1.0.0"


class JobResponse(BaseModel):
    """Ответ о запущенной задаче"""
    job_id: str
    status: str
    message: str
    created_at: datetime


# ============================================================================
# WebSocket Schemas
# ============================================================================

class NewsEvent(BaseModel):
    """Событие новости для WebSocket"""
    event_type: str  # news.created, news.updated
    news_id: str
    source: str
    title: str
    published_at: datetime
    enrichment: Optional[EnrichmentData] = None


# ============================================================================
# Event Importance Schemas
# ============================================================================

class EventImportanceResponse(BaseModel):
    """Ответ с оценкой важности события"""
    event_id: UUID
    event_type: str
    event_title: str
    event_timestamp: datetime
    importance_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Общий балл важности")
    novelty: Optional[float] = Field(None, ge=0.0, le=1.0, description="Компонент новизны")
    burst: Optional[float] = Field(None, ge=0.0, le=1.0, description="Компонент частоты")
    credibility: Optional[float] = Field(None, ge=0.0, le=1.0, description="Компонент надежности")
    breadth: Optional[float] = Field(None, ge=0.0, le=1.0, description="Компонент широты")
    price_impact: Optional[float] = Field(None, ge=0.0, le=1.0, description="Компонент рыночного влияния")
    components_details: Dict[str, Any] = Field(default_factory=dict, description="Детали расчета компонентов")
    calculation_timestamp: Optional[datetime] = Field(None, description="Время расчета")
    weights_version: Optional[str] = Field(None, description="Версия весов")


class EventImportanceSummaryResponse(BaseModel):
    """Сводная статистика важности событий"""
    period_hours: int
    total_events: int
    avg_importance: float = Field(description="Средняя важность")
    max_importance: float = Field(description="Максимальная важность")
    min_importance: float = Field(description="Минимальная важность")
    stddev_importance: Optional[float] = Field(description="Стандартное отклонение")
    avg_novelty: float = Field(description="Средняя новизна")
    avg_burst: float = Field(description="Средний burst")
    avg_credibility: float = Field(description="Средняя надежность")
    avg_breadth: float = Field(description="Средняя широта")
    avg_price_impact: float = Field(description="Среднее рыночное влияние")
    top_events: List[Dict[str, Any]] = Field(description="Топ события по важности")
    event_type_stats: Dict[str, Any] = Field(description="Статистика по типам событий")


# ============================================================================
# Watchers Schemas  
# ============================================================================

class TriggeredWatchResponse(BaseModel):
    """Ответ со сработавшим watcher'ом"""
    watch_id: str
    rule_id: str
    rule_name: str
    watch_level: str = Field(description="L0, L1, или L2")
    event_id: str
    trigger_time: datetime
    auto_expire_at: datetime
    status: str = Field(description="triggered, notified, expired")
    notifications_sent: bool
    context: Dict[str, Any] = Field(default_factory=dict, description="Контекст срабатывания")
    alerts: List[str] = Field(default_factory=list, description="Список для уведомлений")
    notified_at: Optional[datetime] = None


class EventPredictionResponse(BaseModel):
    """Ответ с прогнозом события"""
    prediction_id: str
    watch_id: str
    base_event_id: str
    base_event_type: Optional[str] = None
    predicted_event_type: str
    prediction_probability: float = Field(ge=0.0, le=1.0, description="Вероятность прогноза")
    prediction_window_days: int = Field(ge=1, le=30, description="Окно предсказания")
    target_date_estimate: datetime
    description: Optional[str] = None
    status: str = Field(description="pending, fulfilled, expired")
    fulfilled_at: Optional[datetime] = None
    actual_event_id: Optional[str] = None
    prediction_context: Dict[str, Any] = Field(default_factory=dict, description="Контекст прогноза")
    created_at: datetime
