#Parser.src/core/models.py

from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean,
    ForeignKey, Index, UniqueConstraint, JSON, LargeBinary,
    Float, Table, CHAR
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, BYTEA
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class SourceKind(str, Enum):
    HTML = "html"
    TELEGRAM = "telegram"
    RSS = "rss"


class OutboxStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class EntityType(str, Enum):
    ORG = "ORG"
    ORG_ALIAS = "ORG_ALIAS"
    DATE = "DATE"
    PERIOD = "PERIOD"
    PCT = "PCT"
    AMOUNT = "AMOUNT"
    UNIT = "UNIT"
    MONEY = "MONEY"
    PERSON = "PERSON"
    LOC = "LOC"


# Association tables
news_images_association = Table(
    'news_images',
    Base.metadata,
    Column('news_id', UUID(as_uuid=True), ForeignKey('news.id', ondelete='CASCADE')),
    Column('image_id', UUID(as_uuid=True), ForeignKey('images.id', ondelete='CASCADE')),
    Column('ord', Integer, default=0),
    UniqueConstraint('news_id', 'image_id', name='uq_news_image')
)


class Source(Base):
    __tablename__ = 'sources'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String(20), nullable=False)  # html, telegram
    code = Column(String(50), unique=True, nullable=False)  # cbonds, cbr, tg_channel_name
    name = Column(String(200), nullable=False)
    base_url = Column(Text)  # for HTML sources
    tg_chat_id = Column(String(100))  # for Telegram sources
    config = Column(JSONB)  # source-specific config (selectors, intervals, etc)
    enabled = Column(Boolean, default=True)
    trust_level = Column(Integer, default=5)  # 0-10, used for spam filtering
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    news = relationship("News", back_populates="source", cascade="all, delete-orphan")
    parser_state = relationship("ParserState", back_populates="source", uselist=False)

    __table_args__ = (
        Index('idx_sources_kind_enabled', 'kind', 'enabled'),
    )


class News(Base):
    __tablename__ = 'news'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey('sources.id'), nullable=False)
    external_id = Column(String(500), nullable=False)  # URL or message_id
    url = Column(Text)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    text_html = Column(Text)
    text_plain = Column(Text)
    lang = Column(String(10), default='ru')
    published_at = Column(DateTime(timezone=True), nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    hash_content = Column(CHAR(64))  # SHA-256 of title+text for dedup
    is_updated = Column(Boolean, default=False)
    is_ad = Column(Boolean, default=False)
    ad_score = Column(Float)
    ad_reasons = Column(JSONB)  # List of triggered ad rules
    meta = Column(JSONB)  # Any source-specific metadata
    detailed_json = Column(JSONB)  # Detailed JSON response from CEG processing

    # Full-text search
    tsv = Column(Text)  # Will be populated by trigger with to_tsvector

    # Relationships
    source = relationship("Source", back_populates="news")
    images = relationship("Image", secondary=news_images_association, back_populates="news")
    entities = relationship("Entity", back_populates="news", cascade="all, delete-orphan")
    linked_companies = relationship("LinkedCompany", back_populates="news", cascade="all, delete-orphan")
    topics = relationship("Topic", back_populates="news", cascade="all, delete-orphan")
    outbox_events = relationship("OutboxEvent", back_populates="news", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('source_id', 'external_id', name='uq_source_external_id'),
        Index('idx_news_published_at', 'published_at'),
        Index('idx_news_source_published', 'source_id', 'published_at'),
        Index('idx_news_hash_content', 'hash_content'),
        Index('idx_news_tsv', 'tsv'),  # GIN index will be created via migration
        Index('idx_news_detailed_json', 'detailed_json'),  # GIN index will be created via migration
    )


class Image(Base):
    __tablename__ = 'images'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sha256 = Column(CHAR(64), unique=True, nullable=False)
    mime_type = Column(String(50), nullable=False)
    bytes = Column(BYTEA, nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)
    thumbnail = Column(BYTEA)  # Optional thumbnail
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    news = relationship("News", secondary=news_images_association, back_populates="images")

    __table_args__ = (
        Index('idx_images_sha256', 'sha256'),
    )


class Entity(Base):
    __tablename__ = 'entities'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_id = Column(UUID(as_uuid=True), ForeignKey('news.id', ondelete='CASCADE'), nullable=False)
    type = Column(String(20), nullable=False)  # ORG, DATE, PCT, AMOUNT, etc
    text = Column(Text, nullable=False)  # Original text
    norm = Column(JSONB)  # Normalized value/structure
    start_pos = Column(Integer)  # Character position in text
    end_pos = Column(Integer)
    confidence = Column(Float, default=1.0)

    # Relationships
    news = relationship("News", back_populates="entities")

    __table_args__ = (
        Index('idx_entities_news_type', 'news_id', 'type'),
        Index('idx_entities_type', 'type'),
    )


class LinkedCompany(Base):
    __tablename__ = 'linked_companies'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_id = Column(UUID(as_uuid=True), ForeignKey('news.id', ondelete='CASCADE'), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey('entities.id', ondelete='SET NULL'))

    # MOEX identifiers
    secid = Column(String(50))
    isin = Column(String(20))
    board = Column(String(20))
    name = Column(String(200), nullable=False)
    short_name = Column(String(100))

    confidence = Column(Float, default=1.0)
    is_traded = Column(Boolean, default=True)
    match_method = Column(String(50))  # exact, alias, fuzzy, sector

    # Relationships
    news = relationship("News", back_populates="linked_companies")

    __table_args__ = (
        Index('idx_linked_companies_news', 'news_id'),
        Index('idx_linked_companies_secid', 'secid'),
        Index('idx_linked_companies_isin', 'isin'),
    )


class Topic(Base):
    __tablename__ = 'topics'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_id = Column(UUID(as_uuid=True), ForeignKey('news.id', ondelete='CASCADE'), nullable=False)
    topic = Column(String(50), nullable=False)  # macro, oil_gas, metals_titanium, etc
    confidence = Column(Float, default=1.0)

    # Relationships
    news = relationship("News", back_populates="topics")

    __table_args__ = (
        UniqueConstraint('news_id', 'topic', name='uq_news_topic'),
        Index('idx_topics_news', 'news_id'),
        Index('idx_topics_topic', 'topic'),
    )


class SectorConstituent(Base):
    __tablename__ = 'sector_constituents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sector_code = Column(String(50), nullable=False)  # oil_gas, metals, banks, etc
    secid = Column(String(50), nullable=False)
    isin = Column(String(20))
    board = Column(String(20))
    name = Column(String(200), nullable=False)
    weight = Column(Float)  # Weight in sector index if available
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('sector_code', 'secid', name='uq_sector_secid'),
        Index('idx_sector_constituents_sector', 'sector_code'),
        Index('idx_sector_constituents_secid', 'secid'),
    )


