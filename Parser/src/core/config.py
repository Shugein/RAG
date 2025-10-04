# src/core/config.py

from typing import Optional, Dict, Any, List
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://newsuser:newspass@host.docker.internal:5432/newsdb",
        description="PostgreSQL connection URL"
    )
    DB_POOL_SIZE: int = Field(default=20, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=40, ge=0, le=200)
    DB_POOL_TIMEOUT: float = Field(default=30.0, ge=1.0)

    # RabbitMQ
    RABBITMQ_URL: str = Field(
        default="amqp://admin:admin123@localhost:5672/",
        description="RabbitMQ connection URL"
    )
    RABBITMQ_EXCHANGE: str = Field(default="news")
    RABBITMQ_PREFETCH_COUNT: int = Field(default=10, ge=1)

    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    REDIS_TTL: int = Field(default=3600, description="Default TTL in seconds")

    # Neo4j Graph Database
    NEO4J_URI: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI"
    )
    NEO4J_USER: str = Field(default="neo4j", description="Neo4j username")
    NEO4J_PASSWORD: str = Field(default="password", description="Neo4j password")
    NEO4J_DATABASE: str = Field(default="neo4j", description="Neo4j database name")

    # Telegram
    TELETHON_API_ID: int = Field(description="Telegram API ID from my.telegram.org")
    TELETHON_API_HASH: str = Field(description="Telegram API Hash")
    TELETHON_SESSION_NAME: str = Field(default="news_parser")
    TELETHON_PHONE: str = Field(description="Phone number with country code")
    TELEGRAM_BATCH_SIZE: int = Field(default=100, ge=10, le=1000)
    TELEGRAM_BACKFILL_DAYS: int = Field(default=365, ge=1, le=365)

    # Algopack API
    ALGOPACK_API_KEY: str = Field(description="Algopack API key")
    ALGOPACK_BASE_URL: str = Field(
        default="https://api.algopack.com/v1",
        description="Algopack API base URL"
    )

    # Parsing
    PARSER_WORKERS: int = Field(default=4, ge=1, le=20)
    PARSER_POLL_INTERVAL: int = Field(default=60, description="Seconds between polls")
    PARSER_BACKOFF_FACTOR: float = Field(default=2.0, ge=1.0)
    PARSER_MAX_RETRIES: int = Field(default=3, ge=1, le=10)

    # Enrichment
    ENRICHER_BATCH_SIZE: int = Field(default=20, ge=1, le=100)
    ENRICHER_WORKERS: int = Field(default=2, ge=1, le=10)
    NER_CONFIDENCE_THRESHOLD: float = Field(default=0.7, ge=0.0, le=1.0)
    COMPANY_MATCH_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)

    # Anti-spam
    ANTISPAM_THRESHOLD: float = Field(default=5.0, ge=0.0)
    ANTISPAM_TRUSTED_THRESHOLD: float = Field(default=8.0, ge=0.0)

    # API
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000, ge=1024, le=65535)
    API_WORKERS: int = Field(default=4, ge=1)
    API_CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )
    API_PAGE_SIZE: int = Field(default=50, ge=1, le=200)
    API_MAX_PAGE_SIZE: int = Field(default=200, ge=1, le=1000)

    # Images
    IMAGE_MAX_SIZE_MB: int = Field(default=15, ge=1, le=50)
    IMAGE_THUMBNAIL_SIZE: tuple = Field(default=(400, 400))
    IMAGE_ALLOWED_TYPES: List[str] = Field(
        default=["image/jpeg", "image/png", "image/webp", "image/gif"]
    )

    # Monitoring
    METRICS_PORT: int = Field(default=9090, ge=1024, le=65535)
    LOG_LEVEL: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = Field(default="json", pattern="^(json|text)$")

    # Paths
    CONFIG_DIR: Path = Field(default=Path("config"))
    SESSIONS_DIR: Path = Field(default=Path("sessions"))
    MODELS_DIR: Path = Field(default=Path("models"))

    # Feature flags
    ENABLE_TELEGRAM: bool = Field(default=True)
    ENABLE_HTML_PARSER: bool = Field(default=True)
    ENABLE_ENRICHMENT: bool = Field(default=True)
    ENABLE_ANTISPAM: bool = Field(default=True)
    ENABLE_METRICS: bool = Field(default=True)

    # Development
    DEBUG: bool = Field(default=False)
    TESTING: bool = Field(default=False)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("CONFIG_DIR", "SESSIONS_DIR", "MODELS_DIR")
    @classmethod
    def ensure_dir_exists(cls, v: Path) -> Path:
        """Ensure directory exists"""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure async driver for PostgreSQL"""
        if "postgresql://" in v and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://")
        return v


# Singleton instance
settings = Settings()