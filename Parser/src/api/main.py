from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app

from src.core.config import settings
from src.core.database import init_db, close_db
from src.api.endpoints import news, sources, health, jobs, ceg, importance, watchers
from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    setup_logging()
    logger.info("Starting News Aggregator API")
    await init_db()
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Aggregator API")
    await close_db()


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="News Aggregator API",
        description="Financial news aggregation and enrichment service",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.API_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handlers
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)}
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    # Include routers
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(news.router, prefix="/news", tags=["news"])
    app.include_router(sources.router, prefix="/sources", tags=["sources"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(ceg.router, tags=["ceg"])
    app.include_router(importance.router, tags=["importance"])
    app.include_router(watchers.router, tags=["watchers"])
    
    # Mount metrics endpoint
    if settings.ENABLE_METRICS:
        metrics_app = make_asgi_app()
        app.mount("/metrics", metrics_app)
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=settings.API_WORKERS,
        reload=settings.DEBUG
    )

