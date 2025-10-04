# src/services/events/watchers.py
"""
Watchers System - система мониторинга событий на трех уровнях:
L0: Базовые события (reactive monitoring)
L1: Комбинированные паттерны (pattern-based monitoring) 
L2: Прогнозы событий (predictive monitoring)
"""

import logging
from typing import Dict, Any, List, Optional, Callable, Set
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import asyncio

from src.core.models import Event
from src.graph_models import GraphService
from src.services.events.importance_calculator import ImportanceScoreCalculator

logger = logging.getLogger(__name__)


class WatchLevel(Enum):
    """Уровни мониторинга"""
    L0_BASIC = "L0"      # Базовые события
    L1_PATTERN = "L1"    # Комбинированные паттерны
    L2_PREDICTIVE = "L2"  # Прогнозы событий


class WatchStatus(Enum):
    """Статусы watcher'ов"""
    ACTIVE = "active"
    TRIGGERED = "triggered" 
    EXPIRED = "expired"
    DISABLED = "disabled"


@dataclass
class WatchCondition:
    """Условие срабатывания watcher'а"""
    event_types: List[str]
    companies: List[str]
    sectors: List[str]
    importance_threshold: float = 0.5
    burst_threshold: int = 3
    time_window_hours: int = 24
    
    def matches(self, event: Event, importance_score: float, burst_count: int) -> bool:
        """Проверить соответствие события условию"""
        
        # Проверка типа события
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # Проверка компаний
        event_companies = event.attrs.get("companies", [])
        event_tickers = event.attrs.get("tickers", [])
        event_entities = set(event_companies + event_tickers)
        
        if self.companies and not event_entities.intersection(set(self.companies)):
            return False
        
        # Проверка важности и burst
        if importance_score < self.importance_threshold:
            return False
            
        if burst_count < self.burst_threshold:
            return False
        
        return True


@dataclass
class WatchRule:
    """Правило мониторинга событий"""
    id: str
    name: str
    level: WatchLevel
    condition: WatchCondition
    description: str
    alerts: List[str] = None  # Список контактов для уведомлений
    auto_expire_hours: int = 168  # 7 дней по умолчанию
    
    def __post_init__(self):
        if self.alerts is None:
            self.alerts = []


class TriggeredWatch:
    """Сработавший watcher"""
    
    def __init__(self, rule: WatchRule, trigger_event: Event, trigger_time: datetime, context: Dict[str, Any]):
        self.rule = rule
        self.trigger_event = trigger_event
        self.trigger_time = trigger_time
        self.context = context
        self.status = WatchStatus.TRIGGERED
        self.notifications_sent = False
        self.last_check = trigger_time


class BaseWatcher(ABC):
    """Базовый класс для всех watcher'ов"""
    
    def __init__(self, graph_service: GraphService, importance_calculator: ImportanceScoreCalculator):
        self.graph_service = graph_service
        self.importance_calculator = importance_calculator
        self.active_watches: Dict[str, TriggeredWatch] = {}
        self.statistics = {
            'total_checks': 0,
            'triggers_found': 0,
            'notifications_sent': 0,
            'expired_watches': 0
        }
    
    @abstractmethod
    async def check_event(self, event: Event) -> List[TriggeredWatch]:
        """Проверить событие на срабатывание правил"""
        pass
    
    @abstractmethod
    def get_watch_level(self) -> WatchLevel:
        """Получить уровень watcher'а"""
        pass


