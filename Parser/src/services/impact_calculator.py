#Parser.src/services/impact_calculator.py
"""
Сервис для расчета влияния новостей на компании
Реализует логику AFFECTS связей из Project Charter
"""

import logging
import asyncio
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from Parser.src.core.config import settings
from Parser.src.graph_models import GraphService

logger = logging.getLogger(__name__)


class ImpactWindow(str, Enum):
    """Временные окна для анализа влияния"""
    W15M = "15m"
    W1H = "1h"
    W1D = "1d"
    W5D = "5d"


class ImpactMethod(str, Enum):
    """Методы расчета влияния"""
    PRICE_CHANGE = "price_change"
    VOLUME_CHANGE = "volume_change"
    VOLATILITY_CHANGE = "volatility_change"
    COMBINED = "combined"


@dataclass
class MarketData:
    """Рыночные данные"""
    timestamp: datetime
    price: float
    volume: int
    volatility: Optional[float] = None


@dataclass
class ImpactResult:
    """Результат расчета влияния"""
    company_id: str
    news_id: str
    window: ImpactWindow
    method: ImpactMethod
    weight: float
    price_change_pct: float
    volume_change_pct: float
    volatility_change_pct: Optional[float]
    z_score: float
    confidence: float
    no_impact: bool = False


class ImpactCalculator:
    """
    Калькулятор влияния новостей на компании
    """
    
    def __init__(self):
        self.graph: Optional[GraphService] = None
        self.market_data_service = None
        
        # Пороги для определения значимости влияния
        self.price_threshold = 0.02  # 2%
        self.volume_threshold = 0.5  # 50%
        self.volatility_threshold = 0.1  # 10%
        self.z_score_threshold = 1.96  # 95% доверительный интервал
        
        # Параметры затухания
        self.decay_lambda = 0.1  # Коэффициент затухания
        
    async def initialize(self):
        """Инициализация сервиса"""
        self.graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Инициализируем market data service
        try:
            from Parser.src.services.market_data_service import MarketDataService
            self.market_data_service = MarketDataService()
            await self.market_data_service.initialize()
        except ImportError:
            logger.warning("MarketDataService not available, using mock data")
            self.market_data_service = None
        
        logger.info("ImpactCalculator initialized")
    
    async def close(self):
        """Закрытие соединений"""
        if self.graph:
            await self.graph.close()
        if self.market_data_service:
            await self.market_data_service.close()
    
    async def calculate_impact(
        self, 
        news_id: str,
        company_id: str,
        news_published_at: datetime,
        windows: List[ImpactWindow] = None
    ) -> List[ImpactResult]:
        """
        Рассчитать влияние новости на компанию
        
        Args:
            news_id: ID новости
            company_id: ID компании
            news_published_at: Время публикации новости
            windows: Список временных окон для анализа
        
        Returns:
            Список результатов влияния для разных окон
        """
        
        if windows is None:
            windows = [ImpactWindow.W15M, ImpactWindow.W1H, ImpactWindow.W1D]
        
        results = []
        
        for window in windows:
            try:
                impact = await self._calculate_window_impact(
                    news_id, company_id, news_published_at, window
                )
                
                if impact:
                    results.append(impact)
                    
            except Exception as e:
                logger.error(f"Failed to calculate impact for window {window}: {e}")
                continue
        
        return results
    
    async def _calculate_window_impact(
        self,
        news_id: str,
        company_id: str,
        news_published_at: datetime,
        window: ImpactWindow
    ) -> Optional[ImpactResult]:
        """Рассчитать влияние для конкретного временного окна"""
        
        # Извлекаем тикер из company_id
        ticker = self._extract_ticker(company_id)
        if not ticker:
            return None
        
        # Определяем временные границы
        window_start, window_end = self._get_window_boundaries(
            news_published_at, window
        )
        
        # Получаем данные до и после новости
        before_data = await self._get_market_data_before(ticker, news_published_at, window)
        after_data = await self._get_market_data_after(ticker, window_start, window_end)
        
        if not before_data or not after_data:
            logger.debug(f"Insufficient market data for {ticker}")
            return None
        
        # Рассчитываем изменения
        price_change_pct = self._calculate_price_change(before_data, after_data)
        volume_change_pct = self._calculate_volume_change(before_data, after_data)
        volatility_change_pct = self._calculate_volatility_change(before_data, after_data)
        
        # Рассчитываем Z-score
        z_score = self._calculate_z_score(price_change_pct)
        
        # Определяем, есть ли значимое влияние
        no_impact = self._is_no_impact(
            price_change_pct, volume_change_pct, volatility_change_pct, z_score
        )
        
        # Рассчитываем вес влияния
        weight = self._calculate_impact_weight(
            price_change_pct, volume_change_pct, volatility_change_pct, 
            news_published_at, z_score
        )
        
        # Рассчитываем уверенность
        confidence = self._calculate_confidence(
            before_data, after_data, z_score
        )
        
        result = ImpactResult(
            company_id=company_id,
            news_id=news_id,
            window=window,
            method=ImpactMethod.COMBINED,
            weight=weight,
            price_change_pct=price_change_pct,
            volume_change_pct=volume_change_pct,
            volatility_change_pct=volatility_change_pct,
            z_score=z_score,
            confidence=confidence,
            no_impact=no_impact
        )
        
        # Сохраняем в граф
        if not no_impact:
            await self._save_impact_to_graph(result)
        
        return result
    
    def _extract_ticker(self, company_id: str) -> Optional[str]:
        """Извлечь тикер из company_id"""
        
        if ":" in company_id:
            return company_id.split(":")[1]
        return company_id
    
    def _get_window_boundaries(
        self, 
        news_published_at: datetime, 
        window: ImpactWindow
    ) -> Tuple[datetime, datetime]:
        """Получить временные границы для анализа"""
        
        window_start = news_published_at
        
        if window == ImpactWindow.W15M:
            window_end = news_published_at + timedelta(minutes=15)
        elif window == ImpactWindow.W1H:
            window_end = news_published_at + timedelta(hours=1)
        elif window == ImpactWindow.W1D:
            window_end = news_published_at + timedelta(days=1)
        elif window == ImpactWindow.W5D:
            window_end = news_published_at + timedelta(days=5)
        else:
            window_end = news_published_at + timedelta(hours=1)
        
        return window_start, window_end
    
    async def _get_market_data_before(
        self, 
        ticker: str, 
        news_published_at: datetime,
        window: ImpactWindow
    ) -> Optional[MarketData]:
        """Получить рыночные данные до публикации новости"""
        
        # Определяем период для получения "до" данных
        if window == ImpactWindow.W15M:
            lookback = timedelta(hours=1)
        elif window == ImpactWindow.W1H:
            lookback = timedelta(hours=4)
        elif window == ImpactWindow.W1D:
            lookback = timedelta(days=1)
        elif window == ImpactWindow.W5D:
            lookback = timedelta(days=5)
        else:
            lookback = timedelta(hours=1)
        
        start_time = news_published_at - lookback
        
        try:
            # Получаем данные через market data service
            if self.market_data_service:
                data = await self.market_data_service.get_market_data_in_range(
                    ticker, start_time, news_published_at
                )
                
                if data:
                    # Берем последнюю точку данных
                    last_point = data[-1]
                    return MarketData(
                        timestamp=last_point['timestamp'],
                        price=last_point['price'],
                        volume=last_point['volume'],
                        volatility=last_point.get('volatility')
                    )
            
            # Fallback: симуляция данных
            return self._generate_mock_data(news_published_at - timedelta(minutes=5))
            
        except Exception as e:
            logger.error(f"Error getting 'before' data for {ticker}: {e}")
            return None
    
    async def _get_market_data_after(
        self, 
        ticker: str, 
        window_start: datetime,
        window_end: datetime
    ) -> Optional[MarketData]:
        """Получить рыночные данные после публикации новости"""
        
        try:
            # Получаем данные через market data service
            if self.market_data_service:
                data = await self.market_data_service.get_market_data_in_range(
                    ticker, window_start, window_end
                )
                
                if data:
                    # Берем последнюю точку данных
                    last_point = data[-1]
                    return MarketData(
                        timestamp=last_point['timestamp'],
                        price=last_point['price'],
                        volume=last_point['volume'],
                        volatility=last_point.get('volatility')
                    )
            
            # Fallback: симуляция данных
            return self._generate_mock_data(window_end)
            
        except Exception as e:
            logger.error(f"Error getting 'after' data for {ticker}: {e}")
            return None
    
    def _calculate_price_change(self, before: MarketData, after: MarketData) -> float:
        """Рассчитать изменение цены в процентах"""
        
        if before.price == 0:
            return 0.0
        
        return (after.price - before.price) / before.price
    
    def _calculate_volume_change(self, before: MarketData, after: MarketData) -> float:
        """Рассчитать изменение объема в процентах"""
        
        if before.volume == 0:
            return 0.0
        
        return (after.volume - before.volume) / before.volume
    
    def _calculate_volatility_change(self, before: MarketData, after: MarketData) -> Optional[float]:
        """Рассчитать изменение волатильности в процентах"""
        
        if not before.volatility or not after.volatility:
            return None
        
        if before.volatility == 0:
            return 0.0
        
        return (after.volatility - before.volatility) / before.volatility
    
    def _calculate_z_score(self, price_change_pct: float) -> float:
        """Рассчитать Z-score для изменения цены"""
        
        # Используем исторические данные для расчета стандартного отклонения
        # В реальной реализации здесь должен быть анализ исторических данных
        historical_std = 0.03  # 3% - примерное стандартное отклонение дневных изменений
        
        return price_change_pct / historical_std if historical_std > 0 else 0.0
    
    def _is_no_impact(
        self,
        price_change_pct: float,
        volume_change_pct: float,
        volatility_change_pct: Optional[float],
        z_score: float
    ) -> bool:
        """Определить, есть ли значимое влияние"""
        
        # Проверяем все пороги
        if abs(price_change_pct) < self.price_threshold:
            return True
        
        if abs(volume_change_pct) < self.volume_threshold:
            return True
        
        if volatility_change_pct and abs(volatility_change_pct) < self.volatility_threshold:
            return True
        
        if abs(z_score) < self.z_score_threshold:
            return True
        
        return False
    
    def _calculate_impact_weight(
        self,
        price_change_pct: float,
        volume_change_pct: float,
        volatility_change_pct: Optional[float],
        news_published_at: datetime,
        z_score: float
    ) -> float:
        """
        Рассчитать вес влияния по формуле из Project Charter:
        w = s · f(ΔP%, ΔVol%, recency, source_cred)
        """
        
        # Знак влияния
        s = 1.0 if price_change_pct >= 0 else -1.0
        
        # Нормализующая функция
        f = self._normalizing_function(
            price_change_pct, volume_change_pct, volatility_change_pct, z_score
        )
        
        # Затухание по времени
        time_decay = self._calculate_time_decay(news_published_at)
        
        # Уверенность источника (пока константа)
        source_credibility = 0.8
        
        # Итоговый вес
        weight = s * f * time_decay * source_credibility
        
        # Клиппинг в диапазоне [-1, 1]
        return max(-1.0, min(1.0, weight))
    
    def _normalizing_function(
        self,
        price_change_pct: float,
        volume_change_pct: float,
        volatility_change_pct: Optional[float],
        z_score: float
    ) -> float:
        """Нормализующая функция для расчета веса"""
        
        # Базовый вес на основе изменения цены
        price_weight = min(abs(price_change_pct) / self.price_threshold, 1.0)
        
        # Бонус за объем
        volume_bonus = min(abs(volume_change_pct) / self.volume_threshold, 1.0) * 0.3
        
        # Бонус за волатильность
        volatility_bonus = 0.0
        if volatility_change_pct:
            volatility_bonus = min(abs(volatility_change_pct) / self.volatility_threshold, 1.0) * 0.2
        
        # Бонус за Z-score
        z_score_bonus = min(abs(z_score) / self.z_score_threshold, 1.0) * 0.2
        
        return price_weight + volume_bonus + volatility_bonus + z_score_bonus
    
    def _calculate_time_decay(self, news_published_at: datetime) -> float:
        """Рассчитать затухание по времени"""
        
        time_diff = datetime.now() - news_published_at
        hours_passed = time_diff.total_seconds() / 3600
        
        # Экспоненциальное затухание
        return math.exp(-self.decay_lambda * hours_passed)
    
    def _calculate_confidence(
        self,
        before: MarketData,
        after: MarketData,
        z_score: float
    ) -> float:
        """Рассчитать уверенность в результате"""
        
        # Базовая уверенность
        confidence = 0.5
        
        # Бонус за Z-score
        if abs(z_score) > self.z_score_threshold:
            confidence += 0.3
        
        # Бонус за объем данных
        if before.volume > 1000000 and after.volume > 1000000:  # Высокая ликвидность
            confidence += 0.2
        
        return min(1.0, confidence)
    
    async def _save_impact_to_graph(self, result: ImpactResult):
        """Сохранить результат влияния в граф"""
        
        if not self.graph:
            return
        
        try:
            await self.graph.link_news_affects_company(
                news_id=result.news_id,
                company_id=result.company_id,
                weight=result.weight,
                window=result.window.value,
                method=result.method.value
            )
            
            logger.debug(f"Saved impact {result.news_id}->{result.company_id}: {result.weight:.3f}")
            
        except Exception as e:
            logger.error(f"Failed to save impact to graph: {e}")
    
    def _generate_mock_data(self, timestamp: datetime) -> MarketData:
        """Генерировать тестовые данные"""
        
        import random
        
        return MarketData(
            timestamp=timestamp,
            price=100 + random.uniform(-5, 5),
            volume=random.randint(500000, 2000000),
            volatility=random.uniform(0.1, 0.3)
        )
    
    async def process_news_impact(self, news_id: str, company_ids: List[str], published_at: datetime):
        """Обработать влияние новости на список компаний"""
        
        results = []
        
        for company_id in company_ids:
            try:
                impacts = await self.calculate_impact(
                    news_id=news_id,
                    company_id=company_id,
                    news_published_at=published_at
                )
                
                results.extend(impacts)
                
            except Exception as e:
                logger.error(f"Failed to process impact for {company_id}: {e}")
                continue
        
        return results
    
    async def get_impact_statistics(self, company_id: str, days: int = 30) -> Dict:
        """Получить статистику влияния для компании"""
        
        if not self.graph:
            return {}
        
        async with self.graph.driver.session() as session:
            query = """
            MATCH (n:News)-[r:AFFECTS]->(c:Company {id: $company_id})
            WHERE n.published_at >= datetime() - duration('P%dD')
            RETURN 
                avg(r.weight) as avg_weight,
                max(r.weight) as max_weight,
                min(r.weight) as min_weight,
                count(r) as total_impacts,
                count(CASE WHEN r.weight > 0 THEN 1 END) as positive_impacts,
                count(CASE WHEN r.weight < 0 THEN 1 END) as negative_impacts
            """ % days
            
            result = await session.run(query, company_id=company_id)
            record = await result.single()
            
            if record:
                return {
                    "average_weight": record["avg_weight"],
                    "max_weight": record["max_weight"],
                    "min_weight": record["min_weight"],
                    "total_impacts": record["total_impacts"],
                    "positive_impacts": record["positive_impacts"],
                    "negative_impacts": record["negative_impacts"]
                }
        
        return {}


# ============================================================================
# Пример использования
# ============================================================================

async def example_usage():
    """Пример использования ImpactCalculator"""
    
    calculator = ImpactCalculator()
    await calculator.initialize()
    
    try:
        # Пример расчета влияния
        news_id = "news_123"
        company_id = "moex:SBER"
        published_at = datetime.now() - timedelta(hours=2)
        
        impacts = await calculator.calculate_impact(
            news_id=news_id,
            company_id=company_id,
            news_published_at=published_at
        )
        
        print(f"Impact results for {news_id} -> {company_id}:")
        for impact in impacts:
            print(f"  Window {impact.window}: weight={impact.weight:.3f}, "
                  f"price_change={impact.price_change_pct:.2%}, "
                  f"confidence={impact.confidence:.2f}")
        
        # Статистика влияния
        stats = await calculator.get_impact_statistics(company_id, days=7)
        print(f"\nImpact statistics for {company_id}:")
        print(f"  Average weight: {stats.get('average_weight', 0):.3f}")
        print(f"  Total impacts: {stats.get('total_impacts', 0)}")
        
    finally:
        await calculator.close()


if __name__ == "__main__":
    asyncio.run(example_usage())