# src/services/events/importance_calculator.py
"""
Importance Score Calculator для CEG событий
Реализует многокомпонентную оценку важности событий:
Novelty + Burst + Credibility + Breadth + PriceImpact
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from statistics import median, mean
from collections import defaultdict, Counter

from src.core.models import News, Event
from src.graph_models import GraphService

logger = logging.getLogger(__name__)


class ImportanceScoreCalculator:
    """
    Калькулятор важности событий для CEG системы
    
    Вычисляет Importance Score как взвешенную сумму компонентов:
    - Novelty: насколько новое это событие (не было ранее)
    - Burst: частота упоминания события за короткий период
    - Credibility: надежность источника и контекста
    - Breadth: широта охвата (сколько компаний/секторов затронуто)
    - Price Impact: влияние на рыночные цены
    """

    def __init__(self, session, graph_service: GraphService):
        self.session = session
        self.graph = graph_service
        
        # Гиперпараметры для расчета важности
        self.weights = {
            'novelty': 0.25,     # Новизна события
            'burst': 0.20,       # Частота упоминания
            'credibility': 0.25, # Надежность источника
            'breadth': 0.15,    # Широта охвата
            'price_impact': 0.15 # Рыночное влияние
        }
        
        # Пороги для нормализации
        self.thresholds = {
            'burst_min_events': 2,        # Минимум событий для burst
            'burst_time_window': 24,      # Часы для burst анализа
            'breadth_min_companies': 2,   # Минимум компаний для breadth
            'credibility_min_confidence': 0.7  # Минимум доверия для источника
        }

    async def calculate_importance_score(self, event: Event) -> Dict[str, Any]:
        """
        Рассчитать важность события
        
        Args:
            event: Событие для анализа
            
        Returns:
            {
                'importance_score': float,  # Общий балл важности [0, 1]
                'novelty': float,          # Компонент новизны
                'burst': float,            # Компонент частоты
                'credibility': float,       # Компонент надежности
                'breadth': float,          # Компонент широты
                'price_impact': float,      # Компонент рыночного влияния
                'components_details': dict, # Детали компонентов
                'calculation_timestamp': datetime
            }
        """
        logger.info(f"Calculating importance score for event {event.id} ({event.event_type})")

        components = {}
        
        try:
            # 1. Novelty Score - насколько новое это событие
            components['novelty'] = await self._calculate_novelty_score(event)
            
            # 2. Burst Score - частота упоминания за период
            components['burst'] = await self._calculate_burst_score(event)
            
            # 3. Credibility Score - надежность источника
            components['credibility'] = await self._calculate_credibility_score(event)
            
            # 4. Breadth Score - широта охвата
            components['breadth'] = await self._calculate_breadth_score(event)
            
            # 5. Price Impact Score - влияние на цены
            components['price_impact'] = await self._calculate_price_impact_score(event)
            
            # Суммарный балл важности
            importance_score = sum(
                components[component] * weight 
                for component, weight in self.weights.items()
            )
            
            # Ограничиваем в диапазоне [0, 1]
            importance_score = max(0.0, min(1.0, importance_score))
            
            result = {
                'importance_score': importance_score,
                'novelty': components['novelty'],
                'burst': components['burst'],
                'credibility': components['credibility'],
                'breadth': components['breadth'],
                'price_impact': components['price_impact'],
                'components_details': components,
                'calculation_timestamp': datetime.utcnow(),
                'weights': self.weights
            }
            
            logger.info(
                f"Importance score for event {event.id}: {importance_score:.3f} "
                f"(N:{components['novelty']:.2f} B:{components['burst']:.2f} "
                f"C:{components['credibility']:.2f} Br:{components['breadth']:.2f} "
                f"P:{components['price_impact']:.2f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating importance score for event {event.id}: {e}")
            return {
                'importance_score': 0.0,
                'novelty': 0.0,
                'burst': 0.0,
                'credibility': 0.0,
                'breadth': 0.0,
                'price_impact': 0.0,
                'components_details': {},
                'error': str(e),
                'calculation_timestamp': datetime.utcnow()
            }

    async def _calculate_novelty_score(self, event: Event) -> float:
        """
        Novelty Score: Насколько новое это событие
        
        Анализирует:
        - Первое ли это событие данного типа для компании
        - Редкость типа события
        - Временной интервал с последнего похожего события
        """
        # Базовая оценка новизны
        base_novelty = 0.5
        
        # 1. Проверяем события того же типа для тех же компаний за последний месяц
        company_tickers = event.attrs.get("tickers", [])
        event_type = event.event_type
        
        if company_tickers:
            lookback_date = event.ts - timedelta(days=30)
            
            similar_events_query = """
                SELECT COUNT(*) 
                FROM events 
                WHERE event_type = %s 
                AND ts >= %s 
                AND ts < %s
                AND jsonb_path_exists(attrs, '$.tickers[*] ? (@ == $1)'::jsonpath, %s)
            """
            
            # Для каждой компании или тикера проверяем повторяемость
            for ticker in company_tickers[:3]:  # Ограничиваем до 3 тикеров
                count_result = await self.session.execute(
                    similar_events_query, 
                    (event_type, lookback_date, event.ts, ticker)
                )
                count = count_result.scalar() or 0
                
                if count == 0:
                    # Первое событие этого типа для компании
                    base_novelty += 0.3
                elif count == 1:
                    # Второе событие - средняя новизна
                    base_novelty += 0.1
                else:
                    # Множественные события - низкая новизна
                    base_novelty += 0.05 * max(0, 5 - count) / 5
        
        # 2. Редкость типа события
        event_type_rarity = await self._get_event_type_rarity(event_type)
        
        # 3. Комбинируем оценки
        novelty_score = (base_novelty * 0.7) + (event_type_rarity * 0.3)
        
        return max(0.0, min(1.0, novelty_score))

    async def _calculate_burst_score(self, event: Event) -> float:
        """
        Burst Score: Частота упоминания события за короткий период
        
        Анализирует:
        - Количество событий того же типа за последние N часов
        - Градиент увеличения частоты
        - Пиковые значения упоминаний
        """
        burst_window_hours = self.thresholds['burst_time_window']
        burst_window = timedelta(hours=burst_window_hours)
        
        burst_start = event.ts - burst_window
        
        # Ищем события того же типа в окне burst
        burst_query = """
            SELECT COUNT(*) 
            FROM events 
            WHERE event_type = %s 
            AND ts >= %s 
            AND ts <= %s
        """
        
        count_result = await self.session.execute(
            burst_query, 
            (event.event_type, burst_start, event.ts)
        )
        event_count = count_result.scalar() or 0
        
        if event_count < self.thresholds['burst_min_events']:
            return 0.1  # Без активности - низкий burst
        
        # Нормализуем burst score в зависимости от количества событий
        # Экспоненциальная функция для усиления высоких значений
        burst_score = min(1.0, (event_count - 1) ** 0.7 / 10)
        
        # Бонус за концентрацию во времени (события в последние часы)
        recent_hours = 6
        recent_start = event.ts - timedelta(hours=recent_hours)
        
        recent_count_query = """
            SELECT COUNT(*) 
            FROM events 
            WHERE event_type = %s 
            AND ts >= %s 
            AND ts <= %s
        """
        
        recent_count_result = await self.session.execute(
            recent_count_query, 
            (event.event_type, recent_start, event.ts)
        )
        recent_count = recent_count_result.scalar() or 0
        
        # Если многие события произошли недавно - это burst
        if recent_count > event_count * 0.7:
            burst_score = min(1.0, burst_score + 0.3)
        
        return burst_score

    async def _calculate_credibility_score(self, event: Event) -> float:
        """
        Credibility Score: Надежность источника и контекста события
        
        Анализирует:
        - Trust level источника новости
        - Согласованность с другими источниками
        - Тип события (более надежные типы имеют приоритет)
        """
        # Получаем информацию о источнике через новость
        credibility_score = 0.5  # Базовая оценка
        
        if event.news_id:
            news_query = """
                SELECT sources.trust_level, sources.kind
                FROM news 
                JOIN sources ON news.source_id = sources.id
                WHERE news.id = %s
            """
            
            source_result = await self.session.execute(news_query, (event.news_id,))
            source_data = source_result.fetchone()
            
            if source_data:
                trust_level, source_kind = source_data
                
                # Trust level влияет на credibility
                credibility_score += (trust_level - 5) * 0.1  # Центрируем на 5
                
                # Бонус за тип источника
                if source_kind == 'telegram':
                    if trust_level >= 8:
                        credibility_score += 0.2  # Премиум каналы
                    elif trust_level >= 6:
                        credibility_score += 0.1  # Хорошие каналы
        
        # Бонус за тип события (некоторые события более "надежны")
        high_credibility_types = {
            'earnings', 'earnings_beat', 'earnings_miss',
            'rate_hike', 'rate_cut',
            'default', 'm&a', 'ipo'
        }
        
        if event.event_type in high_credibility_types:
            credibility_score += 0.2
        
        # Модификатор на основе якорности события
        if event.is_anchor:
            credibility_score += 0.15
        
        # Проверяем множественность источников (корреляцию с другими источниками)
        correlation_bonus = await self._check_source_correlation(event)
        credibility_score += correlation_bonus * 0.1
        
        return max(0.0, min(1.0, credibility_score))

    async def _calculate_breadth_score(self, event: Event) -> float:
        """
        Breadth Score: Широта охвата события
        
        Анализирует:
        - Количество вовлеченных компаний/тикеров
        - Отраслевое разнообразие
        - Географический охват (если применимо)
        """
        breadth_score = 0.3  # Базовая оценка для одного события
        
        # Количество компаний/тикеров
        companies = event.attrs.get("companies", [])
        tickers = event.attrs.get("tickers", [])
        unique_entities = len(set(companies + tickers))
        
        if unique_entities <= 1:
            breadth_score = 0.1  # Одна компания
        elif unique_entities <= 3:
            breadth_score = 0.3  # Несколько компаний
        elif unique_entities <= 10:
            breadth_score = 0.6  # Много компаний
        else:
            breadth_score = 0.9  # Очень много компаний
        
        # Бонус за отраслевое разнообразие
        sectors_diversity = await self._get_sectors_diversity(tickers[:5])
        breadth_score += sectors_diversity * 0.2
        
        # Бонус за типы событий с широким охватом
        broad_event_types = {'sanctions', 'regulatory', 'macro', 'market_crash'}
        if event.event_type in broad_event_types:
            breadth_score += 0.2
        
        return max(0.0, min(1.0, breadth_score))

    async def _calculate_price_impact_score(self, event: Event) -> float:
        """
        Price Impact Score: Влияние события на рыночные цены
        
        Использует данные Event Study из графа Neo4j:
        - Abnormal Return (AR)
        - Cumulative Abnormal Return (CAR)
        - Volume spikes
        - Market capitalization impact
        """
        tickers = event.attrs.get("tickers", [])
        
        if not tickers:
            return 0.0  # Нет ценных бумаг для анализа
        
        price_impact_score = 0.0
        ticker_impacts = []
        
        # Получаем данные о рыночном влиянии из Neo4j
        for ticker in tickers[:3]:  # Ограничиваем до 3 тикеров
            impact_query = """
                MATCH (e:EventNode {id: $event_id})-[:IMPACTS]->(i:Instrument {symbol: $ticker})
                RETURN i.price_impact, i.volume_impact, i.sentiment
                LIMIT 1
            """
            
            try:
                result = await self.graph.execute_query(
                    impact_query, 
                    {"event_id": str(event.id), "ticker": ticker}
                )
                
                if result and len(result) > 0:
                    record = result[0]
                    price_impact = record.get('price_impact', 0.0)
                    volume_impact = record.get('volume_impact', 1.0)
                    
                    # Нормализуем влияние цены (AR обычно в диапазоне [-0.1, 0.1])
                    normalized_price_impact = abs(price_impact) * 100  # Конвертируем в проценты
                    
                    # Нормализуем влияние объема
                    normalized_volume_impact = max(0, volume_impact - 1.0) / 5.0  # Assume up to 6x volume
                    
                    # Комбинируем влияние цены и объема
                    ticker_impact = min(1.0, normalized_price_impact * 0.7 + normalized_volume_impact * 0.3)
                    ticker_impacts.append(ticker_impact)
                    
            except Exception as e:
                logger.warning(f"Error fetching price impact for {ticker}: {e}")
        
        # Общая оценка влияния на цены
        if ticker_impacts:
            price_impact_score = mean(ticker_impacts)
            
            # Бонус за высокое влияние
            if max(ticker_impacts) > 0.7:
                price_impact_score += 0.2
        
        return max(0.0, min(1.0, price_impact_score))

    async def _get_event_type_rarity(self, event_type: str) -> float:
        """Получить редкость типа события"""
        
        # Статистика частоты типов событий в системе
        rarity_stats = {
            'sanctions': 0.9,       # Очень редкие
            'default': 0.95,        # Очень редкие
            'ipo': 0.85,           # Редкие
            'm&a': 0.75,           # Умеренно редкие
            'rate_hike': 0.65,      # Умеренные
            'rate_cut': 0.65,       # Умеренные
            'earnings_miss': 0.4,   # Частые
            'earnings_beat': 0.4,   # Частые
            'earnings': 0.3,        # Очень частые
            'dividends': 0.3,       # Очень частые
        }
        
        return rarity_stats.get(event_type, 0.5)

    async def _check_source_correlation(self, event: Event) -> float:
        """
        Проверить корреляцию события с другими источниками
        
        Если похожие события появляются в других источниках -
        это повышает credibility
        """
        correlation_window = timedelta(hours=6)
        
        # Ищем события того же типа в том же окне времени
        correlation_query = """
            SELECT COUNT(DISTINCT sources.kind), COUNT(*)
            FROM events 
            JOIN news ON events.news_id = news.id
            JOIN sources ON news.source_id = sources.id
            WHERE events.event_type = %s 
            AND events.ts >= %s 
            AND events.ts <= %s
            AND events.id != %s
        """
        
        window_start = event.ts - correlation_window
        window_end = event.ts + correlation_window
        
        try:
            corr_result = await self.session.execute(
                correlation_query,
                (event.event_type, window_start, window_end, event.id)
            )
            
            unique_sources, total_events = corr_result.fetchone() or (0, 0)
            
            # Бонус за множественность источников
            source_bonus = min(1.0, unique_sources * 0.3)
            
            # Бонус за количество подтверждающих событий
            events_bonus = min(1.0, (total_events - 1) * 0.2)
            
            return source_bonus + events_bonus
            
        except Exception as e:
            logger.warning(f"Error checking source correlation: {e}")
            return 0.0

    async def _get_sectors_diversity(self, tickers: List[str]) -> float:
        """Получить разнообразие секторов для списка тикеров"""
        
        if not tickers:
            return 0.0
        
        # Получаем сектора для тикеров из Neo4j
        sectors_query = """
            MATCH (i:Instrument)-[:BELONGS_TO]->(s:Sector)
            WHERE i.symbol IN $tickers
            RETURN DISTINCT s.name as sector
            LIMIT 10
        """
        
        try:
            result = await self.graph.execute_query(
                sectors_query,
                {"tickers": tickers}
            )
            
            sectors = [record.get('sector') for record in result] if result else []
            unique_sectors = len(set(sectors))
            
            # Разнообразие секторов нормализуем [0, 1]
            return min(1.0, unique_sectors / max(len(tickers), 1))
            
        except Exception as e:
            logger.warning(f"Error getting sectors diversity: {e}")
            return 0.0

    async def batch_calculate_importance(self, events: List[Event]) -> Dict[str, Dict[str, Any]]:
        """
        Пакетный расчет важности для списка событий
        
        Args:
            events: Список событий
            
        Returns:
            Словарь {event_id: importance_data}
        """
        logger.info(f"Batch calculating importance for {len(events)} events")
        
        results = {}
        
        for event in events:
            try:
                importance_data = await self.calculate_importance_score(event)
                results[str(event.id)] = importance_data
            except Exception as e:
                logger.error(f"Error in batch calculation for event {event.id}: {e}")
                results[str(event.id)] = {
                    'importance_score': 0.0,
                    'error': str(e)
                }
        
        return results

    def update_weights(self, new_weights: Dict[str, float]):
        """Обновить веса компонентов важности"""
        
        # Проверяем сумму весов = 1.0
        total_weight = sum(new_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"Weights sum to {total_weight}, should be 1.0")
        
        # Нормализуем веса
        normalized_weights = {
            key: value / total_weight 
            for key, value in new_weights.items()
        }
        
        self.weights.update(normalized_weights)
        logger.info(f"Updated importance weights: {self.weights}")