class L0BasicWatcher(BaseWatcher):
    """L0 Watcher - мониторинг базовых событий
    
    Отслеживает:
    - Важные события по типам (санкции, дефолты, earnings)
    - События с высокой важностью
    - Burst события
    - Якорные события
    """
    
    def __init__(self, graph_service: GraphService, importance_calculator: ImportanceScoreCalculator):
        super().__init__(graph_service, importance_calculator)
        
        # Загружаем правила L0 мониторинга
        self.watch_rules = self._initialize_l0_rules()
    
    def _initialize_l0_rules(self) -> List[WatchRule]:
        """Инициализация правил L0 мониторинга"""
        
        return [
            # Критические события
            WatchRule(
                id="critical_sanctions",
                name="Критические санкции",
                level=WatchLevel.L0_BASIC,
                condition=WatchCondition(
                    event_types=["sanctions"],
                    companies=[],
                    sectors=["banks", "energy", "defense"],
                    importance_threshold=0.8,
                    burst_threshold=2
                ),
                description="Новые санкции против банковского/энергетического/оборонного секторов",
                priority="high"
            ),
            
            WatchRule(
                id="default_events",
                name="Дефолты компаний",
                level=WatchLevel.L0_BASIC,
                condition=WatchCondition(
                    event_types=["default", "bankruptcy"],
                    companies=[],
                    sectors=[],
                    importance_threshold=0.9,
                    burst_threshold=1
                ),
                description="Объявления о дефолтах или банкротствах",
                priority="critical"
            ),
            
            # Финансовые события
            WatchRule(
                id="central_bank_rates",
                name="Политика ЦБ",
                level=WatchLevel.L0_BASIC,
                condition=WatchRule(
                    event_types=["rate_hike", "rate_cut"],
                    companies=["ЦБ РФ", "Bank of Russia"],
                    sectors=["monetary"],
                    importance_threshold=0.7,
                    burst_threshold=1
                ),
                description="Изменения ключевой ставки ЦБ РФ",
                priority="high"
            ),
            
            # Earnings сюрпризы
            WatchRule(
                id="major_earnings_surprises",
                name="Крупные earnings сюрпризы",
                level=WatchLevel.L0_BASIC,
                condition=WatchCondition(
                    event_types=["earnings_miss", "earnings_beat"],
                    companies=[],  # Любые крупные компании
                    sectors=["banks", "oil_gas", "metals", "telecom"],
                    importance_threshold=0.6,
                    burst_threshold=3
                ),
                description="Значительные отклонения от прогнозов earnings",
                priority="medium"
            ),
            
            # M&A активности
            WatchRule(
                id="large_ma_deals",
                name="Крупные M&A сделки",
                level=WatchLevel.L0_BASIC,
                condition=WatchCondition(
                    event_types=["m&a", "acquisition", "merger"],
                    companies=[],
                    sectors=["finance", "energy", "metals"],
                    importance_threshold=0.8,
                    burst_threshold=2
                ),
                description="Крупные сделки слияний и поглощений",
                priority="medium"
            ),
            
            # IPO события
            WatchRule(
                id="major_ipo_events",
                name="Крупные IPO",
                level=WatchLevel.L0_BASIC,
                condition=WatchCondition(
                    event_types=["ipo", "public_offering"],
                    companies=[],
                    sectors=["technology", "finance", "energy"],
                    importance_threshold=0.7,
                    burst_threshold=1
                ),
                description="Крупные первичные размещения акций",
                priority="medium"
            ),
            
            # Аварии и инциденты
            WatchRule(
                id="major_accidents",
                name="Серьезные аварии",
                level=WatchLevel.L0_BASIC,
                condition=WatchCondition(
                    event_types=["accident", "incident", "disaster"],
                    companies=[],
                    sectors=["transport", "energy", "mining"],
                    importance_threshold=0.9,
                    burst_threshold=1
                ),
                description="Серьезные аварии в стратегически важных секторах",
                priority="high"
            ),
            
            # Макроэкономические события
            WatchRule(
                id="macro_regulatory",
                name="Макро регулирование",
                level=WatchLevel.L0_BASIC,
                condition=WatchCondition(
                    event_types=["regulatory", "legislation", "policy"],
                    companies=["Правительство РФ", "Минфин"],
                    sectors=["macro"],
                    importance_threshold=0.8,
                    burst_threshold=2
                ),
                description="Важные изменения в государственной политике",
                priority="high"
            )
        ]
    
    async def check_event(self, event: Event) -> List[TriggeredWatch]:
        """Проверить событие на соответствие правилам L0"""
        
        triggered_watches = []
        
        # Рассчитываем важность события
        importance_data = await self.importance_calculator.calculate_importance_score(event)
        importance_score = importance_data.get('importance_score', 0.0)
        
        # Получаем burst count для события
        burst_event_count = await self._get_burst_count(event)
        
        logger.debug(
            f"L0 Watch: Checking event {event.id} "
            f"(type: {event.event_type}, importance: {importance_score:.3f}, burst: {burst_event_count})"
        )
        
        # Проверяем каждое правило
        for rule in self.watch_rules:
            
            # Проверяем, не сработал ли уже watcher для этого события
            if rule.id in self.active_watches:
                continue
            
            # Проверяем соответствие условиям
            if rule.condition.matches(event, importance_score, burst_event_count):
                
                # Создаем контекст срабатывания
                context = {
                    'importance_score': importance_score,
                    'burst_count': burst_event_count,
                    'trigger_type': 'L0_BASIC',
                    'companies': event.attrs.get('companies', []),
                    'tickers': event.attrs.get('tickers', []),
                    'importance_details': importance_data.get('components_details', {})
                }
                
                # Создаем сработавший watcher
                triggered_watch = TriggeredWatch(
                    rule=rule,
                    trigger_event=event,
                    trigger_time=datetime.utcnow(),
                    context=context
                )
                
                triggered_watches.append(triggered_watch)
                self.active_watches[str(event.id)] = triggered_watch
                
                logger.info(
                    f"L0 Watcher triggered: {rule.name} for event {event.id} "
                    f"(importance: {importance_score:.3f}, burst: {burst_event_count})"
                )
        
        self.statistics['total_checks'] += 1
        self.statistics['triggers_found'] += len(triggered_watches)
        
        return triggered_watches
    
    async def _get_burst_count(self, event: Event) -> int:
        """Получить количество похожих событий в burst окне"""
        
        burst_window = timedelta(hours=24)
        burst_start = event.ts - burst_window
        
        burst_query = """
            SELECT COUNT(*) 
            FROM events 
            WHERE event_type = %s 
            AND ts >= %s 
            AND ts <= %s
        """
        
        try:
            from sqlalchemy import text
            result = await self.graph_state.session.execute(
                text(burst_query),
                (event.event_type, burst_start, event.ts)
            )
            count = result.scalar() or 0
            return count
        except Exception as e:
            logger.warning(f"Error getting burst count: {e}")
            return 1
    
    def get_watch_level(self) -> WatchLevel:
        return WatchLevel.L0_BASIC


