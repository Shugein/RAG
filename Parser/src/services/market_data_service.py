#Parser.src/radar/services/market_data_service.py
"""
Сервис для получения рыночных данных из различных источников
Согласно Project Charter: MOEX (ALGOPACK), Yahoo Finance, Crypto
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import hashlib
import json

import httpx
import yfinance as yf
import pandas as pd
import numpy as np
from redis import asyncio as aioredis
import ccxt.async_support as ccxt

from Parser.src.core.config import settings

logger = logging.getLogger(__name__)


class MarketProvider(str, Enum):
    """Провайдеры рыночных данных"""
    MOEX = "moex"
    YAHOO = "yahoo"
    CRYPTO = "crypto"


class ExchangeInfo:
    """Информация о биржах и их расписании"""
    
    EXCHANGES = {
        "MOEX": {
            "timezone": "Europe/Moscow",
            "open_time": "10:00",
            "close_time": "18:50",
            "pre_market": "09:50",
            "post_market": "19:00",
            "trading_days": [0, 1, 2, 3, 4],  # Mon-Fri
            "provider": MarketProvider.MOEX
        },
        "NYSE": {
            "timezone": "America/New_York",
            "open_time": "09:30",
            "close_time": "16:00",
            "pre_market": "04:00",
            "post_market": "20:00",
            "trading_days": [0, 1, 2, 3, 4],
            "provider": MarketProvider.YAHOO
        },
        "NASDAQ": {
            "timezone": "America/New_York",
            "open_time": "09:30",
            "close_time": "16:00",
            "pre_market": "04:00",
            "post_market": "20:00",
            "trading_days": [0, 1, 2, 3, 4],
            "provider": MarketProvider.YAHOO
        },
        "BINANCE": {
            "timezone": "UTC",
            "open_time": "00:00",
            "close_time": "23:59",
            "trading_days": [0, 1, 2, 3, 4, 5, 6],  # 24/7
            "provider": MarketProvider.CRYPTO
        }
    }


class MarketDataService:
    """
    Унифицированный сервис для получения рыночных данных
    Поддерживает MOEX через ALGOPACK, Yahoo Finance для США, криптовалюты
    """
    
    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl  # TTL кеша в секундах
        self.redis: Optional[aioredis.Redis] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.crypto_exchange: Optional[ccxt.Exchange] = None
        
        # Кеш для инструментов
        self._instrument_cache = {}
        
        # Rate limiting
        self._last_request_time = {}
        self._rate_limits = {
            MarketProvider.MOEX: 0.1,  # 10 requests per second
            MarketProvider.YAHOO: 0.5,  # 2 requests per second
            MarketProvider.CRYPTO: 0.05  # 20 requests per second
        }
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def initialize(self):
        """Инициализация подключений"""
        
        # Redis для кеширования
        self.redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        
        # HTTP клиент для MOEX/ALGOPACK
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {settings.ALGOPACK_API_KEY}",
                "User-Agent": "RADAR-AI/1.0"
            },
            trust_env=False  # Ignore environment proxy settings
        )
        
        # Crypto exchange (Binance as default)
        self.crypto_exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })
        
        logger.info("MarketDataService initialized")
    
    async def close(self):
        """Закрытие подключений"""
        if self.redis:
            await self.redis.close()
        
        if self.http_client:
            await self.http_client.aclose()
        
        if self.crypto_exchange:
            await self.crypto_exchange.close()
    
    # ============================================================================
    # ОСНОВНЫЕ МЕТОДЫ
    # ============================================================================
    
    async def get_primary_instrument(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить основной инструмент компании
        
        Args:
            company_id: ID или тикер компании
            
        Returns:
            Информация об инструменте
        """
        
        # Проверяем кеш
        cache_key = f"instrument:{company_id}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached
        
        instrument = None
        
        # Пытаемся найти на MOEX
        if not instrument:
            instrument = await self._get_moex_instrument(company_id)
        
        # Пытаемся найти на Yahoo
        if not instrument:
            instrument = await self._get_yahoo_instrument(company_id)
        
        # Пытаемся найти в крипто
        if not instrument:
            instrument = await self._get_crypto_instrument(company_id)
        
        if instrument:
            await self._set_cached(cache_key, instrument)
        
        return instrument
    
    async def get_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1h"
    ) -> List[Dict[str, Any]]:
        """
        Получить OHLCV данные
        
        Args:
            symbol: Тикер инструмента
            start: Начальная дата
            end: Конечная дата
            interval: Интервал (1m, 5m, 15m, 1h, 1d)
            
        Returns:
            Список OHLCV баров
        """
        
        # Определяем провайдера по символу
        provider = await self._detect_provider(symbol)
        
        if provider == MarketProvider.MOEX:
            return await self._get_moex_ohlcv(symbol, start, end, interval)
        elif provider == MarketProvider.YAHOO:
            return await self._get_yahoo_ohlcv(symbol, start, end, interval)
        elif provider == MarketProvider.CRYPTO:
            return await self._get_crypto_ohlcv(symbol, start, end, interval)
        
        return []
    
    async def get_daily_prices(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Получить дневные цены для расчета корреляций"""
        return await self.get_ohlcv(ticker, start_date, end_date, "1d")
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Получить текущую цену инструмента"""
        
        cache_key = f"price:{symbol}"
        cached = await self._get_cached(cache_key, ttl=30)  # Кеш на 30 секунд
        if cached:
            return float(cached)
        
        provider = await self._detect_provider(symbol)
        price = None
        
        if provider == MarketProvider.MOEX:
            price = await self._get_moex_current_price(symbol)
        elif provider == MarketProvider.YAHOO:
            price = await self._get_yahoo_current_price(symbol)
        elif provider == MarketProvider.CRYPTO:
            price = await self._get_crypto_current_price(symbol)
        
        if price:
            await self._set_cached(cache_key, price, ttl=30)
        
        return price
    
    async def get_avg_volume(self, ticker: str, days: int = 30) -> float:
        """Получить среднедневной объем торгов"""
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        data = await self.get_daily_prices(ticker, start_date, end_date)
        
        if not data:
            return 0.0
        
        volumes = [d["volume"] for d in data if d.get("volume")]
        return np.mean(volumes) if volumes else 0.0
    
    async def get_sector_tickers(self, sector: str) -> List[str]:
        """Получить тикеры компаний из сектора"""
        
        cache_key = f"sector_tickers:{sector}"
        cached = await self._get_cached(cache_key, ttl=3600)  # Кеш на час
        if cached:
            return json.loads(cached)
        
        tickers = []
        
        # MOEX секторные индексы
        moex_sectors = {
            "oil_gas": "MOEXOG",
            "metals": "MOEXMM",
            "banks": "MOEXFN",
            "telecom": "MOEXTL",
            "consumer": "MOEXCN",
            "energy": "MOEXEU"
        }
        
        if sector in moex_sectors:
            tickers.extend(await self._get_moex_index_constituents(moex_sectors[sector]))
        
        # Yahoo Finance секторы (S&P 500)
        if sector == "technology":
            # Примеры тикеров технологического сектора
            tickers.extend(["AAPL", "MSFT", "GOOGL", "META", "NVDA"])
        
        if tickers:
            await self._set_cached(cache_key, json.dumps(tickers), ttl=3600)
        
        return tickers
    
    async def get_top_liquid_tickers(self, limit: int = 50) -> List[str]:
        """Получить топ ликвидных инструментов"""
        
        cache_key = f"top_liquid:{limit}"
        cached = await self._get_cached(cache_key, ttl=3600)
        if cached:
            return json.loads(cached)
        
        tickers = []
        
        # MOEX - индекс IMOEX (топ ликвидные)
        moex_tickers = await self._get_moex_index_constituents("IMOEX")
        tickers.extend(moex_tickers[:limit//2])
        
        # US - S&P 500 топ по капитализации
        us_top = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", 
                  "BRK-B", "V", "JNJ", "WMT", "JPM", "MA", "PG", "UNH"]
        tickers.extend(us_top[:limit//3])
        
        # Crypto топ по капитализации
        crypto_top = ["BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT", 
                      "SOL/USDT", "ADA/USDT", "DOGE/USDT"]
        tickers.extend(crypto_top[:limit//6])
        
        tickers = tickers[:limit]
        
        if tickers:
            await self._set_cached(cache_key, json.dumps(tickers), ttl=3600)
        
        return tickers
    
    # ============================================================================
    # MOEX/ALGOPACK МЕТОДЫ
    # ============================================================================
    
    async def _get_moex_instrument(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Получить инструмент с MOEX"""
        
        await self._rate_limit(MarketProvider.MOEX)
        
        try:
            response = await self.http_client.get(
                f"{settings.ALGOPACK_BASE_URL}/securities/{ticker}"
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "symbol": data.get("secid"),
                    "exchange": "MOEX",
                    "type": self._map_moex_type(data.get("sectype")),
                    "currency": data.get("currency", "RUB"),
                    "name": data.get("shortname"),
                    "isin": data.get("isin"),
                    "board": data.get("primary_boardid"),
                    "provider": MarketProvider.MOEX
                }
        except Exception as e:
            logger.error(f"Error fetching MOEX instrument {ticker}: {e}")
        
        return None
    
    async def _get_moex_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """Получить OHLCV с MOEX"""
        
        await self._rate_limit(MarketProvider.MOEX)
        
        # Мапинг интервалов для MOEX
        interval_map = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "1h": "60",
            "1d": "D",
            "1w": "W"
        }
        
        moex_interval = interval_map.get(interval, "60")
        
        try:
            response = await self.http_client.get(
                f"{settings.ALGOPACK_BASE_URL}/candles/{symbol}",
                params={
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "interval": moex_interval
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                return [
                    {
                        "timestamp": bar["datetime"],
                        "open": float(bar["open"]),
                        "high": float(bar["high"]),
                        "low": float(bar["low"]),
                        "close": float(bar["close"]),
                        "volume": float(bar["volume"])
                    }
                    for bar in data.get("candles", [])
                ]
        except Exception as e:
            logger.error(f"Error fetching MOEX OHLCV for {symbol}: {e}")
        
        return []
    
    async def _get_moex_current_price(self, symbol: str) -> Optional[float]:
        """Получить текущую цену с MOEX"""
        
        await self._rate_limit(MarketProvider.MOEX)
        
        try:
            response = await self.http_client.get(
                f"{settings.ALGOPACK_BASE_URL}/securities/{symbol}/quote"
            )
            
            if response.status_code == 200:
                data = response.json()
                return float(data.get("last", 0))
        except Exception as e:
            logger.error(f"Error fetching MOEX price for {symbol}: {e}")
        
        return None
    
    async def _get_moex_index_constituents(self, index: str) -> List[str]:
        """Получить состав индекса MOEX"""
        
        await self._rate_limit(MarketProvider.MOEX)
        
        try:
            response = await self.http_client.get(
                f"{settings.ALGOPACK_BASE_URL}/indices/{index}/securities"
            )
            
            if response.status_code == 200:
                data = response.json()
                return [s["secid"] for s in data.get("securities", [])]
        except Exception as e:
            logger.error(f"Error fetching MOEX index constituents for {index}: {e}")
        
        return []
    
    def _map_moex_type(self, sectype: str) -> str:
        """Маппинг типов инструментов MOEX"""
        type_map = {
            "shares": "equity",
            "bonds": "bond",
            "futures": "future",
            "options": "option",
            "dr": "adr"
        }
        return type_map.get(sectype, "equity")
    
    # ============================================================================
    # YAHOO FINANCE МЕТОДЫ
    # ============================================================================
    
    async def _get_yahoo_instrument(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Получить инструмент с Yahoo Finance"""
        
        await self._rate_limit(MarketProvider.YAHOO)
        
        try:
            # Yahoo Finance использует синхронный API, запускаем в executor
            loop = asyncio.get_event_loop()
            ticker_info = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(ticker).info
            )
            
            if ticker_info and ticker_info.get("symbol"):
                return {
                    "symbol": ticker_info["symbol"],
                    "exchange": ticker_info.get("exchange", "UNKNOWN"),
                    "type": self._map_yahoo_type(ticker_info.get("quoteType")),
                    "currency": ticker_info.get("currency", "USD"),
                    "name": ticker_info.get("shortName"),
                    "isin": ticker_info.get("isin"),
                    "provider": MarketProvider.YAHOO
                }
        except Exception as e:
            logger.debug(f"Yahoo instrument not found for {ticker}: {e}")
        
        return None
    
    async def _get_yahoo_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """Получить OHLCV с Yahoo Finance"""
        
        await self._rate_limit(MarketProvider.YAHOO)
        
        # Мапинг интервалов для Yahoo
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "1d": "1d",
            "1w": "1wk"
        }
        
        yahoo_interval = interval_map.get(interval, "1h")
        
        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: yf.download(
                    symbol,
                    start=start,
                    end=end,
                    interval=yahoo_interval,
                    progress=False
                )
            )
            
            if not df.empty:
                result = []
                for index, row in df.iterrows():
                    result.append({
                        "timestamp": index.isoformat(),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row["Volume"])
                    })
                return result
        except Exception as e:
            logger.error(f"Error fetching Yahoo OHLCV for {symbol}: {e}")
        
        return []
    
    async def _get_yahoo_current_price(self, symbol: str) -> Optional[float]:
        """Получить текущую цену с Yahoo Finance"""
        
        await self._rate_limit(MarketProvider.YAHOO)
        
        try:
            loop = asyncio.get_event_loop()
            ticker = await loop.run_in_executor(
                None,
                lambda: yf.Ticker(symbol)
            )
            
            history = await loop.run_in_executor(
                None,
                lambda: ticker.history(period="1d")
            )
            
            if not history.empty:
                return float(history["Close"].iloc[-1])
        except Exception as e:
            logger.error(f"Error fetching Yahoo price for {symbol}: {e}")
        
        return None
    
    def _map_yahoo_type(self, quote_type: str) -> str:
        """Маппинг типов инструментов Yahoo"""
        type_map = {
            "EQUITY": "equity",
            "ETF": "etf",
            "MUTUALFUND": "fund",
            "OPTION": "option",
            "FUTURE": "future",
            "CRYPTOCURRENCY": "token"
        }
        return type_map.get(quote_type, "equity")
    
    # ============================================================================
    # CRYPTO МЕТОДЫ
    # ============================================================================
    
    async def _get_crypto_instrument(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получить криптовалютный инструмент"""
        
        await self._rate_limit(MarketProvider.CRYPTO)
        
        try:
            # Преобразуем формат: BTC -> BTC/USDT
            if "/" not in symbol:
                symbol = f"{symbol}/USDT"
            
            markets = await self.crypto_exchange.load_markets()
            
            if symbol in markets:
                market = markets[symbol]
                return {
                    "symbol": symbol,
                    "exchange": "BINANCE",
                    "type": "token",
                    "currency": market["quote"],
                    "name": f"{market['base']}/{market['quote']}",
                    "provider": MarketProvider.CRYPTO
                }
        except Exception as e:
            logger.debug(f"Crypto instrument not found for {symbol}: {e}")
        
        return None
    
    async def _get_crypto_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str
    ) -> List[Dict[str, Any]]:
        """Получить OHLCV для криптовалюты"""
        
        await self._rate_limit(MarketProvider.CRYPTO)
        
        # Мапинг интервалов для Binance
        interval_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "1d": "1d",
            "1w": "1w"
        }
        
        ccxt_interval = interval_map.get(interval, "1h")
        
        try:
            # Преобразуем формат символа
            if "/" not in symbol:
                symbol = f"{symbol}/USDT"
            
            since = int(start.timestamp() * 1000)
            
            ohlcv = await self.crypto_exchange.fetch_ohlcv(
                symbol,
                timeframe=ccxt_interval,
                since=since,
                limit=500
            )
            
            result = []
            for candle in ohlcv:
                timestamp = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc)
                if timestamp > end:
                    break
                    
                result.append({
                    "timestamp": timestamp.isoformat(),
                    "open": float(candle[1]),
                    "high": float(candle[2]),
                    "low": float(candle[3]),
                    "close": float(candle[4]),
                    "volume": float(candle[5])
                })
            
            return result
        except Exception as e:
            logger.error(f"Error fetching crypto OHLCV for {symbol}: {e}")
        
        return []
    
    async def _get_crypto_current_price(self, symbol: str) -> Optional[float]:
        """Получить текущую цену криптовалюты"""
        
        await self._rate_limit(MarketProvider.CRYPTO)
        
        try:
            # Преобразуем формат символа
            if "/" not in symbol:
                symbol = f"{symbol}/USDT"
            
            ticker = await self.crypto_exchange.fetch_ticker(symbol)
            return float(ticker["last"]) if ticker else None
        except Exception as e:
            logger.error(f"Error fetching crypto price for {symbol}: {e}")
        
        return None
    
    # ============================================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================================================
    
    async def _detect_provider(self, symbol: str) -> MarketProvider:
        """Определить провайдера для символа"""
        
        # Криптовалюты
        if "/" in symbol or symbol in ["BTC", "ETH", "BNB", "XRP", "SOL"]:
            return MarketProvider.CRYPTO
        
        # Российские тикеры (обычно 4 буквы)
        if len(symbol) == 4 and symbol.isupper():
            return MarketProvider.MOEX
        
        # По умолчанию - Yahoo для остальных
        return MarketProvider.YAHOO
    
    async def _rate_limit(self, provider: MarketProvider):
        """Rate limiting для провайдеров"""
        
        current_time = asyncio.get_event_loop().time()
        
        if provider in self._last_request_time:
            elapsed = current_time - self._last_request_time[provider]
            min_interval = self._rate_limits[provider]
            
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
        
        self._last_request_time[provider] = asyncio.get_event_loop().time()
    
    async def _get_cached(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Получить данные из кеша"""
        
        if not self.redis:
            return None
        
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.debug(f"Cache get error for {key}: {e}")
        
        return None
    
    async def _set_cached(self, key: str, value: Any, ttl: Optional[int] = None):
        """Сохранить данные в кеш"""
        
        if not self.redis:
            return
        
        ttl = ttl or self.cache_ttl
        
        try:
            await self.redis.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.debug(f"Cache set error for {key}: {e}")


# ============================================================================
# Пример использования
# ============================================================================

async def example_usage():
    """Пример использования MarketDataService"""
    
    async with MarketDataService() as market_data:
        
        # Получить инструмент
        instrument = await market_data.get_primary_instrument("SBER")
        print(f"Instrument: {instrument}")
        
        # Получить текущую цену
        price = await market_data.get_current_price("SBER")
        print(f"Current price: {price}")
        
        # Получить исторические данные
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        ohlcv = await market_data.get_ohlcv(
            "SBER",
            start_date,
            end_date,
            interval="1h"
        )
        print(f"OHLCV bars: {len(ohlcv)}")
        
        # Получить среднедневной объем
        avg_volume = await market_data.get_avg_volume("SBER", days=30)
        print(f"Average volume (30d): {avg_volume:,.0f}")
        
        # Получить тикеры сектора
        oil_gas_tickers = await market_data.get_sector_tickers("oil_gas")
        print(f"Oil & Gas tickers: {oil_gas_tickers[:5]}")
        
        # Получить топ ликвидных инструментов
        top_liquid = await market_data.get_top_liquid_tickers(20)
        print(f"Top liquid: {top_liquid[:10]}")
        
        # Пример с US акцией
        apple = await market_data.get_primary_instrument("AAPL")
        print(f"Apple: {apple}")
        
        apple_price = await market_data.get_current_price("AAPL")
        print(f"Apple price: ${apple_price}")
        
        # Пример с криптовалютой
        btc = await market_data.get_primary_instrument("BTC")
        print(f"Bitcoin: {btc}")
        
        btc_price = await market_data.get_current_price("BTC/USDT")
        print(f"BTC price: ${btc_price:,.0f}")


if __name__ == "__main__":
    # Для тестирования
    asyncio.run(example_usage())