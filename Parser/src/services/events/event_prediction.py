import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, or_

from src.core.models import Event, TriggeredWatch, EventPrediction, EventImportance
from src.graph_models import GraphService, EventNode

logger = logging.getLogger(__name__)


class EventPredictionEngine:
    """
    Движок предсказания событий на основе CEG и исторических паттернов
    """
    
    def __init__(self, session: AsyncSession, graph_service: GraphService):
        self.session = session
        self.graph = graph_service
        
        # Конфигурация различных типов предсказаний
        self.prediction_patterns = {
            'follow_up_events': {
                'patterns': [
                    ('sanctions', ['sanctions_compliance', 'trade_restrictions', 'banking_limitations']),
                    ('rate_hike', ['rate_cut', 'inflation_response', 'market_volatility']),
                    ('earnings_beat', ['guidance_update', 'dividend_increase', 'stock_split']),
                    ('merger', ['regulatory_approval', 'shareholder_vote', 'integration_updates'])
                ],
                'probabilities': [0.7, 0.4, 0.3],  # Высокая, средняя, низкая вероятность
                'windows_days': [7, 14, 30]  # Короткое, среднее, длинное окно
            },
            'market_reactions': {
                'patterns': [
                    ('volatility_spike', ['index_movements', 'currency_changes', 'bond_yields']),
                    ('sector_impact', ['related_companies', 'supply_chain_disruptions']),
                    ('regulatory_response', ['policy_changes', 'enforcement_actions'])
                ],
                'probabilities': [0.6, 0.5, 0.3],
                'windows_days': [3, 7, 14]
            },
            'timing_patterns': {
                'patterns': [
                    ('quarterly_patterns', ['earnings', 'guidance', 'regulatory_filing']),
                    ('monthly_patterns', ['rate_decisions', 'policy_updates']),
                    ('weekly_patterns', ['trading_updates', 'announcements'])
                ],
                'probabilities': [0.8, 0.6, 0.4],
                'windows_days': [5, 10, 21]
            }
        }
        
        # Статистики системы
        self.prediction_stats = {
            'predictions_generated': 0,
            'predictions_fulfilled': 0,
            'predictions_expired': 0,
            'accuracy_by_type': {},
            'avg_prediction_horizon': 0.0
        }
    
    async def generate_l2_predictions(
        self, 
        triggered_watch: TriggeredWatch, 
        prediction_types: List[str] = None
    ) -> List[EventPrediction]:
        """
        Генерирует предсказания событий на основе L2 watcher'а
        
        Args:
            triggered_watch: Сработавший watcher уровня L2
            prediction_types: Типы предсказаний для генерации
            
        Returns:
            List[EventPrediction]: Список созданных предсказаний
        """
        logger.info(f"Generating L2 predictions for watch {triggered_watch.rule_id}")
        
        # Получаем базовое событие
        base_event_result = await self.session.execute(
            select(Event).where(Event.id == triggered_watch.event_id)
        )
        base_event = base_event_result.scalar_one_or_none()
        
        if not base_event:
            logger.error(f"Base event not found for watch {triggered_watch.rule_id}")
            return []
        
        predictions = []
        
        # Генерируем предсказания на основе типов
        prediction_types = prediction_types or ['follow_up_events', 'market_reactions']
        
        async for prediction in self._generate_predictions_for_event(
            base_event, 
            triggered_watch, 
            prediction_types
        ):
            predictions.append(prediction)
            # Сохраняем предсказание
            self.session.add(prediction)
        
        await self.session.flush()
        
        self.prediction_stats['predictions_generated'] += len(predictions)
        logger.info(f"Generated {len(predictions)} predictions for event {base_event.event_type}")
        
        return predictions
    
    async def _generate_predictions_for_event(
        self, 
        base_event: Event, 
        triggered_watch: TriggeredWatch, 
        prediction_types: List[str]
    ):
        """Генерирует предсказания для конкретного события"""
        
        # Анализируем исторические паттерны для данного типа события
        historical_patterns = await self._analyze_historical_patterns(base_event)
        
        # Анализируем CEG контекст события
        ceg_context = await self._analyze_ceg_context(base_event)
        
        for pred_type in prediction_types:
            if pred_type in self.prediction_patterns:
                pattern_config = self.prediction_patterns[pred_type]
                
                # Находим подходящие паттерны для события
                for event_pattern, predicted_types in pattern_config['patterns']:
                    if self._matches_event_pattern(base_event.event_type, event_pattern):
                        
                        # Генерируем предсказания для каждого типа через индексы
                        for i, predicted_event_type in enumerate(predicted_types):
                            if i < len(pattern_config['probabilities']):
                                
                                # Рассчитываем вероятность и окно на основе CEG контекста
                                probability_multiplier = await self._calculate_ceg_probability_multiplier(
                                    base_event, 
                                    predicted_event_type
                                )
                                
                                final_probability = min(0.95, 
                                    pattern_config['probabilities'][i] * probability_multiplier
                                )
                                
                                prediction_window = pattern_config['windows_days'][i]
                                target_date = datetime.utcnow() + timedelta(days=prediction_window)
                                
                                # Создаем предсказание
                                prediction = EventPrediction(
                                    watch_id=triggered_watch.id,
                                    base_event_id=base_event.id,
                                    predicted_event_type=predicted_event_type,
                                    prediction_probability=final_probability,
                                    prediction_window_days=prediction_window,
                                    target_date_estimate=target_date,
                                    description=f"Predicted based on {event_pattern} -> {predicted_event_type} pattern",
                                    status='pending',
                                    prediction_context={
                                        'prediction_type': pred_type,
                                        'pattern_used': event_pattern,
                                        'historical_support': historical_patterns.get(predicted_event_type, {}),
                                        'ceg_context': ceg_context,
                                        'probability_multiplier': probability_multiplier,
                                        'generation_timestamp': datetime.utcnow().isoformat()
                                    }
                                )
                                
                                logger.debug(f"Generated prediction: {prediction.predicted_event_type} "
                                           f"(prob: {prediction.prediction_probability:.3f}, "
                                           f"window: {prediction.prediction_window_days}d)")
                                
                                yield prediction
    
    async def _analyze_historical_patterns(self, base_event: Event) -> Dict[str, Any]:
        """Анализирует исторические паттерны для событий подобного типа"""
        
        # Находим события подобного типа за последние 90 дней
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        
        historical_events = await self.session.execute(
            select(Event)
            .where(
                and_(
                    Event.event_type == base_event.event_type,
                    Event.ts >= cutoff_date,
                    Event.id != base_event.id
                )
            )
            .order_by(desc(Event.ts))
            .limit(50)
        )
        
        events = historical_events.scalars().all()
        
        # Анализируем последовательности событий после каждого исторического события
        patterns = {}
        
        for event in events:
            # Находим события, произошедшие в течение 30 дней после этого события
            follow_ups = await self.session.execute(
                select(Event)
                .where(
                    and_(
                        Event.ts > event.ts,
                        Event.ts <= event.ts + timedelta(days=30),
                        Event.id != event.id
                    )
                )
                .order_by(Event.ts)
            )
            
            follow_up_events = follow_ups.scalars().all()
            
            # Группируем по типам событий
            for follow_up in follow_up_events:
                event_type = follow_up.event_type
                if event_type not in patterns:
                    patterns[event_type] = {
                        'count': 0,
                        'avg_delay_days': 0.0,
                        'frequency': 0.0
                    }
                
                patterns[event_type]['count'] += 1
                delay_days = (follow_up.ts - event.ts).days
                patterns[event_type]['avg_delay_days'] = (
                    (patterns[event_type]['avg_delay_days'] * (patterns[event_type]['count'] - 1) + delay_days) /
                    patterns[event_type]['count']
                )
        
        # Рассчитываем частоты
        total_events = len(events)
        for pattern_key in patterns:
            patterns[pattern_key]['frequency'] = patterns[pattern_key]['count'] / total_events
        
        logger.debug(f"Historical patterns for {base_event.event_type}: {len(patterns)} patterns found")
        
        return patterns
    
    async def _analyze_ceg_context(self, base_event: Event) -> Dict[str, Any]:
        """Анализирует контекст события в CEG"""
        
        try:
            # Получаем данные из графа Neo4j
            graph_context = await self.graph.get_event_context(str(base_event.id))
            
            if graph_context:
                return {
                    'connected_events': len(graph_context.get('causes', [])),
                    'impacting_events': len(graph_context.get('impacts', [])),
                    'cluster_size': len(graph_context.get('cluster', {}).get('events', [])),
                    'importance_context': graph_context.get('importance_rank', 0)
                }
            else:
                return {'connected_events': 0, 'impacting_events': 0, 'cluster_size': 0}
                
        except Exception as e:
            logger.error(f"Error analyzing CEG context: {e}")
            return {'connected_events': 0, 'impacting_events': 0, 'cluster_size': 0}
    
    def _matches_event_pattern(self, event_type: str, pattern: str) -> bool:
        """Проверяет соответствие типа события паттерну"""
        
        # Простое сопоставление для начала
        if pattern == 'sanctions' and 'sanctions' in event_type.lower():
            return True
        elif pattern == 'rate_hike' and ('rate' in event_type.lower() or 'interest' in event_type.lower()):
            return True
        elif pattern == 'earnings' and ('earnings' in event_type.lower() or 'quarterly' in event_type.lower()):
            return True
        elif pattern == 'volatility' and ('volatility' in event_type.lower() or 'market' in event_type.lower()):
            return True
        
        return False
    
    async def _calculate_ceg_probability_multiplier(
        self, 
        base_event: Event, 
        predicted_event_type: str
    ) -> float:
        """Рассчитывает множитель вероятности на основе CEG контекста"""
        
        multiplier = 1.0
        
        try:
            # Получаем важность базового события
            importance_statement = await self.session.execute(
                select(EventImportance)
                .where(EventImportance.event_id == base_event.id)
                .order_by(desc(EventImportance.calculation_timestamp))
                .limit(1)
            )
            
            importance = importance_statement.scalar_one_or_none()
            
            if importance:
                # Высокая важность = больше вероятность последствий
                multiplier += (importance.importance_score - 0.5) * 0.5
                
                # Высокий цена impact = больше вероятность рыночных реакций
                if 'market' in predicted_event_type.lower() or 'volatility' in predicted_event_type.lower():
                    multiplier += importance.price_impact * 0.3
            
            # Проверяем связанные события в графе
            ceg_context = await self._analyze_ceg_context(base_event)
            
            # Больше связанных событий = больше вероятность новых
            connected_ratio = min(1.0, ceg_context['connected_events'] / 5.0)  # Нормализуем к максимум 5
            multiplier += connected_ratio * 0.2
            
            # Ограничиваем множитель разумными пределами
            multiplier = max(0.5, min(2.0, multiplier))
            
        except Exception as e:
            logger.error(f"Error calculating CEG probability multiplier: {e}")
        
        return multiplier
    
    async def check_prediction_fulfillment(self) -> List[EventPrediction]:
        """
        Проверяет выполнение предсказаний
        
        Returns:
            List[EventPrediction]: Список обновленных предсказаний
        """
        logger.info("Checking prediction fulfillment...")
        
        # Находим предсказания, которые должны быть проверены
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        pending_predictions = await self.session.execute(
            select(EventPrediction)
            .where(
                and_(
                    EventPrediction.status == 'pending',
                    EventPrediction.created_at <= cutoff_time
                )
            )
            .order_by(EventPrediction.target_date_estimate)
        )
        
        predictions = pending_predictions.scalars().all()
        fulfilled_predictions = []
        
        for prediction in predictions:
            # Проверяем, есть ли события, которые могли выполнить предсказание
            fulfillment_result = await self._check_single_prediction_fulfillment(prediction)
            
            if fulfillment_result['fulfilled']:
                prediction.status = 'fulfilled'
                prediction.fulfilled_at = datetime.utcnow()
                prediction.actual_event_id = fulfillment_result['event_id']
                
                fulfilled_predictions.append(prediction)
                self.prediction_stats['predictions_fulfilled'] += 1
                
                logger.info(f"Prediction fulfilled: {prediction.predicted_event_type} "
                           f"-> {fulfillment_result['event_summary']}")
            
            else:
                # Проверяем, не истек ли срок предсказания
                if datetime.utcnow() > prediction.target_date_estimate:
                    prediction.status = 'expired'
                    self.prediction_stats['predictions_expired'] += 1
                    
                    logger.debug(f"Prediction expired: {prediction.predicted_event_type}")
        
        await self.session.flush()
        
        logger.info(f"Checked {len(predictions)} predictions, "
                   f"{len(fulfilled_predictions)} fulfilled")
        
        return fulfilled_predictions
    
    async def _check_single_prediction_fulfillment(
        self, 
        prediction: EventPrediction
    ) -> Dict[str, Any]:
        """Проверяет выполнение одного предсказания"""
        
        # Получаем базовое событие для контекста
        base_event_result = await self.session.execute(
            select(Event).where(Event.id == prediction.base_event_id)
        )
        base_event = base_event_result.scalar_one_or_none()
        
        if not base_event:
            return {'fulfilled': False}
        
        # Ищем события нужного типа после базового события
        search_start = max(base_event.ts, prediction.created_at)
        search_end = prediction.target_date_estimate
        
        matching_events = await self.session.execute(
            select(Event)
            .where(
                and_(
                    Event.id != prediction.base_event_id,
                    Event.ts >= search_start,
                    Event.ts <= search_end
                )
            )
            .order_by(Event.ts)
        )
        
        events_after = matching_events.scalars().all()
        
        # Проверяем соответствие типов событий
        for event in events_after:
            if self._is_prediction_match(prediction.predicted_event_type, event.event_type):
                return {
                    'fulfilled': True,
                    'event_id': event.id,
                    'event_summary': f"{event.event_type} at {event.ts}"
                }
        
        return {'fulfilled': False}
    
    def _is_prediction_match(self, predicted_type: str, actual_type: str) -> bool:
        """Проверяет соответствие предсказанного и фактического типа события"""
        
        # Простые правила сопоставления
        if predicted_type == actual_type:
            return True
        
        # Категориальное сопоставление
        category_mappings = {
            'sanctions_compliance': 'sanctions',
            'trade_restrictions': 'sanctions',
            'banking_limitations': 'sanctions',
            'rate_cut': 'rate_hike',
            'inflation_response': 'rate_hike',
            'market_volatility': 'volatility_spike',
            'index_movements': 'volatility_spike',
            'currency_changes': 'volatility_spike'
        }
        
        for category_key, possible_types in category_mappings.items():
            if predicted_type == category_key and actual_type in [actual_type]:
                if any(keyword in actual_type.lower() for keyword in category_key.split('_')):
                    return True
        
        return False
    
    async def update_predictions_accuracy(self) -> Dict[str, Any]:
        """Обновляет статистики точности предсказаний"""
        
        # Получаем выполненные предсказания
        fulfilled_predictions = await self.session.execute(
            select(EventPrediction)
            .where(EventPrediction.status == 'fulfilled')
        )
        
        fulfilled = fulfilled_predictions.scalars().all()
        
        # Получаем все предсказания для расчета общей точности
        all_predictions = await self.session.execute(
            select(EventPrediction)
            .where(
                or_(
                    EventPrediction.status == 'fulfilled',
                    EventPrediction.status == 'pending'
                )
            )
        )
        
        all_preds = all_predictions.scalars().all()
        
        # Рассчитываем статистики по типам
        type_stats = {}
        for prediction in fulfilled:
            pred_type = prediction.predicted_event_type
            
            if pred_type not in type_stats:
                type_stats[pred_type] = {
                    'total_made': 0,
                    'fulfilled': 0,
                    'accuracy': 0.0
                }
            
            type_stats[pred_type]['fulfilled'] += 1
        
        # Считаем общее количество по типам
        for prediction in all_preds:
            pred_type = prediction.predicted_event_type
            if pred_type in type_stats:
                type_stats[pred_type]['total_made'] += 1
        
        # Рассчитываем точность
        for pred_type in type_stats:
            if type_stats[pred_type]['total_made'] > 0:
                type_stats[pred_type]['accuracy'] = (
                    type_stats[pred_type]['fulfilled'] / 
                    type_stats[pred_type]['total_made']
                )
        
        self.prediction_stats['accuracy_by_type'] = type_stats
        
        # Общая точность
        overall_accuracy = len(fulfilled) / len(all_preds) if len(all_preds) > 0 else 0.0
        
        logger.info(f"Prediction accuracy update: {overall_accuracy:.3f} overall accuracy")
        
        return {
            'total_predictions': len(all_preds),
            'fulfilled_predictions': len(fulfilled),
            'overall_accuracy': overall_accuracy,
            'by_type': type_stats
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистики системы предсказаний"""
        try:
            self.prediction_stats['avg_prediction_horizon'] = (
                self.prediction_stats['avg_prediction_horizon'] / 
                max(1, self.prediction_stats['predictions_generated'])
            )
        except (ZeroDivisionError, KeyError):
            pass
        
        return {
            'prediction_engine_stats': self.prediction_stats,
            'prediction_patterns': {
                pattern_type: len(config['patterns']) 
                for pattern_type, config in self.prediction_patterns.items()
            },
            'system_status': 'running'
        }