class L1PatternWatcher(BaseWatcher):
    """L1 Watcher - мониторинг комбинированных паттернов
    
    Отслеживает:
    - Последовательности событий
    - Коррелирующие события в разных секторах
    - Каскады влияний
    - Паттерны рынка
    """
    
    def __init__(self, graph_service: GraphService, importance_calculator: ImportanceScoreCalculator):
        super().__init__(graph_service, importance_calculator)
        
        # Паттерны L1 мониторинга
        self.pattern_rules = self._initialize_l1_patterns()
    
    def _initialize_l1_patterns(self) -> List[WatchRule]:
        """Инициализация паттернов L1"""
        
        return [
            # Паттерн: Санкции → Падение рынка
            WatchRule(
                id="sanctions_market_pattern",
                name="Паттерн санкции→рынок",
                level=WatchLevel.L1_PATTERN,
                condition=WatchCondition(
                    event_types=["sanctions"],  # Инициатор
                    companies=[],
                    importance_threshold=0.7
                ),
                description="Санкции с последующим анализом рыночной реакции",
                pattern_type="causal_chain",
                follow_days=7
            ),
            
            # Паттерн: Повышение ставки → Реакция банков
            WatchRule(
                id="rate_hike_banking_pattern",
                name="Паттерн ставка→банки",
                level=WatchLevel.L1_PATTERN,
                condition=WatchCondition(
                    event_types=["rate_hike"],
                    sectors=["monetary"],
                    importance_threshold=0.6
                ),
                description="Повышение ставки с анализом реакции банковского сектора",
                pattern_type="sector_reaction",
                follow_days=5
            ),
            
            # Паттерн: Earnings каскад
            WatchRule(
                id="earnings_cascade_pattern",
                name="Паттерн earnings каскад",
                level=WatchLevel.L1_PATTERN,
                condition=WatchCondition(
                    event_types=["earnings_miss", "earnings_beat"],
                    sectors=["banking", "oil_gas", "metals"],
                    importance_threshold=0.5
                ),
                description="Earnings события в одном секторе влияют на другие сектора",
                pattern_type="sector_cascade",
                follow_days=3
            ),
            
            # Паттерн: Регулирование → Сегоднястй impact
            WatchRule(
                id="regulatory_contagion_pattern",
                name="Паттерн регулирование→заражение",
                level=WatchLevel.L1_PATTERN,
                condition=WatchCondition(
                    event_types=["regulatory", "legislation"],
                    sectors=["finance", "energy", "telecom"],
                    importance_threshold=0.7
                ),
                description="Новое регулирование влияет на связанные сектора",
                pattern_type="regulatory_contagion",
                follow_days=5
            )
        ]
    
    async def check_event(self, event: Event) -> List[TriggeredWatch]:
        """Проверить событие на соответствие L1 паттернам"""
        
        triggered_watches = []
        
        # Рассчитываем важность
        importance_data = await self.importance_calculator.calculate_importance_score(event)
        importance_score = importance_data.get('importance_score', 0.0)
        
        for pattern_rule in self.pattern_rules:
            
            # Проверяем базовые условия паттерна
            event_types = pattern_rule.condition.event_types
            sectors = pattern_rule.condition.sectors
            
            # Проверка типа события
            if event_types and event.event_type not in event_types:
                continue
            
            # Проверка сектора (через связанные компании)
            if sectors and not await self._check_sector_match(event, sectors):
                continue
            
            # Проверка важности
            if importance_score < pattern_rule.condition.importance_threshold:
                continue
            
            # Создаем watcher для отслеживания развития паттерна
            context = {
                'pattern_type': getattr(pattern_rule, 'pattern_type', 'general'),
                'importance_score': importance_score,
                'follow_days': getattr(pattern_rule, 'follow_days', 3),
                'initial_event': {
                    'id': str(event.id),
                    'type': event.event_type,
                    'timestamp': event.ts,
                    'companies': event.attrs.get('companies', []),
                    'tickers': event.attrs.get('tickers', [])
                }
            }
            
            triggered_watch = TriggeredWatch(
                rule=pattern_rule,
                trigger_event=event,
                trigger_time=datetime.utcnow(),
                context=context
            )
            
            triggered_watches.append(triggered_watch)
            self.active_watches[f"{pattern_rule.id}_{event.id}"] = triggered_watch
            
            logger.info(f"L1 Pattern Watcher triggered: {pattern_rule.name} for event {event.id}")
        
        self.statistics['total_checks'] += 1
        self.statistics['triggers_found'] += len(triggered_watches)
        
        return triggered_watches
    
    async def _check_sector_match(self, event: Event, target_sectors: List[str]) -> bool:
        """Проверить соответствие секторам"""
        
        tickers = event.attrs.get('tickers', [])
        
        # Получаем сектора из Neo4j
        sector_query = """
            MATCH (i:Instrument)-[:BELONGS_TO]->(s:Sector)
            WHERE i.symbol IN $tickers
            RETURN DISTINCT s.name as sector
        """
        
        try:
            result = await self.graph_service.execute_query(
                sector_query, 
                {"tickers": tickers}
            )
            
            event_sectors = [record.get('sector') for record in result] if result else []
            
            # Проверяем пересечение с целевыми секторами
            target_sectors_lower = [s.lower() for s in target_sectors]
            event_sectors_lower = [s.lower() for s in event_sectors]
            
            return bool(set(target_sectors_lower) & set(event_sectors_lower))
            
        except Exception as e:
            logger.warning(f"Error checking sector match: {e}")
            return False
    
    def get_watch_level(self) -> WatchLevel:
        return WatchLevel.L1_PATTERN


