#Parser.src/services/events/cmnln_engine.py
"""
CMNLN Engine - Causal Mining of News & Links Networks
Определение причинно-следственных связей с использованием domain priors из ТЗ
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import uuid4

from Parser.src.core.models import Event
from Parser.src.graph_models import GraphService, EventNode, CausesRelation
from Parser.src.services.events.enhanced_evidence_engine import EnhancedEvidenceEngine
from Parser.src.services.events.causal_chains_engine import CausalChainsEngine, ChainDirection
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CMLNEngine:
    """
    Simple CMNLN Engine для определения причинности
    Использует domain priors из ТЗ (раздел 9)
    """

    # Domain Priors - причинно-следственные правила (из ТЗ раздел 9)
    DOMAIN_PRIORS = [
        {
            "cause_type": "sanctions",
            "effect_type": "market_drop",
            "sign": "-",
            "expected_lag": "0-1d",
            "conf_prior": 0.75,
            "description": "Санкции → падение рынка"
        },
        {
            "cause_type": "rate_hike",
            "effect_type": "rub_appreciation",
            "sign": "+",
            "expected_lag": "1h-1d",
            "conf_prior": 0.65,
            "description": "Повышение ставки → укрепление рубля"
        },
        {
            "cause_type": "rate_hike",
            "effect_type": "bank_stock_up",
            "sign": "+",
            "expected_lag": "0-3d",
            "conf_prior": 0.60,
            "description": "Повышение ставки → рост банковских акций"
        },
        {
            "cause_type": "rate_cut",
            "effect_type": "rub_depreciation",
            "sign": "-",
            "expected_lag": "1h-1d",
            "conf_prior": 0.60,
            "description": "Снижение ставки → ослабление рубля"
        },
        {
            "cause_type": "earnings_beat",
            "effect_type": "stock_rally",
            "sign": "+",
            "expected_lag": "0-1d",
            "conf_prior": 0.70,
            "description": "Превышение ожиданий → рост акций"
        },
        {
            "cause_type": "earnings_miss",
            "effect_type": "stock_drop",
            "sign": "-",
            "expected_lag": "0-1d",
            "conf_prior": 0.75,
            "description": "Неоправданные ожидания → падение акций"
        },
        {
            "cause_type": "guidance_cut",
            "effect_type": "stock_drop",
            "sign": "-",
            "expected_lag": "0-1d",
            "conf_prior": 0.70,
            "description": "Снижение прогноза → падение акций"
        },
        {
            "cause_type": "m&a",
            "effect_type": "target_stock_up",
            "sign": "+",
            "expected_lag": "0-1d",
            "conf_prior": 0.80,
            "description": "M&A → рост акций цели"
        },
        {
            "cause_type": "default",
            "effect_type": "bond_crash",
            "sign": "-",
            "expected_lag": "0-1h",
            "conf_prior": 0.90,
            "description": "Дефолт → обвал облигаций"
        },
        {
            "cause_type": "dividend_cut",
            "effect_type": "stock_drop",
            "sign": "-",
            "expected_lag": "0-1d",
            "conf_prior": 0.65,
            "description": "Сокращение дивидендов → падение акций"
        },
        {
            "cause_type": "buyback",
            "effect_type": "stock_up",
            "sign": "+",
            "expected_lag": "0-3d",
            "conf_prior": 0.60,
            "description": "Байбэк → рост акций"
        },
        {
            "cause_type": "regulatory",
            "effect_type": "sector_drop",
            "sign": "-",
            "expected_lag": "1-7d",
            "conf_prior": 0.55,
            "description": "Регулирование → падение сектора"
        },
        {
            "cause_type": "supply_chain",
            "effect_type": "production_down",
            "sign": "-",
            "expected_lag": "1-4w",
            "conf_prior": 0.50,
            "description": "Сбой цепочки → снижение производства"
        },
        {
            "cause_type": "accident",
            "effect_type": "stock_drop",
            "sign": "-",
            "expected_lag": "0-1d",
            "conf_prior": 0.65,
            "description": "Авария → падение акций"
        },
        {
            "cause_type": "management_change",
            "effect_type": "stock_volatility",
            "sign": "±",
            "expected_lag": "0-3d",
            "conf_prior": 0.45,
            "description": "Смена руководства → волатильность"
        }
    ]

    # Текстовые маркеры причинности (из ТЗ раздел 11)
    CAUSAL_TEXT_MARKERS = [
        ("из-за", 0.8),
        ("в результате", 0.8),
        ("вследствие", 0.8),
        ("в связи с", 0.7),
        ("на фоне", 0.6),
        ("после", 0.5),
        ("привело к", 0.9),
        ("вызвало", 0.9),
        ("стало причиной", 0.9),
        ("повлекло", 0.8),
        ("спровоцировало", 0.8),
        ("следствие", 0.7),
        ("due to", 0.8),
        ("because of", 0.8),
        ("as a result of", 0.8),
        ("caused by", 0.9),
        ("led to", 0.9),
        ("resulted in", 0.8)
    ]

    def __init__(self, graph_service: GraphService, session: AsyncSession = None):
        """Инициализация движка CMNLN"""
        self.graph_service = graph_service
        self.session = session
        
        # Инициализируем Enhanced Evidence Engine если есть session
        if self.session:
            self.enhanced_evidence_engine = EnhancedEvidenceEngine(session, graph_service)
            self.causal_chains_engine = CausalChainsEngine(session, graph_service)
        else:
            self.enhanced_evidence_engine = None
            self.causal_chains_engine = None

    async def detect_causality(
        self,
        cause_event: Event,
        effect_event: Event,
        news_text: str = ""
    ) -> Optional[CausesRelation]:
        """
        Определить причинно-следственную связь между событиями

        Args:
            cause_event: Событие-причина
            effect_event: Событие-следствие
            news_text: Текст новости для анализа текстовых маркеров

        Returns:
            CausesRelation если связь найдена, иначе None
        """
        # 1. Проверка временной последовательности
        if cause_event.ts >= effect_event.ts:
            return None

        time_diff = (effect_event.ts - cause_event.ts).total_seconds()

        # 2. Поиск соответствующего domain prior
        prior = self._find_domain_prior(cause_event.event_type, effect_event.event_type)

        if not prior:
            # Если нет явного prior, используем общие правила
            conf_prior = 0.0
            expected_lag = "0-7d"
            sign = "±"
        else:
            conf_prior = prior["conf_prior"]
            expected_lag = prior["expected_lag"]
            sign = prior["sign"]

            # Проверка соответствия ожидаемому лагу
            if not self._check_lag_match(time_diff, expected_lag):
                # Если лаг не соответствует, снижаем уверенность
                conf_prior *= 0.5

        # 3. Анализ текстовых маркеров
        conf_text = self._analyze_text_markers(news_text)

        # 4. Общая уверенность (пока без conf_market)
        conf_total = self._calculate_total_confidence(
            conf_prior=conf_prior,
            conf_text=conf_text,
            conf_market=0.0  # TODO: будет добавлено в Task 5
        )

        # Порог уверенности
        if conf_total < 0.3:
            return None

        # Определение типа связи
        kind = self._determine_kind(conf_prior, conf_text)

        return CausesRelation(
            kind=kind,
            sign=sign,
            expected_lag=expected_lag,
            conf_text=conf_text,
            conf_prior=conf_prior,
            conf_market=0.0,  # TODO: Task 5
            conf_total=conf_total,
            evidence_set=[]  # TODO: будет заполнено при поиске Evidence Events
        )

    def _find_domain_prior(self, cause_type: str, effect_type: str) -> Optional[Dict[str, Any]]:
        """Найти соответствующий domain prior"""
        for prior in self.DOMAIN_PRIORS:
            if prior["cause_type"] == cause_type:
                # Для упрощения, возвращаем первое совпадение
                # В полной версии нужно анализировать effect_type
                return prior
        return None

    def _check_lag_match(self, time_diff_sec: float, expected_lag: str) -> bool:
        """Проверить соответствие времени между событиями ожидаемому лагу"""
        lag_ranges = {
            "0-1h": (0, 3600),
            "1h-1d": (3600, 86400),
            "0-1d": (0, 86400),
            "0-3d": (0, 259200),
            "1-7d": (86400, 604800),
            "1-4w": (604800, 2419200)
        }

        if expected_lag not in lag_ranges:
            return True  # Если лаг неизвестен, принимаем

        min_lag, max_lag = lag_ranges[expected_lag]
        return min_lag <= time_diff_sec <= max_lag

    def _analyze_text_markers(self, text: str) -> float:
        """Анализ текстовых маркеров причинности"""
        if not text:
            return 0.0

        text_lower = text.lower()
        max_conf = 0.0

        for marker, conf in self.CAUSAL_TEXT_MARKERS:
            if marker in text_lower:
                max_conf = max(max_conf, conf)

        return max_conf

    def _calculate_total_confidence(
        self,
        conf_prior: float,
        conf_text: float,
        conf_market: float
    ) -> float:
        """
        Рассчитать общую уверенность в причинности
        Формула: conf_total = W1*conf_prior + W2*conf_text + W3*conf_market
        """
        # Веса (из ТЗ)
        W_PRIOR = 0.4
        W_TEXT = 0.3
        W_MARKET = 0.3

        return W_PRIOR * conf_prior + W_TEXT * conf_text + W_MARKET * conf_market

    def _determine_kind(self, conf_prior: float, conf_text: float) -> str:
        """
        Определить тип причинной связи:
        - CONFIRMED: высокая уверенность (prior + text)
        - RETRO: есть prior, нет текстовых маркеров
        - HYPOTHESIS: низкая уверенность, требует проверки
        """
        if conf_prior >= 0.6 and conf_text >= 0.6:
            return "CONFIRMED"
        elif conf_prior >= 0.5:
            return "RETRO"
        else:
            return "HYPOTHESIS"

    async def build_causal_chain(
        self,
        anchor_event: Event,
        all_events: List[Event],
        max_depth: int = 3
    ) -> List[Tuple[Event, Event, CausesRelation]]:
        """
        Построить причинную цепочку от якорного события
        Возвращает список (cause, effect, relation)
        """
        causal_links = []

        # Сортируем события по времени
        sorted_events = sorted(all_events, key=lambda e: e.ts)

        # Ищем связи от якорного события
        for event in sorted_events:
            if event.id == anchor_event.id:
                continue

            # Проверяем причинность
            relation = await self.detect_causality(
                cause_event=anchor_event,
                effect_event=event,
                news_text=""  # TODO: можно передать текст новости
            )

            if relation:
                causal_links.append((anchor_event, event, relation))

        # TODO: рекурсивный поиск цепочки (BFS до max_depth)
        # Для MVP достаточно одного уровня

        return causal_links

    async def find_evidence_events(
        self,
        cause_event: Event,
        effect_event: Event,
        all_events: List[Event]
    ) -> List[Event]:
        """
        Найти Evidence Events между причиной и следствием
        (события, усиливающие причинную связь)
        
        Использует Enhanced Evidence Engine если доступен, иначе простой алгоритм
        """
        
        # Используем Enhanced Evidence Engine если доступен
        if self.enhanced_evidence_engine and self.session:
            enhanced_evidence = await self.enhanced_evidence_engine.find_enhanced_evidence_events(
                cause_event, effect_event
            )
            
            logger.info(f"Found {len(enhanced_evidence)} enhanced evidence events")
            
            # Конвертируем в список Event объектов для обратной совместимости
            evidence_events = []
            for evidence_data in enhanced_evidence:
                if evidence_data['evidence_event']['id']:
                    # Находим соответствующий Event объект
                    for event in all_events:
                        if str(event.id) == evidence_data['evidence_event']['id']:
                            evidence_events.append(event)
                            break
            
            return evidence_events
        
        # Fallback: простой алгоритм как раньше
        evidence_events = []

        for event in all_events:
            # Evidence Event должно быть между cause и effect по времени
            if cause_event.ts < event.ts < effect_event.ts:
                # Проверяем связь с обоими событиями
                if self._shares_entities(event, cause_event) or \
                   self._shares_entities(event, effect_event):
                    evidence_events.append(event)

        # Ограничиваем до 3 событий (из ТЗ)
        return evidence_events[:3]

    def _shares_entities(self, event1: Event, event2: Event) -> bool:
        """Проверить, есть ли общие сущности между событиями"""
        # Проверяем компании
        companies1 = set(event1.attrs.get("companies", []))
        companies2 = set(event2.attrs.get("companies", []))

        if companies1 & companies2:
            return True

        # Проверяем тикеры
        tickers1 = set(event1.attrs.get("tickers", []))
        tickers2 = set(event2.attrs.get("tickers", []))

        if tickers1 & tickers2:
            return True

        return False
    
    async def discover_causal_chains(
        self,
        root_event_id: str,
        direction: Optional[str] = None,
        max_depth: Optional[int] = None,
        min_confidence: Optional[float] = None,
        time_window_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Обнаружить причинные цепочки для корневого события
        
        Args:
            root_event_id: ID корневого события
            direction: Направление поиска ('forward', 'backward', 'bidirectional')
            max_depth: Максимальная глубина поиска
            min_confidence: Минимальная уверенность в связях
            time_window_hours: Временное окно для поиска событий
            
        Returns:
            Словарь с найденными цепочками и метаданными
        """
        if not self.causal_chains_engine or not self.session:
            return {"error": "Causal chains engine not available"}
        
        # Преобразуем direction в enum
        direction_enum = ChainDirection.BIDIRECTIONAL
        if direction == 'forward':
            direction_enum = ChainDirection.FORWARD
        elif direction == 'backward':
            direction_enum = ChainDirection.BACKWARD
        
        result = await self.causal_chains_engine.discover_causal_chains(
            root_event_id=root_event_id,
            direction=direction_enum,
            max_depth=max_depth,
            min_confidence=min_confidence,
            time_window_hours=time_window_hours
        )
        
        return result
    
    def get_causal_chains_statistics(self) -> Dict[str, Any]:
        """Получить статистики движка причинных цепочек"""
        if not self.causal_chains_engine:
            return {"error": "Causal chains engine not available"}
        
        return self.causal_chains_engine.get_statistics()
