# src/services/moex/moex_prices.py
"""
MOEX Price Service via Algopack API - получение исторических и текущих цен MOEX
Event Study Analysis - расчет AR, CAR, volume spikes
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import httpx
from statistics import mean, stdev

from src.core.config import settings

logger = logging.getLogger(__name__)


class MOEXPriceService:
    """
    Сервис для получения цен через Algopack API
    Документация Algopack: см. ALGOPACK_BASE_URL
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {settings.ALGOPACK_API_KEY}",
                "User-Agent": "RADAR-AI-CEG/1.0"
            }
        )
        self.base_url = settings.ALGOPACK_BASE_URL

    async def close(self):
        await self.client.aclose()

    async def get_candles(
        self,
        secid: str,
        from_date: datetime,
        to_date: datetime,
        interval: str = "1d"  # 1m, 5m, 1h, 1d
    ) -> List[Dict[str, Any]]:
        """
        Получить свечи (OHLCV) для инструмента через Algopack

        Args:
            secid: MOEX security ID (например, SBER)
            from_date: Начало периода
            to_date: Конец периода
            interval: Интервал свечи (1m, 5m, 1h, 1d)

        Returns:
            Список свечей [{timestamp, open, high, low, close, volume}, ...]
        """
        try:
            url = f"{self.base_url}/candles/{secid}"
            params = {
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "interval": interval,
                "market": "shares"
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            candles = data.get("candles", [])

            if not candles:
                logger.warning(f"No candles data for {secid} from {from_date} to {to_date}")
                return []

            logger.info(f"Fetched {len(candles)} candles for {secid}")
            return candles

        except httpx.HTTPError as e:
            logger.error(f"Algopack API error for {secid}: {e}")
            return []

    async def get_last_price(self, secid: str) -> Optional[float]:
        """Получить последнюю цену инструмента через Algopack"""
        try:
            url = f"{self.base_url}/securities/{secid}/quote"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            last_price = data.get("last") or data.get("close") or data.get("prevprice")
            return float(last_price) if last_price else None

        except Exception as e:
            logger.error(f"Error fetching last price for {secid}: {e}")
            return None

    async def get_historical_prices(
        self,
        secid: str,
        from_date: datetime,
        to_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Получить исторические дневные цены через Algopack

        Returns:
            [{timestamp, date, open, close, low, high, volume}, ...]
        """
        try:
            url = f"{self.base_url}/history/{secid}"
            params = {
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "market": "shares"
            }

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            prices = data.get("history", [])
            return prices

        except Exception as e:
            logger.error(f"Error fetching historical prices for {secid}: {e}")
            return []

    async def get_market_status(self, secid: str) -> Dict[str, Any]:
        """
        Получить статус торгов инструмента

        Returns:
            {
                'is_traded': bool,
                'board': str,
                'market_cap': float,
                'shares_outstanding': int
            }
        """
        try:
            url = f"{self.base_url}/securities/{secid}"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            security = data.get("security", {})

            return {
                "is_traded": security.get("is_traded", False),
                "board": security.get("primary_boardid"),
                "market_cap": security.get("market_cap"),
                "shares_outstanding": security.get("shares_outstanding"),
                "sector": security.get("sector"),
                "isin": security.get("isin")
            }

        except Exception as e:
            logger.error(f"Error fetching market status for {secid}: {e}")
            return {}


class EventStudyAnalyzer:
    """
    Event Study Analysis - анализ влияния событий на цены
    Рассчитывает AR (Abnormal Return), CAR (Cumulative AR), volume spikes
    """

    def __init__(self, moex_service: MOEXPriceService):
        self.moex = moex_service

    async def calculate_abnormal_return(
        self,
        secid: str,
        event_date: datetime,
        estimation_window: int = 30,  # Окно оценки нормального возврата
        event_window: Tuple[int, int] = (-1, 1)  # Окно события (дни до/после)
    ) -> Dict[str, Any]:
        """
        Рассчитать Abnormal Return для события

        Args:
            secid: MOEX security ID
            event_date: Дата события
            estimation_window: Размер окна для оценки (дней до события)
            event_window: Окно события (дни до, дни после)

        Returns:
            {
                'ar': abnormal_return,
                'car': cumulative_abnormal_return,
                'volume_spike': volume_ratio,
                'estimation_mean': mean_return,
                'estimation_std': std_return,
                'event_window_returns': [...]
            }
        """
        # Определяем период для получения данных
        start_date = event_date - timedelta(days=estimation_window + abs(event_window[0]) + 5)
        end_date = event_date + timedelta(days=event_window[1] + 5)

        # Получаем исторические цены
        prices = await self.moex.get_historical_prices(secid, start_date, end_date)

        if len(prices) < estimation_window:
            logger.warning(f"Not enough data for {secid}, need {estimation_window} days")
            return None

        # Рассчитываем дневные возвраты
        returns = []
        volumes = []
        dates = []

        for i in range(1, len(prices)):
            prev_close = prices[i-1].get("CLOSE")
            curr_close = prices[i].get("CLOSE")
            volume = prices[i].get("VOLUME", 0)
            date = prices[i].get("TRADEDATE")

            if prev_close and curr_close and prev_close > 0:
                ret = (curr_close - prev_close) / prev_close
                returns.append(ret)
                volumes.append(volume)
                dates.append(date)

        if len(returns) < estimation_window:
            return None

        # Находим индекс даты события
        event_date_str = event_date.strftime("%Y-%m-%d")
        try:
            event_idx = dates.index(event_date_str)
        except ValueError:
            # Ищем ближайшую дату
            event_idx = None
            for i, d in enumerate(dates):
                if d >= event_date_str:
                    event_idx = i
                    break

            if event_idx is None:
                logger.warning(f"Event date {event_date_str} not found in data")
                return None

        # Estimation window (до события)
        estimation_start = max(0, event_idx - estimation_window)
        estimation_returns = returns[estimation_start:event_idx]

        if len(estimation_returns) < 10:
            logger.warning(f"Not enough estimation data for {secid}")
            return None

        # Рассчитываем средний возврат и стандартное отклонение
        mean_return = mean(estimation_returns)
        std_return = stdev(estimation_returns) if len(estimation_returns) > 1 else 0.0

        # Event window returns
        event_start_idx = max(0, event_idx + event_window[0])
        event_end_idx = min(len(returns), event_idx + event_window[1] + 1)
        event_returns = returns[event_start_idx:event_end_idx]

        # Abnormal Returns (AR)
        abnormal_returns = [r - mean_return for r in event_returns]

        # Cumulative Abnormal Return (CAR)
        car = sum(abnormal_returns)

        # AR на день события
        ar_event_day = abnormal_returns[abs(event_window[0])] if len(abnormal_returns) > abs(event_window[0]) else 0.0

        # Volume spike (отношение объема в день события к среднему)
        estimation_volumes = volumes[estimation_start:event_idx]
        avg_volume = mean(estimation_volumes) if estimation_volumes else 1.0
        event_volume = volumes[event_idx] if event_idx < len(volumes) else 0.0
        volume_spike = event_volume / avg_volume if avg_volume > 0 else 1.0

        return {
            "ar": ar_event_day,
            "car": car,
            "volume_spike": volume_spike,
            "estimation_mean": mean_return,
            "estimation_std": std_return,
            "event_window_returns": event_returns,
            "abnormal_returns": abnormal_returns,
            "event_date": event_date_str,
            "secid": secid
        }

    async def analyze_event_impact(
        self,
        event_id: str,
        secid: str,
        event_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Полный анализ влияния события на инструмент

        Returns:
            {
                'event_id': ...,
                'secid': ...,
                'ar': ...,
                'car': ...,
                'volume_spike': ...,
                'is_significant': bool,
                'impact_score': float
            }
        """
        result = await self.calculate_abnormal_return(secid, event_date)

        if not result:
            return None

        # Определяем значимость (AR > 2*std или volume_spike > 2)
        is_significant = (
            abs(result["ar"]) > 2 * result["estimation_std"] or
            result["volume_spike"] > 2.0
        )

        # Impact score (нормализованный)
        impact_score = min(abs(result["ar"]) / (result["estimation_std"] + 1e-6), 1.0)

        return {
            "event_id": event_id,
            "secid": secid,
            "ar": result["ar"],
            "car": result["car"],
            "volume_spike": result["volume_spike"],
            "is_significant": is_significant,
            "impact_score": impact_score,
            "estimation_mean": result["estimation_mean"],
            "estimation_std": result["estimation_std"]
        }

    async def calculate_market_confidence(
        self,
        secid: str,
        event_date: datetime
    ) -> float:
        """
        Рассчитать conf_market для CMNLN на основе Event Study

        Формула: conf_market = sigmoid(|AR| / σ) если significant, иначе 0

        Returns:
            conf_market: float [0, 1]
        """
        impact = await self.analyze_event_impact("", secid, event_date)

        if not impact:
            return 0.0

        if not impact["is_significant"]:
            return 0.0

        # Нормализуем через sigmoid
        z_score = abs(impact["ar"]) / (impact["estimation_std"] + 1e-6)

        # Sigmoid: 1 / (1 + e^(-z))
        import math
        conf_market = 1.0 / (1.0 + math.exp(-z_score + 2))  # Сдвиг для порога

        return min(conf_market, 1.0)