class L2PredictiveWatcher(BaseWatcher):
    """L2 Watcher - прогноз событий на основе CEG
    
    Использует причинно-следственные связи для предсказания:
    - Последствий текущих событий
    - Появления событий в будущем
    - Каскадов влияний
    """
    
    def __init__(self, graph_service: GraphService, importance_calculator: ImportanceScoreCalculator):
        super().__init__(graph_service, importance_calculator)
        
        # Правила прогнозирования L2
        self.prediction_rules = self._initialize_l2_predictions()
    
    def _initialize_l2_predictions(self) -> List[WatchRule]:
        """Инициализация правил L2 прогнозирования"""
        
        return [
            WatchRule(
                id="sanctions_consequence_prediction",
                name="Прогноз последствий санкций",
                level=WatchLevel.L2_PREDICTIVE,
                condition=WatchCondition(
                    event_types=["sanctions"],
                    importance_threshold=0.8
                ),
                description="Предсказывает рыночную реакцию на новые санкции",
                prediction_window_days=14,
                prediction_types=["market_drop", "currency_pressure", "sector_reaction"]
            ),
            
            WatchRule(
                id="election_period_events",
                name="События электорального цикла",
                level=WatchLevel.L2_PREDICTIVE,
                condition=WatchCondition(
                    event_types=["regulatory", "policy"],
                    importance_threshold=0.7
                ),
                description="Предсказывает политические события перед выборами",
                prediction_window_days=30,
                prediction_types=["policy_announcements", "market_uncertainty"]
            ),
            
            WatchRule(
                id="credit_downgrade_cascade",
                name="Каскад кредитных понижений",
                level=WatchLevel.L2_PREDICTIVE,
                condition=WatchCondition(
                    event_types=["credit_downgrade", "default"],
                    sectors=["finance", "sovereign"],
                    importance_threshold=0.6
                ),
                description="Предсказывает каскадные понижения кредитного рейтинга",
                prediction_window_days=21,
                prediction_types=["rating_reviews", "bond_yield_spikes", "fx_volatility"]
            )
        ]
    
    async def check_event(self, event: Event) -> List[TriggeredWatch]:
        """Проверить событие на базу для L2 прогнозов"""
        
        triggered_watches = []
        
        # Рассчитываем важность
        importance_data = await self.importance_calculator.calculate_importance_score(event)
        importance_score = importance_data.get('importance_score', 0.0)
        
        for pred_rule in self.prediction_rules:
            
            # Проверяем условия для активации прогноза
            if not pred_rule.condition.matches(event, importance_score, 1):
                continue
            
            # Получаем причинные цепочки из графа
            causal_chains = await self._get_causal_chains(event)
            
            if not causal_chains:
                continue
            
            # Генерируем прогнозы на основе CEG
            predictions = await self._generate_predictions(event, causal_chains, pred_rule)
            
            context = {
                'predictions': predictions,
                'causal_chains': causal_chains,
                'prediction_window_days': getattr(pred_rule, 'prediction_window_days', 14),
                'prediction_types': getattr(pred_rule, 'prediction_types', []),
                'importance_score': importance_score,
                'base_event': {
                    'id': str(event.id),
                    'type': event.event_type,
                    'timestamp': event.ts
                }
            }
            
            triggered_watch = TriggeredWatch(
                rule=pred_rule,
                trigger_event=event,
                trigger_time=datetime.utcnow(),
                context=context
            )
            
            triggered_watches.append(triggered_watch)
            self.active_watches[f"{pred_rule.id}_{event.id}"] = triggered_watch
            
            logger.info(f"L2 Predictive Watcher triggered: {pred_rule.name} generated {len(predictions)} predictions")
        
        self.statistics['total_checks'] += 1
        self.statistics['triggers_found'] += len(triggered_watches)
        
        return triggered_watches
    
    async def _get_causal_chains(self, event: Event) -> List[Dict[str, Any]]:
        """Получить причинные стратегии от события"""
        
        causal_query = """
            MATCH path = (e:EventNode {id: $event_id})-[:CAUSES*1..3]->(target:EventNode)
            WHERE target.importance_score >= 0.5
            RETURN path, target.type as next_event_type, target.importance_score
            ORDER BY target.importance_score DESC
            LIMIT 5
        """
        
        try:
            result = await self.graph_service.execute_query(
                causal_query,
                {"event_id": str(event.id)}
            )
            
            chains = []
            for record in result:
                chain_data = {
                    'path': record.get('path'),
                    'next_event_type': record.get('next_event_type'),
                    'probability': record.get('target_importance_score', 0.5),
                }
                chains.append(chain_data)
            
            return chains
            
        except Exception as e:
            logger.warning(f"Error getting causal chains: {e}")
            return []
    
    async def _generate_predictions(self, event: Event, chains: List[Dict[str, Any]], rule: WatchRule) -> List[Dict[str, Any]]:
        """Сгенерировать прогнозы на основе причинных цепочек"""
        
        predictions = []
        prediction_window = timedelta(days=getattr(rule, 'prediction_window_days', 14))
        
        for chain in chains:
            prediction = {
                'id': f"{rule.id}_{len(predictions)}",
                'type': chain.get('next_event_type', 'unknown'),
                'probability': chain.get('probability', 0.5),
                'prediction_window_days': prediction_window.days,
                'base_event_id': str(event.id),
                'generated_at': datetime.utcnow(),
                'target_date_estimate': datetime.utcnow() + prediction_window,
                'description': f"Predicted {chain.get('next_event_type')} based on {event.event_type}"
            }
            
            predictions.append(prediction)
        
        return predictions
    
    def get_watch_level(self) -> WatchLevel:
        return WatchLevel.L2_PREDICTIVE


