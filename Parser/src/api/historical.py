"""
API для загрузки исторических новостей
Сохраняет совместимость для интеграции с нейронками
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from Parser.src.core.database import get_db
from Parser.src.graph_models import GraphService, News, NewsType
from Parser.src.services.impact_calculator import ImpactCalculator
from Parser.src.services.covariance_service import CovarianceService

router = APIRouter(prefix="/historical", tags=["historical"])


class HistoricalLoadRequest(BaseModel):
    """Запрос на загрузку исторических данных"""
    source: str = Field(..., description="Источник новостей")
    date_from: date = Field(..., description="Начальная дата")
    date_to: date = Field(..., description="Конечная дата")
    process_impact: bool = Field(True, description="Рассчитывать влияние на рынок")
    spread_correlation: bool = Field(True, description="Распространять эффект по корреляциям")
    batch_size: int = Field(100, ge=1, le=1000)


class NewsItem(BaseModel):
    """Элемент новости для загрузки"""
    url: str
    title: str
    text: str
    published_at: datetime
    source: str
    companies: Optional[List[str]] = None  # Тикеры или ID компаний
    markets: Optional[List[str]] = None   # Коды рынков


class BulkLoadRequest(BaseModel):
    """Массовая загрузка новостей"""
    items: List[NewsItem]
    process_impact: bool = True
    spread_correlation: bool = True


class HistoricalLoadResponse(BaseModel):
    """Ответ о загрузке"""
    job_id: str
    status: str
    message: str
    stats: Optional[Dict[str, Any]] = None


@router.post("/load", response_model=HistoricalLoadResponse)
async def load_historical_news(
    request: HistoricalLoadRequest,
    background_tasks: BackgroundTasks,
    graph: GraphService = Depends(get_graph_service)
):
    """
    Загрузка исторических новостей из источника
    Согласно п.3 Project Charter
    """
    
    # Создаем задачу
    job_id = str(uuid4())
    
    # Запускаем в фоне
    background_tasks.add_task(
        process_historical_load,
        job_id=job_id,
        request=request,
        graph=graph
    )
    
    return HistoricalLoadResponse(
        job_id=job_id,
        status="started",
        message=f"Loading news from {request.source} between {request.date_from} and {request.date_to}"
    )


@router.post("/bulk", response_model=HistoricalLoadResponse)
async def bulk_load_news(
    request: BulkLoadRequest,
    background_tasks: BackgroundTasks,
    graph: GraphService = Depends(get_graph_service)
):
    """
    Массовая загрузка новостей через API
    Для интеграции с внешними системами и нейронками
    """
    
    job_id = str(uuid4())
    
    background_tasks.add_task(
        process_bulk_load,
        job_id=job_id,
        items=request.items,
        process_impact=request.process_impact,
        spread_correlation=request.spread_correlation,
        graph=graph
    )
    
    return HistoricalLoadResponse(
        job_id=job_id,
        status="started",
        message=f"Loading {len(request.items)} news items",
        stats={"total_items": len(request.items)}
    )


async def process_historical_load(
    job_id: str,
    request: HistoricalLoadRequest,
    graph: GraphService
):
    """
    Обработка исторической загрузки
    Конвейер согласно п.3.1 Project Charter
    """
    
    logger.info(f"Starting historical load job {job_id}")
    
    try:
        stats = {
            "total": 0,
            "processed": 0,
            "with_impact": 0,
            "correlations_spread": 0,
            "errors": 0
        }
        
        # 1. Получаем исторические новости из источника
        news_items = await fetch_historical_news(
            request.source,
            request.date_from,
            request.date_to,
            request.batch_size
        )
        
        stats["total"] = len(news_items)
        
        # 2. Обрабатываем батчами
        for batch_start in range(0, len(news_items), request.batch_size):
            batch = news_items[batch_start:batch_start + request.batch_size]
            
            for item in batch:
                try:
                    # 3. Создаем новость в графе
                    news = News(
                        id=News.generate_id(item["url"]),
                        url=item["url"],
                        title=item["title"],
                        text=item["text"],
                        lang_orig=item.get("lang", "ru"),
                        lang_norm="ru",
                        published_at=item["published_at"],
                        source=item["source"],
                        news_type=classify_news_type(item)
                    )
                    
                    await graph.upsert_news(news)
                    
                    # 4. Оценка влияния на компании
                    if request.process_impact and item.get("companies"):
                        impact_calc = ImpactCalculator(market_data_service)
                        
                        for company_id in item["companies"]:
                            affects, no_impact = await impact_calc.calculate_impact(
                                news.published_at,
                                company_id
                            )
                            
                            if affects and not no_impact:
                                await graph.link_news_to_company(
                                    news.id,
                                    company_id,
                                    affects
                                )
                                stats["with_impact"] += 1
                                
                                # 5. Распространение по корреляциям
                                if request.spread_correlation:
                                    spread_results = await graph.spread_impact(
                                        news.id,
                                        company_id,
                                        max_depth=2
                                    )
                                    stats["correlations_spread"] += len(spread_results)
                    
                    stats["processed"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing news {item.get('url')}: {e}")
                    stats["errors"] += 1
            
            # Логируем прогресс
            logger.info(f"Job {job_id}: Processed {stats['processed']}/{stats['total']} news")
        
        logger.info(f"Historical load job {job_id} completed: {stats}")
        
        # TODO: Сохранить статус задачи в БД
        
    except Exception as e:
        logger.error(f"Failed job {job_id}: {e}")


async def fetch_historical_news(
    source: str,
    date_from: date,
    date_to: date,
    limit: int
) -> List[Dict]:
    """
    Получение исторических новостей из источника
    """
    
    # В реальности - запрос к архиву источника
    # Здесь - заглушка
    
    if source.startswith("telegram:"):
        # Загрузка из Telegram архива
        channel = source.replace("telegram:", "")
        # TODO: Использовать Telethon iter_messages с датами
        pass
    elif source == "rbc":
        # Парсинг архива РБК
        # TODO: Реализовать парсер
        pass
    elif source == "e-disclosure":
        # API e-disclosure
        # TODO: Интеграция с API
        pass
    
    return []


def classify_news_type(news_item: Dict) -> NewsType:
    """
    Классификация типа новости
    """
    
    # Простая rule-based классификация
    # В продакшене - ML модель
    
    text_lower = (news_item.get("title", "") + " " + news_item.get("text", "")).lower()
    
    # Проверка на рыночные новости
    market_keywords = ["рынок", "биржа", "индекс", "moex", "ртс", "центробанк", "ставка"]
    if any(kw in text_lower for kw in market_keywords):
        return NewsType.MARKET
    
    # Проверка на регуляторные
    regulatory_keywords = ["регулятор", "цб рф", "закон", "постановление", "указ"]
    if any(kw in text_lower for kw in regulatory_keywords):
        return NewsType.REGULATORY
    
    # По умолчанию - новость об одной компании
    return NewsType.ONE_COMPANY


async def get_graph_service() -> GraphService:
    """Dependency для получения GraphService"""
    return GraphService(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
