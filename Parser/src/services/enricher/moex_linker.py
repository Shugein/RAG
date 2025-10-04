# src/radar/services/moex_linker.py
"""
Сервис связывания текстовых упоминаний компаний с инструментами MOEX
Использует ALGOPACK API, fuzzy matching и алиасы
"""

import re
import logging
import asyncio
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import hashlib
import json

import httpx
from transliterate import translit
from fuzzywuzzy import fuzz, process
import pymorphy3
from redis import asyncio as aioredis

from src.core.config import settings
from src.graph_models import Company, Instrument, GraphService
from src.services.enricher.company_aliases import get_alias_manager
from src.services.enricher.moex_auto_search import MOEXAutoSearch

logger = logging.getLogger(__name__)


@dataclass
class CompanyMatch:
    """Результат сопоставления компании"""
    text: str  # Оригинальный текст
    normalized: str  # Нормализованное название
    ticker: Optional[str] = None
    isin: Optional[str] = None
    board: Optional[str] = None
    company_name: str = ""
    short_name: str = ""
    confidence: float = 0.0
    match_method: str = "unknown"  # exact, alias, fuzzy, sector
    is_traded: bool = False
    market_cap: Optional[float] = None
    sector: Optional[str] = None


@dataclass 
class CompanyAlias:
    """Алиас компании"""
    alias: str
    normalized: str
    ticker: str
    confidence: float = 1.0
    source: str = "manual"  # manual, auto, verified


