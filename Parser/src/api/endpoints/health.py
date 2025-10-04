# src/api/endpoints/health.py
"""
Health check endpoints
"""

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db, check_connection
from src.api.schemas import HealthResponse
import aio_pika
import redis.asyncio as redis
from src.core.config import settings

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Проверка здоровья всех компонентов системы"""
    
    # Проверяем БД
    db_ok = await check_connection()
    
    # Проверяем RabbitMQ
    rabbit_ok = False
    try:
        connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL,
            timeout=5.0
        )
        await connection.close()
        rabbit_ok = True
    except:
        pass
    
    # Проверяем Redis
    redis_ok = False
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        redis_ok = True
    except:
        pass
    
    # Общий статус
    all_ok = db_ok and rabbit_ok and redis_ok
    
    return HealthResponse(
        status="healthy" if all_ok else "degraded",
        database=db_ok,
        rabbitmq=rabbit_ok,
        redis=redis_ok,
        timestamp=datetime.utcnow(),
        version="1.0.0"
    )


@router.get("/ready")
async def readiness_check():
    """Проверка готовности к работе"""
    db_ok = await check_connection()
    
    if not db_ok:
        return {"ready": False, "reason": "Database not available"}, 503
    
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """Проверка что сервис жив"""
    return {"alive": True}
