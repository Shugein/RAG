import logging
import asyncio
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload

from src.core.models import News, Event, EventImportance, TriggeredWatch, EventPrediction
from src.core.database import get_session as get_db_session
from src.services.events.ceg_realtime_service import CEGRealtimeService
from src.services.events.event_extractor import EventExtractor
from src.graph_models import GraphService, EventNode

logger = logging.getLogger(__name__)


@dataclass
class BackfillTask:
    """Задача для исторической загрузки"""
    task_id: str
    source_ids: List[str]  # Источники новостей
    start_date: datetime
    end_date: datetime
    quality_threshold: float  # Порог качества данных
    priority: str  # high, medium, low
    status: str  # pending, running, completed, failed
    progress: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class HistoricalBackfillService:
    """
    Сервис для исторической загрузки и обработки событий
    
    Обрабатывает новости из прошлого и строит на их основе CEG
    """
    
    def __init__(self, session: AsyncSession, graph_service: GraphService):
        self.session = session
        self.graph = graph_service
        self.backfill_tasks: Dict[str, BackfillTask] = {}
        
        # Конфигурация
        self.batch_size = 50  # Размер батча для обработки
        self.max_concurrent_tasks = 3
        self.quality_thresholds = {
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4
        }
        
        # Статистики
        self.stats = {
            'tasks_completed': 0,
            'events_processed': 0,
            'news_batches_processed': 0,
            'total_processing_time_hours': 0,
            'average_events_per_batch': 0,
            'failed_tasks': 0
        }
        
        # Инициализация компонентов CEG
        self.ceg_service = CEGRealtimeService(
            session=session,
            graph_service=graph_service,
            enable_watchers=True,
            enable_predictions=True
        )
    
    async def create_backfill_task(
        self,
        source_ids: List[str],
        start_date: datetime,
        end_date: datetime,
        priority: str = 'medium',
        quality_threshold: Optional[float] = None
    ) -> str:
        """
        Создать задачу исторической загрузки
        
        Args:
            source_ids: Список ID источников для обработки
            start_date: Начальная дата
            end_date: Конечная дата
            priority: Приоритет задачи
            quality_threshold: Порог качества данных
            
        Returns:
            task_id: ID созданной задачи
        """
        task_id = f"backfill_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        if quality_threshold is None:
            quality_threshold = self.quality_thresholds.get(priority, 0.6)
        
        task = BackfillTask(
            task_id=task_id,
            source_ids=source_ids.copy(),
            start_date=start_date,
            end_date=end_date,
            quality_threshold=quality_threshold,
            priority=priority,
            status='pending',
            progress={
                'total_news': 0,
                'processed_news': 0,
                'events_created': 0,
                'current_batch': 0,
                'total_batches': 0
            },
            created_at=datetime.utcnow()
        )
        
        # Валидация параметров
        validation_result = await self._validate_backfill_parameters(task)
        if not validation_result['valid']:
            task.status = 'failed'
            task.error_message = validation_result['error']
            return task_id
        
        self.backfill_tasks[task_id] = task
        
        logger.info(f"Created backfill task {task_id}: "
                   f"{len(source_ids)} sources, "
                   f"{start_date.date()} to {end_date.date()}, "
                   f"priority {priority}")
        
        return task_id
    
    async def execute_backfill_task(self, task_id: str) -> Dict[str, Any]:
        """
        Выполнить задачу исторической загрузки
        
        Args:
            task_id: ID задачи для выполнения
            
        Returns:
            Результат выполнения задачи
        """
        if task_id not in self.backfill_tasks:
            return {"error": f"Task {task_id} not found"}
        
        task = self.backfill_tasks[task_id]
        
        if task.status != 'pending':
            return {"error": f"Task {task_id} is already {task.status}"}
        
        task.status = 'running'
        task.started_at = datetime.utcnow()
        
        try:
            logger.info(f"Starting backfill task {task_id}")
            
            # Подсчитываем общее количество новостей
            total_news = await self._count_news_in_range(
                task.source_ids, task.start_date, task.end_date
            )
            
            task.progress['total_news'] = total_news
            task.progress['total_batches'] = (total_news + self.batch_size - 1) // self.batch_size
            
            if total_news == 0:
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                return {"message": "No news found in specified range", "task_status": "completed"}
            
            logger.info(f"Processing {total_news} news articles in {task.progress['total_batches']} batches")
            
            # Обрабатываем новости батчами
            total_events = 0
            processed_news = 0
            
            for batch_num in range(task.progress['total_batches']):
                try:
                    batch_result = await self._process_news_batch(
                        task, batch_num
                    )
                    
                    processed_news += batch_result['processed_count']
                    total_events += batch_result['events_created']
                    
                    task.progress['processed_news'] = processed_news
                    task.progress['events_created'] = total_events
                    task.progress['current_batch'] = batch_num + 1
                    
                    logger.info(f"Batch {batch_num + 1}/{task.progress['total_batches']} completed: "
                               f"{batch_result['processed_count']} news, "
                               f"{batch_result['events_created']} events")
                    
                except Exception as e:
                    logger.error(f"Error processing batch {batch_num} for task {task_id}: {e}")
                    continue
            
            # Обновляем статистики
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            
            processing_time = (task.completed_at - task.started_at).total_seconds() / 3600
            self.stats['tasks_completed'] += 1
            self.stats['events_processed'] += total_events
            self.stats['news_batches_processed'] += task.progress['total_batches']
            self.stats['total_processing_time_hours'] += processing_time
            
            if self.stats['news_batches_processed'] > 0:
                self.stats['average_events_per_batch'] = (
                    self.stats['events_processed'] / 
                    self.stats['news_batches_processed']
                )
            
            logger.info(f"Backfill task {task_id} completed successfully: "
                       f"{processed_news} news, {total_events} events "
                       f"in {processing_time:.2f} hours")
            
            return {
                "task_id": task_id,
                "status": "completed",
                "processed_news": processed_news,
                "total_news": total_news,
                "events_created": total_events,
                "processing_time_hours": processing_time,
                "average_events_per_news": total_events / max(1, processed_news),
                "completion_timestamp": task.completed_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Backfill task {task_id} failed: {e}", exc_info=True)
            task.status = 'failed'
            task.error_message = str(e)
            self.stats['failed_tasks'] += 1
            
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "failed_timestamp": datetime.utcnow().isoformat()
            }
    
    async def _validate_backfill_parameters(self, task: BackfillTask) -> Dict[str, Any]:
        """Валидация параметров задачи загрузки"""
        
        # Проверяем корректность дат
        if task.start_date >= task.end_date:
            return {"valid": False, "error": "Start date must be before end date"}
        
        timedelta_days = (task.end_date - task.start_date).days
        if timedelta_days > 365:  # Ограничение на год
            return {"valid": False, "error": "Date range exceeds maximum 365 days"}
        
        # Проверяем источники
        if not task.source_ids:
            return {"valid": False, "error": "At least one source must be specified"}
        
        # Проверяем существование источников
        existing_sources = await self.session.execute(
            select(News.source_id)
            .where(News.source_id.in_(task.source_ids))
            .group_by(News.source_id)
        )
        
        valid_sources = {row.source_id for row in existing_sources}
        invalid_sources = set(task.source_ids) - valid_sources
        
        if invalid_sources:
            return {
                "valid": False,
                "error": f"Invalid source IDs: {list(invalid_sources)}"
            }
        
        return {"valid": True}
    
    async def _count_news_in_range(
        self,
        source_ids: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> int:
        """Подсчитать количество новостей в диапазоне дат"""
        
        result = await self.session.execute(
            select(func.count(News.id))
            .where(
                and_(
                    News.source_id.in_(source_ids),
                    News.published_at >= start_date,
                    News.published_at <= end_date,
                    News.is_ad == False  # Исключаем рекламу
                )
            )
        )
        
        return result.scalar() or 0
    
    async def _process_news_batch(
        self,
        task: BackfillTask,
        batch_num: int
    ) -> Dict[str, Any]:
        """Обработать батч новостей"""
        
        offset = batch_num * self.batch_size
        
        # Получаем новости для этого батча
        news_result = await self.session.execute(
            select(News)
            .where(
                and_(
                    News.source_id.in_(task.source_ids),
                    News.published_at >= task.start_date,
                    News.published_at <= task.end_date,
                    News.is_ad == False
                )
            )
            .order_by(News.published_at)
            .offset(offset)
            .limit(self.batch_size)
        )
        
        news_items = news_result.scalars().all()
        
        if not news_items:
            return {"processed_count": 0, "events_created": 0}
        
        events_created = 0
        
        # Обрабатываем каждую новость
        for news in news_items:
            try:
                # Извлекаем события из новости
                events = await self._extract_events_from_news(news)
                
                if not events:
                    continue
                
                # Обрабатываем каждое событие через CEG сервис
                for event in events:
                    # Создаем AI extraction результат для совместимости
                    ai_extracted = {
                        'entities': self._extract_entities_from_event(event),
                        'companies': event.attrs.get('companies', []),
                        'metrics': event.attrs.get('metrics', [])
                    }
                    
                    # Обрабатываем событие через CEG
                    result = await self.ceg_service.process_news(news, ai_extracted)
                    
                    events_in_result = result.get('events', [])
                    events_created += len(events_in_result)
                    
            except Exception as e:
                logger.error(f"Error processing news {news.id}: {e}")
                continue
        
        return {
            "processed_count": len(news_items),
            "events_created": events_created,
            "batch_start_date": news_items[0].published_at.isoformat(),
            "batch_end_date": news_items[-1].published_at.isoformat()
        }
    
    async def _extract_events_from_news(self, news: News) -> List[Event]:
        """Извлечь события из новости"""
        
        # Используем EventExtractor для извлечения событий
        event_extractor = EventExtractor()
        
        # Простой extraction для случая backfill
        # В реальной реализации здесь должен быть более сложный логика
        events = []
        
        # Проверяем, есть ли уже извлеченные события для этой новости
        existing_events = await self.session.execute(
            select(Event).where(Event.news_id == news.id)
        )
        existing_events_list = existing_events.scalars().all()
        
        if existing_events_list:
            # Если события уже есть, используем их
            return existing_events_list
        
        # Создаем базовое событие для новости если его нет
        basic_event = Event(
            id=str(uuid.uuid4()),
            news_id=news.id,
            event_type='general_news',
            title=news.title,
            ts=news.published_at,
            attrs={
                'companies': [],
                'tickers': [],
                'metrics': [],
                'people': []
            },
            is_anchor=False,
            confidence=0.5
        )
        
        # Сохраняем событие
        self.session.add(basic_event)
        await self.session.flush()
        
        return [basic_event]
    
    def _extract_entities_from_event(self, event: Event) -> List[Dict[str, Any]]:
        """Извлечь сущности из события"""
        
        entities = []
        
        # Простое извлечение сущностей для обратной совместимости
        if event.attrs:
            companies = event.attrs.get('companies', [])
            for company in companies:
                entities.append({
                    'text': company,
                    'type': 'ORG',
                    'norm': {'company_name': company}
                })
        
        return entities
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о задаче"""
        
        if task_id not in self.backfill_tasks:
            return None
        
        task = self.backfill_tasks[task_id]
        
        return {
            "task_id": task.task_id,
            "source_count": len(task.source_ids),
            "start_date": task.start_date.isoformat(),
            "end_date": task.end_date.isoformat(),
            "priority": task.priority,
            "quality_threshold": task.quality_threshold,
            "status": task.status,
            "progress": task.progress.copy(),
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message
        }
    
    def get_all_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить все задачи или отфильтрованные по статусу"""
        
        tasks = list(self.backfill_tasks.values())
        
        if status:
            tasks = [task for task in tasks if task.status == status]
        
        return [self.get_task_by_id(task.task_id) for task in tasks]
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Отменить задачу"""
        
        if task_id not in self.backfill_tasks:
            return {"error": f"Task {task_id} not found"}
        
        task = self.backfill_tasks[task_id]
        
        if task.status not in ['pending', 'running']:
            return {"error": f"Cannot cancel task with status {task.status}"}
        
        task.status = 'cancelled'
        
        logger.info(f"Cancelled backfill task {task_id}")
        
        return {"message": f"Task {task_id} cancelled successfully"}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистики сервиса"""
        
        current_tasks = {
            "pending": len([t for t in self.backfill_tasks.values() if t.status == 'pending']),
            "running": len([t for t in self.backfill_tasks.values() if t.status == 'running']),
            "completed": len([t for t in self.backfill_tasks.values() if t.status == 'completed']),
            "failed": len([t for t in self.backfill_tasks.values() if t.status == 'failed']),
            "cancelled": len([t for t in self.backfill_tasks.values() if t.status == 'cancelled'])
        }
        
        return {
            "backfill_service_stats": self.stats.copy(),
            "task_counts": current_tasks,
            "total_tasks": len(self.backfill_tasks),
            "service_config": {
                "batch_size": self.batch_size,
                "max_concurrent_tasks": self.max_concurrent_tasks,
                "quality_thresholds": self.quality_thresholds
            },
            "status": "operational"
        }