class CompanyAlias(Base):
    __tablename__ = 'company_aliases'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    secid = Column(String(50), nullable=False)
    alias = Column(String(200), nullable=False)
    alias_normalized = Column(String(200), nullable=False)
    lang = Column(String(10), default='ru')
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('alias_normalized', 'secid', name='uq_alias_secid'),
        Index('idx_company_aliases_secid', 'secid'),
        Index('idx_company_aliases_normalized', 'alias_normalized'),
    )


class OutboxEvent(Base):
    __tablename__ = 'outbox'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)  # news.created, news.updated
    aggregate_id = Column(UUID(as_uuid=True), ForeignKey('news.id', ondelete='CASCADE'))
    payload_json = Column(JSONB, nullable=False)
    status = Column(String(20), default='pending')
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))

    # Relationships
    news = relationship("News", back_populates="outbox_events")

    __table_args__ = (
        Index('idx_outbox_status_next_retry', 'status', 'next_retry_at'),
        Index('idx_outbox_created_at', 'created_at'),
    )


class ParserState(Base):
    __tablename__ = 'parser_states'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey('sources.id'), unique=True, nullable=False)
    last_parsed_at = Column(DateTime(timezone=True))
    last_external_id = Column(String(500))  # Last processed item ID
    cursor_data = Column(JSONB)  # Any state needed for pagination
    backfill_completed = Column(Boolean, default=False)
    backfill_started_at = Column(DateTime(timezone=True))
    backfill_completed_at = Column(DateTime(timezone=True))
    error_count = Column(Integer, default=0)
    last_error = Column(Text)
    last_error_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    source = relationship("Source", back_populates="parser_state")

    __table_args__ = (
        Index('idx_parser_states_source', 'source_id'),
    )


class Event(Base):
    """
    События, извлечённые из новостей для CEG (Causal Event Graph)
    """
    __tablename__ = 'events'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    news_id = Column(UUID(as_uuid=True), ForeignKey('news.id', ondelete='CASCADE'), nullable=False)

    # Основные атрибуты события
    event_type = Column(String(100), nullable=False)  # sanctions, rate_hike, earnings, etc.
    title = Column(Text, nullable=False)
    ts = Column(DateTime(timezone=True), nullable=False)  # Время события

    # Дополнительные атрибуты (JSON)
    attrs = Column(JSONB, default={})  # {companies: [], tickers: [], metrics: [], people: []}

    # CEG атрибуты
    is_anchor = Column(Boolean, default=False)  # Является ли якорным событием
    confidence = Column(Float, default=0.8)  # Уверенность в извлечении

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    news = relationship("News", foreign_keys=[news_id])
    importance_scores = relationship("EventImportance", back_populates="event", cascade="all, delete-orphan")
    triggered_watches = relationship("TriggeredWatch", back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_events_news', 'news_id'),
        Index('idx_events_type', 'event_type'),
        Index('idx_events_ts', 'ts'),
        Index('idx_events_is_anchor', 'is_anchor'),
        Index('idx_events_type_ts', 'event_type', 'ts'),
    )


