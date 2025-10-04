# src/services/covariance_service.py
"""
Сервис для расчета корреляций между компаниями
Реализует логику COVARIATES_WITH связей из Project Charter
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
try:
    import numpy as np
    import pandas as pd
except ImportError:
    # Fallback для случаев когда numpy/pandas не установлены
    np = None
    pd = None
from dataclasses import dataclass

from src.core.config import settings
from src.graph_models import GraphService

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Результат расчета корреляции"""
    company1_id: str
    company2_id: str
    correlation: float
    window: str
    confidence: float
    sample_size: int


class CovarianceService:
    """
    Сервис для расчета корреляций между компаниями
    """
    
    def __init__(self):
        self.graph: Optional[GraphService] = None
        self.market_data_service = None
        self._correlation_cache: Dict[str, float] = {}
        
    async def initialize(self):
        """Инициализация сервиса"""
        self.graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Инициализируем market data service для получения исторических данных
        try:
            from src.services.market_data_service import MarketDataService
            self.market_data_service = MarketDataService()
            await self.market_data_service.initialize()
        except ImportError:
            logger.warning("MarketDataService not available, using mock data")
            self.market_data_service = None
        
        logger.info("CovarianceService initialized")
    
    async def close(self):
        """Закрытие соединений"""
        if self.graph:
            await self.graph.close()
        if self.market_data_service:
            await self.market_data_service.close()
    
    async def calculate_correlations_for_company(
        self, 
        company_id: str, 
        window: str = "1Y",
        min_correlation: float = 0.3,
        max_companies: int = 10
    ) -> List[CorrelationResult]:
        """
        Рассчитать корреляции для одной компании с другими
        
        Args:
            company_id: ID компании
            window: Окно для расчета (1M, 3M, 6M, 1Y, 2Y, 5Y)
            min_correlation: Минимальная корреляция для включения
            max_companies: Максимальное количество компаний для расчета
            
        Returns:
            Список результатов корреляции
        """
        
        # Получаем список всех компаний
        all_companies = await self._get_all_companies()
        
        if company_id not in all_companies:
            logger.warning(f"Company {company_id} not found")
            return []
        
        # Ограничиваем количество компаний для расчета
        companies_to_check = all_companies[:max_companies] if max_companies else all_companies
        
        results = []
        
        for other_company_id in companies_to_check:
            if other_company_id == company_id:
                continue
                
            try:
                correlation = await self._calculate_pair_correlation(
                    company_id, other_company_id, window
                )
                
                if correlation and abs(correlation.correlation) >= min_correlation:
                    results.append(correlation)
                    
            except Exception as e:
                logger.debug(f"Failed to calculate correlation {company_id}-{other_company_id}: {e}")
                continue
        
        # Сортируем по абсолютному значению корреляции
        results.sort(key=lambda x: abs(x.correlation), reverse=True)
        
        return results
    
    async def _calculate_pair_correlation(
        self, 
        company1_id: str, 
        company2_id: str, 
        window: str
    ) -> Optional[CorrelationResult]:
        """Рассчитать корреляцию между двумя компаниями"""
        
        # Проверяем кеш
        cache_key = f"{company1_id}:{company2_id}:{window}"
        if cache_key in self._correlation_cache:
            cached_corr = self._correlation_cache[cache_key]
            return CorrelationResult(
                company1_id=company1_id,
                company2_id=company2_id,
                correlation=cached_corr,
                window=window,
                confidence=0.8,  # Кешированные данные имеют меньшую уверенность
                sample_size=0
            )
        
        try:
            # Получаем исторические данные для обеих компаний
            prices1 = await self._get_historical_prices(company1_id, window)
            prices2 = await self._get_historical_prices(company2_id, window)
            
            if not prices1 or not prices2:
                return None
            
            # Выравниваем данные по датам
            aligned_data = self._align_price_data(prices1, prices2)
            
            if len(aligned_data) < 10:  # Минимум данных для корреляции
                return None
            
            # Рассчитываем корреляцию
            correlation = self._calculate_correlation_coefficient(aligned_data)
            
            # Сохраняем в кеш
            self._correlation_cache[cache_key] = correlation
            
            # Определяем уверенность на основе размера выборки
            confidence = min(1.0, len(aligned_data) / 252)  # 252 торговых дня в году
            
            result = CorrelationResult(
                company1_id=company1_id,
                company2_id=company2_id,
                correlation=correlation,
                window=window,
                confidence=confidence,
                sample_size=len(aligned_data)
            )
            
            # Сохраняем в граф
            await self._save_correlation_to_graph(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error calculating correlation {company1_id}-{company2_id}: {e}")
            return None
    
    async def _get_historical_prices(self, company_id: str, window: str) -> Optional[List[Dict]]:
        """Получить исторические цены для компании"""
        
        try:
            # Извлекаем тикер из company_id (формат: moex:TICKER)
            if ":" in company_id:
                ticker = company_id.split(":")[1]
            else:
                ticker = company_id
            
            # Определяем период
            end_date = datetime.now()
            if window == "1M":
                start_date = end_date - timedelta(days=30)
            elif window == "3M":
                start_date = end_date - timedelta(days=90)
            elif window == "6M":
                start_date = end_date - timedelta(days=180)
            elif window == "1Y":
                start_date = end_date - timedelta(days=365)
            elif window == "2Y":
                start_date = end_date - timedelta(days=730)
            elif window == "5Y":
                start_date = end_date - timedelta(days=1825)
            else:
                start_date = end_date - timedelta(days=365)  # По умолчанию 1 год
            
            # Получаем данные через market data service
            if self.market_data_service:
                prices = await self.market_data_service.get_historical_prices(
                    ticker, start_date, end_date
                )
                return prices
            
            # Fallback: симуляция данных для тестирования
            return self._generate_mock_prices(start_date, end_date)
            
        except Exception as e:
            logger.error(f"Error getting historical prices for {company_id}: {e}")
            return None
    
    def _align_price_data(self, prices1: List[Dict], prices2: List[Dict]) -> List[Tuple[float, float]]:
        """Выровнять данные по ценам по датам"""
        
        if not pd:
            # Простая реализация без pandas
            return self._align_price_data_simple(prices1, prices2)
        
        # Создаем DataFrame для удобства работы
        df1 = pd.DataFrame(prices1)
        df2 = pd.DataFrame(prices2)
        
        if df1.empty or df2.empty:
            return []
        
        # Преобразуем даты
        df1['date'] = pd.to_datetime(df1['date'])
        df2['date'] = pd.to_datetime(df2['date'])
        
        # Объединяем по датам
        merged = pd.merge(df1, df2, on='date', suffixes=('_1', '_2'))
        
        if merged.empty:
            return []
        
        # Возвращаем пары цен
        return list(zip(merged['close_1'].tolist(), merged['close_2'].tolist()))
    
    def _align_price_data_simple(self, prices1: List[Dict], prices2: List[Dict]) -> List[Tuple[float, float]]:
        """Простая реализация выравнивания данных без pandas"""
        
        # Создаем словари по датам
        dict1 = {p['date']: p['close'] for p in prices1}
        dict2 = {p['date']: p['close'] for p in prices2}
        
        # Находим общие даты
        common_dates = set(dict1.keys()) & set(dict2.keys())
        
        # Возвращаем пары цен для общих дат
        return [(dict1[date], dict2[date]) for date in sorted(common_dates)]
    
    def _calculate_correlation_coefficient(self, price_pairs: List[Tuple[float, float]]) -> float:
        """Рассчитать коэффициент корреляции Пирсона"""
        
        if len(price_pairs) < 2:
            return 0.0
        
        prices1, prices2 = zip(*price_pairs)
        
        if np:
            # Используем numpy если доступен
            correlation = np.corrcoef(prices1, prices2)[0, 1]
            
            # Обрабатываем NaN
            if np.isnan(correlation):
                return 0.0
            
            return float(correlation)
        else:
            # Простая реализация без numpy
            return self._calculate_correlation_simple(prices1, prices2)
    
    def _calculate_correlation_simple(self, prices1: List[float], prices2: List[float]) -> float:
        """Простая реализация корреляции без numpy"""
        
        if len(prices1) != len(prices2) or len(prices1) < 2:
            return 0.0
        
        n = len(prices1)
        
        # Средние значения
        mean1 = sum(prices1) / n
        mean2 = sum(prices2) / n
        
        # Вычисляем корреляцию
        numerator = sum((p1 - mean1) * (p2 - mean2) for p1, p2 in zip(prices1, prices2))
        
        sum_sq1 = sum((p1 - mean1) ** 2 for p1 in prices1)
        sum_sq2 = sum((p2 - mean2) ** 2 for p2 in prices2)
        
        denominator = (sum_sq1 * sum_sq2) ** 0.5
        
        if denominator == 0:
            return 0.0
        
        return numerator / denominator
    
    async def _save_correlation_to_graph(self, result: CorrelationResult):
        """Сохранить корреляцию в граф"""
        
        if not self.graph:
            return
        
        try:
            await self.graph.link_company_covariates_with(
                company1_id=result.company1_id,
                company2_id=result.company2_id,
                rho=result.correlation,
                window=result.window
            )
            
            logger.debug(f"Saved correlation {result.company1_id}-{result.company2_id}: {result.correlation:.3f}")
            
        except Exception as e:
            logger.error(f"Failed to save correlation to graph: {e}")
    
    async def _get_all_companies(self) -> List[str]:
        """Получить список всех компаний из графа"""
        
        if not self.graph:
            return []
        
        async with self.graph.driver.session() as session:
            query = """
            MATCH (c:Company)
            WHERE c.ticker IS NOT NULL
            RETURN c.id as company_id
            ORDER BY c.ticker
            """
            
            result = await session.run(query)
            companies = [record["company_id"] async for record in result]
            
            return companies
    
    def _generate_mock_prices(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Генерировать тестовые данные цен"""
        
        import random
        
        prices = []
        current_date = start_date
        
        while current_date <= end_date:
            # Генерируем случайные цены с трендом
            base_price = 100 + random.uniform(-20, 20)
            prices.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "close": base_price,
                "open": base_price * random.uniform(0.98, 1.02),
                "high": base_price * random.uniform(1.0, 1.05),
                "low": base_price * random.uniform(0.95, 1.0),
                "volume": random.randint(100000, 1000000)
            })
            
            current_date += timedelta(days=1)
        
        return prices
    
    async def get_top_correlated_companies(
        self, 
        company_id: str, 
        limit: int = 10,
        min_correlation: float = 0.5
    ) -> List[Dict]:
        """Получить топ коррелированных компаний"""
        
        correlations = await self.calculate_correlations_for_company(
            company_id, 
            min_correlation=min_correlation,
            max_companies=50  # Проверяем больше компаний для лучшего результата
        )
        
        # Ограничиваем результат
        top_correlations = correlations[:limit]
        
        # Форматируем результат
        result = []
        for corr in top_correlations:
            result.append({
                "company_id": corr.company2_id,
                "correlation": corr.correlation,
                "confidence": corr.confidence,
                "sample_size": corr.sample_size,
                "window": corr.window
            })
        
        return result
    
    async def update_all_correlations(self, window: str = "1Y"):
        """Обновить корреляции для всех компаний"""
        
        companies = await self._get_all_companies()
        logger.info(f"Updating correlations for {len(companies)} companies")
        
        updated_count = 0
        
        for company_id in companies:
            try:
                correlations = await self.calculate_correlations_for_company(
                    company_id, window=window, max_companies=20
                )
                
                updated_count += len(correlations)
                
                if updated_count % 100 == 0:
                    logger.info(f"Updated {updated_count} correlations")
                
            except Exception as e:
                logger.error(f"Failed to update correlations for {company_id}: {e}")
                continue
        
        logger.info(f"Correlation update completed. Total correlations: {updated_count}")
        return updated_count


# ============================================================================
# Утилиты для работы с корреляциями
# ============================================================================

class CorrelationAnalyzer:
    """Анализ корреляций между компаниями"""
    
    def __init__(self, covariance_service: CovarianceService):
        self.covariance_service = covariance_service
    
    async def find_correlation_clusters(self, min_correlation: float = 0.7) -> Dict[str, List[str]]:
        """Найти кластеры сильно коррелированных компаний"""
        
        companies = await self.covariance_service._get_all_companies()
        clusters = {}
        visited = set()
        
        for company_id in companies:
            if company_id in visited:
                continue
            
            # Находим все компании, коррелированные с текущей
            correlations = await self.covariance_service.calculate_correlations_for_company(
                company_id, min_correlation=min_correlation
            )
            
            if correlations:
                cluster = [company_id]
                for corr in correlations:
                    cluster.append(corr.company2_id)
                    visited.add(corr.company2_id)
                
                clusters[company_id] = cluster
                visited.add(company_id)
        
        return clusters
    
    async def analyze_sector_correlations(self) -> Dict[str, float]:
        """Анализ корреляций внутри секторов"""
        
        # Получаем компании по секторам
        sectors = await self._get_companies_by_sector()
        sector_correlations = {}
        
        for sector, companies in sectors.items():
            if len(companies) < 2:
                continue
            
            correlations = []
            
            # Рассчитываем корреляции между всеми парами в секторе
            for i, company1 in enumerate(companies):
                for company2 in companies[i+1:]:
                    corr = await self.covariance_service._calculate_pair_correlation(
                        company1, company2, "1Y"
                    )
                    if corr:
                        correlations.append(abs(corr.correlation))
            
            if correlations:
                if np:
                    sector_correlations[sector] = np.mean(correlations)
                else:
                    sector_correlations[sector] = sum(correlations) / len(correlations)
        
        return sector_correlations
    
    async def _get_companies_by_sector(self) -> Dict[str, List[str]]:
        """Получить компании, сгруппированные по секторам"""
        
        if not self.covariance_service.graph:
            return {}
        
        async with self.covariance_service.graph.driver.session() as session:
            query = """
            MATCH (c:Company)-[:IN_SECTOR]->(s:Sector)
            RETURN s.name as sector, collect(c.id) as companies
            """
            
            result = await session.run(query)
            sectors = {record["sector"]: record["companies"] async for record in result}
            
            return sectors


# ============================================================================
# Пример использования
# ============================================================================

async def example_usage():
    """Пример использования CovarianceService"""
    
    service = CovarianceService()
    await service.initialize()
    
    try:
        # Пример расчета корреляций для Сбербанка
        sber_id = "moex:SBER"
        
        correlations = await service.calculate_correlations_for_company(
            sber_id, 
            window="1Y",
            min_correlation=0.3,
            max_companies=10
        )
        
        print(f"Correlations for {sber_id}:")
        for corr in correlations:
            print(f"  {corr.company2_id}: {corr.correlation:.3f} (confidence: {corr.confidence:.2f})")
        
        # Анализ кластеров
        analyzer = CorrelationAnalyzer(service)
        clusters = await analyzer.find_correlation_clusters(min_correlation=0.7)
        
        print(f"\nFound {len(clusters)} correlation clusters:")
        for leader, cluster in clusters.items():
            print(f"  Cluster {leader}: {len(cluster)} companies")
        
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(example_usage())