class MOEXLinker:
    """
    Сервис для связывания упоминаний компаний с инструментами MOEX
    Поддерживает различные варианты написания, транслитерацию, аббревиатуры
    Использует автоматический поиск через MOEX ISS API
    """
    
    # Список общих слов, которые нужно игнорировать при поиске
    STOP_WORDS = {
        "компания", "группа", "холдинг", "корпорация", "банк",
        "company", "group", "holding", "corporation", "bank",
        "пао", "оао", "ооо", "ао", "зао", "нко", "нпф",
        "jsc", "pjsc", "llc", "ltd", "inc", "corp", "plc"
    }
    
    def __init__(self, enable_auto_learning: bool = True):
        """
        Args:
            enable_auto_learning: Включить автоматическое обучение через MOEX ISS API
        """
        self.http_client: Optional[httpx.AsyncClient] = None
        self.redis: Optional[aioredis.Redis] = None
        self.morph = pymorphy3.MorphAnalyzer(lang='ru')
        self.graph: Optional[GraphService] = None
        
        # Менеджер алиасов (общий для всех модулей)
        self.alias_manager = get_alias_manager()
        
        # Автоматический поиск через MOEX ISS API
        self.auto_search: Optional[MOEXAutoSearch] = None
        self.enable_auto_learning = enable_auto_learning
        
        # Кеш для результатов
        self._ticker_cache: Dict[str, CompanyMatch] = {}
        self._alias_cache: Dict[str, CompanyAlias] = {}
        self._moex_securities: Dict[str, Dict] = {}
        
        # Счетчики для метрик
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "not_found": 0
        }
    
    async def initialize(self):
        """Инициализация сервиса"""
        
        # HTTP клиент для ALGOPACK
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {settings.ALGOPACK_API_KEY}",
                "User-Agent": "RADAR-AI-MOEXLinker/1.0"
            }
        )
        
        # Redis для кеширования
        self.redis = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        
        # Подключение к графу
        self.graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Инициализация автопоиска через MOEX ISS API
        if self.enable_auto_learning:
            self.auto_search = MOEXAutoSearch(use_cache=True)
            await self.auto_search.initialize()
            logger.info("MOEX Auto-search enabled")
        
        # Загружаем список всех инструментов MOEX
        await self._load_moex_securities()
        
        logger.info("MOEXLinker initialized")
    
    async def close(self):
        """Закрытие соединений"""
        if self.http_client:
            await self.http_client.aclose()
        if self.redis:
            await self.redis.close()
        if self.graph:
            await self.graph.close()
        if self.auto_search:
            await self.auto_search.close()
    
    async def link_companies(
        self,
        text: str,
        entities: Optional[List[Dict]] = None
    ) -> List[CompanyMatch]:
        """
        Найти и связать упоминания компаний в тексте с инструментами MOEX
        
        Args:
            text: Текст для анализа
            entities: Опциональный список уже извлеченных NER сущностей
            
        Returns:
            Список найденных компаний с тикерами
        """
        
        self.stats["total_requests"] += 1
        
        results = []
        processed = set()  # Для избежания дубликатов
        
        # 1. Ищем прямые упоминания тикеров
        ticker_matches = await self._find_tickers_in_text(text)
        for match in ticker_matches:
            if match.ticker not in processed:
                results.append(match)
                processed.add(match.ticker)
        
        # 2. Обрабатываем NER сущности типа ORG
        if entities:
            for entity in entities:
                if entity.get("type") == "ORG":
                    org_text = entity.get("text", "")
                    if org_text:
                        match = await self.link_organization(org_text)
                        if match and match.ticker and match.ticker not in processed:
                            results.append(match)
                            processed.add(match.ticker)
        
        # 3. Ищем известные алиасы в тексте
        alias_matches = await self._find_aliases_in_text(text)
        for match in alias_matches:
            if match.ticker not in processed:
                results.append(match)
                processed.add(match.ticker)
        
        # Сортируем по confidence
        results.sort(key=lambda x: x.confidence, reverse=True)
        
        return results
    
    async def link_organization(self, org_name: str) -> Optional[CompanyMatch]:
        """
        Связать название организации с инструментом MOEX
        
        Args:
            org_name: Название организации
            
        Returns:
            CompanyMatch или None если не найдено
        """
        
        # Нормализуем название
        normalized = self._normalize_company_name(org_name)
        
        # Проверяем кеш
        cache_key = f"moex_link:{normalized}"
        if normalized in self._ticker_cache:
            self.stats["cache_hits"] += 1
            return self._ticker_cache[normalized]
        
        # Проверяем Redis кеш
        cached = await self._get_redis_cached(cache_key)
        if cached:
            self.stats["cache_hits"] += 1
            match = CompanyMatch(**json.loads(cached))
            self._ticker_cache[normalized] = match
            return match
        
        # 1. Проверяем известные алиасы
        match = await self._check_known_aliases(normalized)
        if match:
            self.stats["exact_matches"] += 1
            await self._cache_result(cache_key, match)
            return match
        
        # 2. Ищем в базе алиасов (Neo4j)
        match = await self._find_in_graph_aliases(normalized)
        if match:
            self.stats["exact_matches"] += 1
            await self._cache_result(cache_key, match)
            return match
        
        # 3. Поиск через ALGOPACK API
        match = await self._search_algopack(normalized, org_name)
        if match:
            self.stats["exact_matches"] += 1
            await self._cache_result(cache_key, match)
            return match
        
        # 4. Fuzzy matching по всем известным инструментам
        match = await self._fuzzy_match_securities(normalized, org_name)
        if match:
            self.stats["fuzzy_matches"] += 1
            await self._cache_result(cache_key, match)
            return match
        
        self.stats["not_found"] += 1
        return None
    
    async def _load_moex_securities(self):
        """Загрузить список всех инструментов MOEX"""
        
        cache_key = "moex_securities:all"
        
        # Проверяем Redis кеш
        cached = await self._get_redis_cached(cache_key, ttl=86400)  # 24 часа
        if cached:
            self._moex_securities = json.loads(cached)
            logger.info(f"Loaded {len(self._moex_securities)} securities from cache")
            return
        
        try:
            # Загружаем все акции
            response = await self.http_client.get(
                f"{settings.ALGOPACK_BASE_URL}/securities",
                params={
                    "market": "shares",
                    "is_traded": "true"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                for security in data.get("securities", []):
                    ticker = security.get("secid")
                    if ticker:
                        self._moex_securities[ticker] = {
                            "ticker": ticker,
                            "name": security.get("shortname", ""),
                            "full_name": security.get("name", ""),
                            "isin": security.get("isin"),
                            "board": security.get("primary_boardid"),
                            "type": security.get("sectype", "shares"),
                            "is_traded": security.get("is_traded", False)
                        }
                
                # Кешируем на 24 часа
                await self._set_redis_cached(
                    cache_key,
                    json.dumps(self._moex_securities),
                    ttl=86400
                )
                
                logger.info(f"Loaded {len(self._moex_securities)} MOEX securities")
                
        except Exception as e:
            logger.error(f"Error loading MOEX securities: {e}")
    
    def _normalize_company_name(self, name: str) -> str:
        """Нормализация названия компании"""
        
        # Приводим к нижнему регистру
        name = name.lower().strip()
        
        # Удаляем кавычки и спецсимволы
        name = re.sub(r'[«»"\'`„"]', '', name)
        
        # Заменяем дефисы и слеши на пробелы
        name = re.sub(r'[-/]', ' ', name)
        
        # Удаляем точки после аббревиатур
        name = re.sub(r'\.(?=\s|$)', '', name)
        
        # Удаляем стоп-слова
        words = name.split()
        words = [w for w in words if w not in self.STOP_WORDS]
        name = ' '.join(words)
        
        # Удаляем множественные пробелы
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    async def _find_tickers_in_text(self, text: str) -> List[CompanyMatch]:
        """Найти прямые упоминания тикеров в тексте"""
        
        results = []
        
        # Паттерн для тикеров MOEX (обычно 4 буквы)
        ticker_pattern = re.compile(r'\b([A-Z]{4}[A-Z0-9]*)\b')
        
        for match in ticker_pattern.finditer(text.upper()):
            ticker = match.group(1)
            
            # Проверяем, является ли это реальным тикером
            if ticker in self._moex_securities:
                security = self._moex_securities[ticker]
                
                results.append(CompanyMatch(
                    text=ticker,
                    normalized=ticker,
                    ticker=ticker,
                    isin=security.get("isin"),
                    board=security.get("board"),
                    company_name=security.get("full_name", ""),
                    short_name=security.get("name", ""),
                    confidence=1.0,
                    match_method="ticker",
                    is_traded=security.get("is_traded", False)
                ))
        
        return results
    
    async def _find_aliases_in_text(self, text: str) -> List[CompanyMatch]:
        """Найти известные алиасы компаний в тексте"""
        
        results = []
        text_lower = text.lower()
        
        # Получаем все известные алиасы (ручные + выученные)
        all_aliases = self.alias_manager.get_all_aliases()
        
        # Проверяем каждый известный алиас
        for alias, ticker in all_aliases.items():
            # Ищем алиас как отдельное слово или фразу
            pattern = r'\b' + re.escape(alias) + r'\b'
            
            if re.search(pattern, text_lower):
                # Получаем информацию о компании
                if ticker in self._moex_securities:
                    security = self._moex_securities[ticker]
                    
                    results.append(CompanyMatch(
                        text=alias,
                        normalized=alias,
                        ticker=ticker,
                        isin=security.get("isin"),
                        board=security.get("board"),
                        company_name=security.get("full_name", ""),
                        short_name=security.get("name", ""),
                        confidence=0.95,
                        match_method="alias",
                        is_traded=security.get("is_traded", False)
                    ))
        
        return results
    
    async def _check_known_aliases(self, normalized_name: str) -> Optional[CompanyMatch]:
        """Проверить известные алиасы"""
        
        # Проверяем через менеджер алиасов
        ticker = self.alias_manager.get_ticker(normalized_name)
        
        if ticker and ticker in self._moex_securities:
            security = self._moex_securities[ticker]
            
            return CompanyMatch(
                text=normalized_name,
                normalized=normalized_name,
                ticker=ticker,
                isin=security.get("isin"),
                board=security.get("board"),
                company_name=security.get("full_name", ""),
                short_name=security.get("name", ""),
                confidence=0.95,
                match_method="known_alias",
                is_traded=security.get("is_traded", False)
            )
        
        # Если не нашли в алиасах, пробуем автопоиск через MOEX ISS API
        if self.auto_search and self.enable_auto_learning:
            try:
                auto_match = await self.auto_search.auto_learn_from_ner(
                    normalized_name,
                    save_alias=True
                )
                
                if auto_match:
                    # Обновляем кеш securities если нужно
                    if auto_match.secid not in self._moex_securities:
                        self._moex_securities[auto_match.secid] = {
                            "ticker": auto_match.secid,
                            "name": auto_match.shortname,
                            "full_name": auto_match.name,
                            "isin": auto_match.isin,
                            "board": auto_match.primary_boardid,
                            "type": auto_match.type,
                            "is_traded": auto_match.is_traded
                        }
                    
                    return CompanyMatch(
                        text=normalized_name,
                        normalized=normalized_name,
                        ticker=auto_match.secid,
                        isin=auto_match.isin,
                        board=auto_match.primary_boardid,
                        company_name=auto_match.name,
                        short_name=auto_match.shortname,
                        confidence=0.85,  # Чуть меньше, т.к. автоматическое
                        match_method="auto_learned",
                        is_traded=auto_match.is_traded
                    )
            except Exception as e:
                logger.debug(f"Auto-search failed for {normalized_name}: {e}")
        
        return None
    
    async def _find_in_graph_aliases(self, normalized_name: str) -> Optional[CompanyMatch]:
        """Поиск в графовой БД по алиасам"""
        
        # Запрос к Neo4j для поиска алиасов
        # TODO: Implement when graph aliases are populated
        
        return None
    
    async def _search_algopack(self, normalized_name: str, original_name: str) -> Optional[CompanyMatch]:
        """Поиск через ALGOPACK API"""
        
        try:
            # Поиск по названию
            response = await self.http_client.get(
                f"{settings.ALGOPACK_BASE_URL}/securities/search",
                params={
                    "query": original_name,
                    "limit": 10
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("securities", [])
                
                if results:
                    # Ищем лучшее совпадение
                    best_match = None
                    best_score = 0.0
                    
                    for security in results:
                        # Нормализуем название из результата
                        result_name = self._normalize_company_name(
                            security.get("shortname", "")
                        )
                        
                        # Вычисляем схожесть
                        score = self._calculate_similarity(normalized_name, result_name)
                        
                        # Бонус за торгуемость
                        if security.get("is_traded"):
                            score *= 1.2
                        
                        # Бонус за основную площадку
                        if security.get("primary_boardid") in ["TQBR", "TQTF"]:
                            score *= 1.1
                        
                        if score > best_score and score > 0.7:
                            best_score = score
                            best_match = security
                    
                    if best_match:
                        return CompanyMatch(
                            text=original_name,
                            normalized=normalized_name,
                            ticker=best_match.get("secid"),
                            isin=best_match.get("isin"),
                            board=best_match.get("primary_boardid"),
                            company_name=best_match.get("name", ""),
                            short_name=best_match.get("shortname", ""),
                            confidence=min(best_score, 1.0),
                            match_method="algopack_search",
                            is_traded=best_match.get("is_traded", False)
                        )
        
        except Exception as e:
            logger.error(f"Error searching ALGOPACK for {original_name}: {e}")
        
        return None
    
    async def _fuzzy_match_securities(self, normalized_name: str, original_name: str) -> Optional[CompanyMatch]:
        """Fuzzy matching по всем известным инструментам"""
        
        if not self._moex_securities:
            return None
        
        # Подготавливаем список для fuzzy matching
        choices = {}
        
        for ticker, security in self._moex_securities.items():
            # Нормализуем названия для сравнения
            short_norm = self._normalize_company_name(security.get("name", ""))
            full_norm = self._normalize_company_name(security.get("full_name", ""))
            
            if short_norm:
                choices[short_norm] = (ticker, security)
            if full_norm and full_norm != short_norm:
                choices[full_norm] = (ticker, security)
        
        # Используем fuzzywuzzy для поиска
        if choices:
            # Ищем лучшие совпадения
            matches = process.extract(
                normalized_name,
                choices.keys(),
                scorer=fuzz.token_sort_ratio,
                limit=5
            )
            
            # Фильтруем по минимальному порогу
            for match_text, score in matches:
                if score >= 80:  # Порог схожести
                    ticker, security = choices[match_text]
                    
                    # Дополнительная проверка через SequenceMatcher
                    final_score = self._calculate_similarity(normalized_name, match_text)
                    
                    if final_score > 0.7:
                        return CompanyMatch(
                            text=original_name,
                            normalized=normalized_name,
                            ticker=ticker,
                            isin=security.get("isin"),
                            board=security.get("board"),
                            company_name=security.get("full_name", ""),
                            short_name=security.get("name", ""),
                            confidence=final_score * 0.9,  # Снижаем confidence для fuzzy
                            match_method="fuzzy",
                            is_traded=security.get("is_traded", False)
                        )
        
        return None
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Вычислить схожесть двух строк"""
        
        # Базовая схожесть через SequenceMatcher
        base_similarity = SequenceMatcher(None, str1, str2).ratio()
        
        # Token sort ratio для учета перестановки слов
        token_similarity = fuzz.token_sort_ratio(str1, str2) / 100.0
        
        # Partial ratio для частичных совпадений
        partial_similarity = fuzz.partial_ratio(str1, str2) / 100.0
        
        # Взвешенное среднее
        return (base_similarity * 0.4 + token_similarity * 0.4 + partial_similarity * 0.2)
    
    async def _cache_result(self, key: str, match: CompanyMatch):
        """Кешировать результат"""
        
        # Локальный кеш
        self._ticker_cache[match.normalized] = match
        
        # Redis кеш
        await self._set_redis_cached(
            key,
            json.dumps(match.__dict__, default=str),
            ttl=3600  # 1 час
        )
    
    async def _get_redis_cached(self, key: str, ttl: Optional[int] = None) -> Optional[str]:
        """Получить из Redis кеша"""
        
        if not self.redis:
            return None
        
        try:
            return await self.redis.get(key)
        except Exception as e:
            logger.debug(f"Redis get error for {key}: {e}")
            return None
    
    async def _set_redis_cached(self, key: str, value: str, ttl: int = 3600):
        """Сохранить в Redis кеш"""
        
        if not self.redis:
            return
        
        try:
            await self.redis.setex(key, ttl, value)
        except Exception as e:
            logger.debug(f"Redis set error for {key}: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику работы"""
        return self.stats.copy()


# ============================================================================
# Пример использования
# ============================================================================

async def example_usage():
    """Пример использования MOEXLinker"""
    
    linker = MOEXLinker()
    await linker.initialize()
    
    try:
        # Пример текста новости
        text = """
        Сбербанк отчитался о рекордной прибыли. 
        Газпром увеличил добычу на 15%. 
        Акции Яндекса выросли после новости о партнерстве.
        MOEX индекс достиг исторического максимума.
        Норникель планирует выплатить дивиденды.
        X5 Retail Group открыла новые магазины Пятерочка.
        """
        
        # Поиск компаний в тексте
        companies = await linker.link_companies(text)
        
        print("Найденные компании:")
        for company in companies:
            print(f"  {company.text} -> {company.ticker} "
                  f"({company.short_name}) "
                  f"[confidence: {company.confidence:.2f}, "
                  f"method: {company.match_method}]")
        
        # Тест отдельных названий
        test_names = [
            "Сбербанк России",
            "Газпром нефть",
            "Яндекс НВ",
            "Норильский никель",
            "X5 Retail",
            "Московская биржа",
            "ПАО Лукойл",
            "Группа ПИК",
            "ВТБ Банк"
        ]
        
        print("\nТест отдельных названий:")
        for name in test_names:
            match = await linker.link_organization(name)
            if match:
                print(f"  {name} -> {match.ticker} ({match.short_name}) "
                      f"[{match.confidence:.2f}]")
            else:
                print(f"  {name} -> НЕ НАЙДЕНО")
        
        # Статистика
        print(f"\nСтатистика:")
        stats = linker.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
            
    finally:
        await linker.close()


# ============================================================================
# Дополнительные утилиты
# ============================================================================

class MOEXSectorMapper:
    """Маппинг компаний по секторам MOEX"""
    
    SECTOR_MAPPING = {
        "oil_gas": [
            "GAZP", "ROSN", "LKOH", "NVTK", "SNGS", "TATN", "TRNFP",
            "GAZPN", "SNGSP", "TATNP"
        ],
        "metals": [
            "GMKN", "NLMK", "CHMF", "MAGN", "PLZL", "ALRS", "RUAL",
            "POGR", "VSMO", "POLY"
        ],
        "banks": [
            "SBER", "VTBR", "CBOM", "BSPB", "QIWI", "TCSG", "SBERP"
        ],
        "telecom": [
            "MTSS", "MFON", "VEON-RX", "RTKM", "RTKMP"
        ],
        "retail": [
            "MGNT", "FIVE", "DSKY", "LENT", "FIXP", "OZON", "MVID"
        ],
        "energy": [
            "HYDR", "IRAO", "FEES", "UPRO", "TGKA", "TGKB", "OGKB",
            "MOSN", "LSNG", "LSNGP"
        ],
        "transport": [
            "AFLT", "NMTP", "FESH", "GLTR", "AFKS"
        ],
        "realestate": [
            "PIKK", "LSRG", "SMLT", "ETLN", "INGRAD"
        ],
        "it": [
            "YNDX", "VKCO", "POSI", "HHRU", "OZON", "CIAN", "TCSG"
        ],
        "chemistry": [
            "PHOR", "KAZT", "KAZTP", "NKNC", "NKNCP", "AKRN"
        ],
        "consumer": [
            "ABRD", "AQUA", "BELU", "GCHE", "SVAV", "MDMG"
        ],
        "machinery": [
            "KMAZ", "SGZH", "UWGN", "KZOS", "TRMK"
        ],
        "agriculture": [
            "AGRO", "RSGR", "MRSB"
        ]
    }
    
    @classmethod
    def get_sector(cls, ticker: str) -> Optional[str]:
        """Получить сектор по тикеру"""
        for sector, tickers in cls.SECTOR_MAPPING.items():
            if ticker in tickers:
                return sector
        return None
    
    @classmethod
    def get_sector_tickers(cls, sector: str) -> List[str]:
        """Получить тикеры сектора"""
        return cls.SECTOR_MAPPING.get(sector, [])


class CompanyDataEnricher:
    """Обогащение данных о компаниях дополнительной информацией"""
    
    def __init__(self, market_data_service):
        self.market_data = market_data_service
        
    async def enrich_company(self, company_match: CompanyMatch) -> CompanyMatch:
        """Обогатить данные о компании"""
        
        if not company_match.ticker:
            return company_match
        
        try:
            # Получаем текущие рыночные данные
            current_price = await self.market_data.get_current_price(company_match.ticker)
            
            # Получаем дополнительную информацию через ALGOPACK
            instrument = await self.market_data.get_primary_instrument(company_match.ticker)
            
            if instrument:
                # Обновляем данные
                company_match.market_cap = self._calculate_market_cap(
                    current_price,
                    instrument.get("shares_outstanding")
                )
                
                # Определяем сектор
                company_match.sector = MOEXSectorMapper.get_sector(company_match.ticker)
                
                # Проверяем торгуемость
                company_match.is_traded = instrument.get("is_traded", False)
                
        except Exception as e:
            logger.error(f"Error enriching company {company_match.ticker}: {e}")
        
        return company_match
    
    def _calculate_market_cap(self, price: Optional[float], shares: Optional[int]) -> Optional[float]:
        """Рассчитать рыночную капитализацию"""
        if price and shares:
            return price * shares
        return None


class CompanyNewsLinker:
    """Связывание новостей с компаниями в графовой БД"""
    
    def __init__(self, graph_service: GraphService, moex_linker: MOEXLinker):
        self.graph = graph_service
        self.linker = moex_linker
        
    async def process_news(self, news_id: str, text: str, entities: List[Dict]) -> List[str]:
        """
        Обработать новость и создать связи с компаниями
        
        Returns:
            Список ID компаний, с которыми создана связь
        """
        
        # Находим компании в тексте
        companies = await self.linker.link_companies(text, entities)
        
        linked_company_ids = []
        
        for company_match in companies:
            if company_match.ticker and company_match.confidence > 0.5:
                # Создаем/обновляем компанию в графе
                company_id = await self._upsert_company(company_match)
                
                # Создаем связь новости с компанией
                await self._link_news_to_company(news_id, company_id, company_match)
                
                linked_company_ids.append(company_id)
        
        logger.info(f"Linked news {news_id} to {len(linked_company_ids)} companies")
        
        return linked_company_ids
    
    async def _upsert_company(self, company_match: CompanyMatch) -> str:
        """Создать или обновить компанию в графе"""
        
        company_id = f"moex:{company_match.ticker}"
        
        query = """
        MERGE (c:Company {id: $company_id})
        SET c.ticker = $ticker,
            c.name = $name,
            c.short_name = $short_name,
            c.isin = $isin,
            c.moex_board = $board,
            c.sector = $sector,
            c.country_code = 'RU',
            c.updated_at = datetime()
        RETURN c.id as company_id
        """
        
        async with self.graph.driver.session() as session:
            result = await session.run(
                query,
                company_id=company_id,
                ticker=company_match.ticker,
                name=company_match.company_name,
                short_name=company_match.short_name,
                isin=company_match.isin,
                board=company_match.board,
                sector=company_match.sector
            )
            
            record = await result.single()
            return record["company_id"]
    
    async def _link_news_to_company(
        self,
        news_id: str,
        company_id: str,
        company_match: CompanyMatch
    ):
        """Создать связь между новостью и компанией"""
        
        query = """
        MATCH (n:News {id: $news_id})
        MATCH (c:Company {id: $company_id})
        MERGE (n)-[r:ABOUT]->(c)
        SET r.confidence = $confidence,
            r.match_method = $match_method,
            r.extracted_text = $text,
            r.created_at = datetime()
        """
        
        async with self.graph.driver.session() as session:
            await session.run(
                query,
                news_id=news_id,
                company_id=company_id,
                confidence=company_match.confidence,
                match_method=company_match.match_method,
                text=company_match.text
            )


# ============================================================================
# Интеграция с основным pipeline
# ============================================================================

class MOEXEnrichmentProcessor:
    """Процессор для обогащения новостей данными MOEX"""
    
    def __init__(self):
        self.linker = MOEXLinker()
        self.graph = None
        self.market_data = None
        self.enricher = None
        self.news_linker = None
        
    async def initialize(self):
        """Инициализация всех компонентов"""
        
        # Инициализируем linker
        await self.linker.initialize()
        
        # Инициализируем граф
        from src.radar.core.graph_models import GraphService
        self.graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Инициализируем market data service
        from src.radar.services.market_data_service import MarketDataService
        self.market_data = MarketDataService()
        await self.market_data.initialize()
        
        # Создаем вспомогательные сервисы
        self.enricher = CompanyDataEnricher(self.market_data)
        self.news_linker = CompanyNewsLinker(self.graph, self.linker)
        
        logger.info("MOEXEnrichmentProcessor initialized")
    
    async def process(self, news_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработать событие новости и обогатить данными MOEX
        
        Args:
            news_event: Событие из RabbitMQ (news.raw или news.norm)
            
        Returns:
            Обогащенное событие
        """
        
        news_id = news_event.get("id")
        text = news_event.get("text", "")
        title = news_event.get("title", "")
        entities = news_event.get("entities", [])
        
        # Объединяем заголовок и текст для анализа
        full_text = f"{title} {text}"
        
        # Находим компании
        companies = await self.linker.link_companies(full_text, entities)
        
        # Обогащаем данные о компаниях
        enriched_companies = []
        for company in companies:
            if company.confidence > 0.5:
                # Обогащаем дополнительными данными
                enriched = await self.enricher.enrich_company(company)
                
                enriched_companies.append({
                    "id": f"moex:{enriched.ticker}",
                    "ticker": enriched.ticker,
                    "name": enriched.short_name,
                    "full_name": enriched.company_name,
                    "isin": enriched.isin,
                    "board": enriched.board,
                    "confidence": enriched.confidence,
                    "match_method": enriched.match_method,
                    "is_traded": enriched.is_traded,
                    "sector": enriched.sector,
                    "market_cap": enriched.market_cap,
                    "instrument_type": "equity"
                })
        
        # Связываем в графе
        if news_id:
            linked_company_ids = await self.news_linker.process_news(
                news_id,
                full_text,
                entities
            )
            
            # Добавляем ID в результат
            for i, company in enumerate(enriched_companies):
                if i < len(linked_company_ids):
                    company["graph_id"] = linked_company_ids[i]
        
        # Обновляем событие
        news_event["extracted_companies"] = enriched_companies
        news_event["has_moex_companies"] = len(enriched_companies) > 0
        news_event["moex_enriched_at"] = datetime.utcnow().isoformat()
        
        # Добавляем статистику
        news_event["moex_stats"] = {
            "companies_found": len(enriched_companies),
            "traded_companies": sum(1 for c in enriched_companies if c["is_traded"]),
            "linker_stats": self.linker.get_stats()
        }
        
        return news_event
    
    async def close(self):
        """Закрытие всех соединений"""
        if self.linker:
            await self.linker.close()
        if self.graph:
            await self.graph.close()
        if self.market_data:
            await self.market_data.close()


if __name__ == "__main__":
    # Для тестирования
    asyncio.run(example_usage())