class EventImportance(Base):
    """
    Важность событий - результаты расчета Importance Score
    """
    __tablename__ = 'event_importance'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False)

    # Основная оценка важности
    importance_score = Column(Float, nullable=False)  # Общий балл важности [0, 1]

    # Компоненты важности
    novelty = Column(Float, nullable=False)           # Новизна события
    burst = Column(Float, nullable=False)            # Частота упоминания
    credibility = Column(Float, nullable=False)       # Надежность источника
    breadth = Column(Float, nullable=False)           # Широта охвата
    price_impact = Column(Float, nullable=False)     # Рыночное влияние

    # Детали расчета
    components_details = Column(JSONB)  # Детали компонентов
    calculation_timestamp = Column(DateTime(timezone=True), nullable=False)
    weights_version = Column(String(50))  # Версия весов для пересчета

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    event = relationship("Event", back_populates="importance_scores")

    __table_args__ = (
        Index('ix_event_importance_event_id', 'event_id'),
        Index('ix_event_importance_score', 'importance_score'),
        Index('ix_event_importance_timestamp', 'calculation_timestamp'),
    )


class TriggeredWatch(Base):
    """
    Сработавшие watcher'ы событий (L0/L1/L2 мониторинг)
    """
    __tablename__ = 'triggered_watches'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


    rule_id = Column(String(100), nullable=False)          # ID правила мониторинга
    rule_name = Column(String(200), nullable=False)       # Название правила
    watch_level = Column(String(10), nullable=False)      # L0, L1, L2
    event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False)

    # Временные метки
    trigger_time = Column(DateTime(timezone=True), nullable=False)
    auto_expire_at = Column(DateTime(timezone=True), nullable=False)

    # Статус и уведомления
    status = Column(String(20), nullable=False, default='triggered')  # triggered, notified, expired
    notifications_sent = Column(Boolean, nullable=False, default=False)

    # Данные контекста
    context = Column(JSONB)      # Контекст срабатывания
    alerts = Column(JSONB)       # Список для уведомлений

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    notified_at = Column(DateTime(timezone=True))

    # Relationships
    event = relationship("Event", back_populates="triggered_watches")
    predictions = relationship("EventPrediction", back_populates="triggered_watch", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_triggered_watches_rule_id', 'rule_id'),
        Index('ix_triggered_watches_level', 'watch_level'),
        Index('ix_triggered_watches_event_id', 'event_id'),
        Index('ix_triggered_watches_trigger_time', 'trigger_time'),
        Index('ix_triggered_watches_status', 'status'),
    )


class EventPrediction(Base):
    """
    Прогнозы событий на основе L2 watcher'ов
    """
    __tablename__ = 'event_predictions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watch_id = Column(UUID(as_uuid=True), ForeignKey('triggered_watches.id', ondelete='CASCADE'), nullable=False)
    base_event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='CASCADE'), nullable=False)

    # Данные прогноза
    predicted_event_type = Column(String(100), nullable=False)
    prediction_probability = Column(Float, nullable=False)          # [0, 1]
    prediction_window_days = Column(Integer, nullable=False)
    target_date_estimate = Column(DateTime(timezone=True), nullable=False)
    description = Column(Text)

    # Статус прогноза
    status = Column(String(20), nullable=False, default='pending')  # pending, fulfilled, expired
    fulfilled_at = Column(DateTime(timezone=True))
    actual_event_id = Column(UUID(as_uuid=True), ForeignKey('events.id', ondelete='SET NULL'))

    # Контекст прогноза
    prediction_context = Column(JSONB)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    triggered_watch = relationship("TriggeredWatch", back_populates="predictions")
    base_event = relationship("Event", foreign_keys=[base_event_id])
    actual_event = relationship("Event", foreign_keys=[actual_event_id])

    __table_args__ = (
        Index('ix_event_predictions_watch_id', 'watch_id'),
        Index('ix_event_predictions_base_event_id', 'base_event_id'),
        Index('ix_event_predictions_status', 'status'),
        Index('ix_event_predictions_target_date', 'target_date_estimate'),
    )