class WatchersSystem:
    """
    Главная система управления watcher'ами
    
    Координирует работу L0, L1, L2 watcher'ов
    """
    
    def __init__(self, graph_service: GraphService, importance_calculator: ImportanceScoreCalculator):
        self.graph_service = graph_service
        self.importance_calculator = importance_calculator
        
        # Инициализируем watcher'ы всех уровней
        self.watchers = {
            WatchLevel.L0_BASIC: L0BasicWatcher(graph_service, importance_calculator),
            WatchLevel.L1_PATTERN: L1PatternWatcher(graph_service, importance_calculator), 
            WatchLevel.L2_PREDICTIVE: L2PredictiveWatcher(graph_service, importance_calculator)
        }
        
        self.notification_handlers: List[Callable] = []
        self.statistics = {
            'total_events_checked': 0,
            'watchers_by_level': {level: 0 for level in WatchLevel},
            'active_watches': 0,
            'notifications_sent': 0
        }
    
    async def check_event(self, event: Event) -> Dict[str, Any]:
        """
        Проверить событие всеми watcher'ами
        
        Args:
            event: Событие для проверки
            
        Returns:
            Результат проверки всех уровней
        """
        logger.info(f"WatchersSystem: Checking event {event.id} ({event.event_type})")
        
        results = {
            'event_id': str(event.id),
            'event_type': event.event_type,
            'check_timestamp': datetime.utcnow(),
            'level_results': {},
            'summary': {
                'total_triggers': 0,
                'levels_triggered': []
            }
        }
        
        total_triggers = 0
        
        # Проверяем каждым watcher'ом
        for level, watcher in self.watchers.items():
            
            try:
                triggered_watches = await watcher.check_event(event)
                
                results['level_results'][level.value] = {
                    'triggered_count': len(triggered_watches),
                    'triggered_watches': [
                        {
                            'rule_id': tw.rule.id,
                            'rule_name': tw.rule.name,
                            'trigger_time': tw.trigger_time.isoformat(),
                            'context': tw.context
                        }
                        for tw in triggered_watches
                    ]
                }
                
                if triggered_watches:
                    total_triggers += len(triggered_watches)
                    results['summary']['levels_triggered'].append(level.value)
                    
                    # Отправляем уведомления
                    await self._send_notifications(triggered_watches)
                
            except Exception as e:
                logger.error(f"Error checking event with {level.value} watcher: {e}")
                results['level_results'][level.value] = {
                    'error': str(e),
                    'triggered_count': 0
                }
        
        results['summary']['total_triggers'] = total_triggers
        
        # Обновляем статистику
        self.statistics['total_events_checked'] += 1
        
        logger.info(f"WatchersSystem check complete: {total_triggers} triggers across {len(results['summary']['levels_triggered'])} levels")
        
        return results
    
    async def _send_notifications(self, triggered_watches: List[TriggeredWatch]):
        """Отправить уведомления о сработавших watcher'ах"""
        
        for watch in triggered_watches:
            
            if watch.notifications_sent:
                continue
            
            # Подготавливаем данные уведомления
            notification = {
                'watch_id': watch.rule.id,
                'watch_name': watch.rule.name,
                'level': watch.rule.level.value,
                'trigger_event_id': str(watch.trigger_event.id),
                'trigger_time': watch.trigger_time.isoformat(),
                'alerts': watch.rule.alerts,
                'context': watch.context,
                'priority': getattr(watch.rule.condition, 'priority', 'medium')
            }
            
            # Отправляем через все зарегистрированные обработчики
            for handler in self.notification_handlers:
                try:
                    await handler(notification)
                    watch.notifications_sent = True
                except Exception as e:
                    logger.error(f"Error sending notification via handler: {e}")
        
        self.statistics['notifications_sent'] += len(triggered_watches)
    
    def add_notification_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Добавить обработчик уведомлений"""
        self.notification_handlers.append(handler)
    
    async def cleanup_expired_watches(self):
        """Очистка истекших watcher'ов"""
        
        expired_count = 0
        current_time = datetime.utcnow()
        
        for level, watcher in self.watchers.items():
            
            expired_watch_ids = []
            
            for watch_id, triggered_watch in watcher.active_watches.items():
                
                # Проверяем срок действия
                expire_hours = triggered_watch.rule.auto_expire_hours
                expire_time = triggered_watch.trigger_time + timedelta(hours=expire_hours)
                
                if current_time > expire_time:
                    expired_watch_ids.append(watch_id)
                    triggered_watch.status = WatchStatus.EXPIRED
                    expired_count += 1
            
            # Удаляем истекшие watcher'ы
            for watch_id in expired_watch_ids:
                del watcher.active_watches[watch_id]
        
        self.statistics['expired_watches'] += expired_count
        
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired watches")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы"""
        
        # Собираем статистику со всех watcher'ов
        watcher_stats = {}
        total_active_watches = 0
        
        for level, watcher in self.watchers.items():
            watcher_stats[level.value] = {
                'active_watches': len(watcher.active_watches),
                'statistics': watcher.statistics
            }
            total_active_watches += len(watcher.active_watches)
        
        return {
            'system_statistics': self.statistics,
            'watcher_statistics': watcher_stats,
            'total_active_watches': total_active_watches,
            'notification_handlers_count': len(self.notification_handlers)
        }
