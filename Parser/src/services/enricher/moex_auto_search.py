# src/services/enricher/moex_auto_search.py
"""
Автоматический поиск инструментов на Московской бирже через ISS API
https://iss.moex.com/iss/reference/
"""

import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import httpx

from src.services.enricher.company_aliases import get_alias_manager

logger = logging.getLogger(__name__)


@dataclass
class MOEXSecurityInfo:
    """Информация об инструменте MOEX"""
    secid: str  # Тикер
    shortname: str  # Короткое название
    name: str  # Полное название
    isin: Optional[str] = None  # ISIN код
    regnumber: Optional[str] = None  # Регистрационный номер
    is_traded: bool = False  # Торгуется ли сейчас
    market: Optional[str] = None  # Рынок (shares, bonds, etc)
    engine: Optional[str] = None  # Торговая система
    type: Optional[str] = None  # Тип инструмента
    primary_boardid: Optional[str] = None  # Основной режим торгов


class MOEXAutoSearch:
    """
    Автоматический поиск и связывание компаний с инструментами MOEX
    Использует бесплатное ISS API Московской биржи
    """
    
    MOEX_ISS_BASE_URL = "https://iss.moex.com/iss"
    
    def __init__(self, use_cache: bool = True):
        """
        Инициализация автопоиска
        
        Args:
            use_cache: Использовать ли кеширование результатов
        """
        self.http_client: Optional[httpx.AsyncClient] = None
        self.use_cache = use_cache
        self._search_cache: Dict[str, List[MOEXSecurityInfo]] = {}
        self.alias_manager = get_alias_manager()
    
    async def initialize(self):
        """Инициализация HTTP клиента"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": "RADAR-AI-MOEXAutoSearch/1.0"
                }
            )
            logger.info("MOEXAutoSearch initialized")
    
    async def close(self):
        """Закрыть HTTP клиент"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
    
    async def search_by_query(self, query: str, limit: int = 10) -> List[MOEXSecurityInfo]:
        """
        Поиск инструментов по запросу через MOEX ISS API
        
        Args:
            query: Поисковый запрос (название компании, тикер и т.д.)
            limit: Максимальное количество результатов
            
        Returns:
            Список найденных инструментов
        """
        if not self.http_client:
            await self.initialize()
        
        # Проверяем кеш
        cache_key = f"{query.lower()}:{limit}"
        if self.use_cache and cache_key in self._search_cache:
            logger.debug(f"Cache hit for query: {query}")
            return self._search_cache[cache_key]
        
        try:
            # Запрос к MOEX ISS API
            # Документация: https://iss.moex.com/iss/reference/5
            url = f"{self.MOEX_ISS_BASE_URL}/securities.json"
            params = {
                "q": query,
                "limit": limit,
                "iss.meta": "off",  # Отключаем метаданные для скорости
                "iss.only": "securities"  # Только секции securities
            }
            
            response = await self.http_client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                results = self._parse_iss_response(data)
                
                # Кешируем результаты
                if self.use_cache:
                    self._search_cache[cache_key] = results
                
                logger.info(f"Found {len(results)} securities for query: {query}")
                return results
            else:
                logger.error(f"MOEX ISS API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching MOEX for '{query}': {e}")
            return []
    
    def _parse_iss_response(self, data: Dict[str, Any]) -> List[MOEXSecurityInfo]:
        """
        Парсинг ответа от MOEX ISS API
        
        Формат ответа:
        {
          "securities": {
            "columns": ["secid", "shortname", "regnumber", "name", "isin", ...],
            "data": [
              ["SBER", "Сбербанк", "...", "ПАО Сбербанк", "RU0009029540", ...],
              ...
            ]
          }
        }
        """
        results = []
        
        try:
            securities = data.get("securities", {})
            columns = securities.get("columns", [])
            rows = securities.get("data", [])
            
            # Находим индексы нужных полей
            col_index = {col: idx for idx, col in enumerate(columns)}
            
            for row in rows:
                # Создаем словарь из строки
                row_dict = dict(zip(columns, row))
                
                # Парсим основные поля
                security = MOEXSecurityInfo(
                    secid=row_dict.get("secid", ""),
                    shortname=row_dict.get("shortname", ""),
                    name=row_dict.get("name", ""),
                    isin=row_dict.get("isin"),
                    regnumber=row_dict.get("regnumber"),
                    is_traded=row_dict.get("is_traded", 0) == 1,
                    market=row_dict.get("market"),
                    engine=row_dict.get("engine"),
                    type=row_dict.get("type"),
                    primary_boardid=row_dict.get("primary_boardid")
                )
                
                # Фильтруем: только акции и торгуемые инструменты
                # или хотя бы с ISIN кодом
                if security.secid and (security.isin or security.is_traded):
                    results.append(security)
        
        except Exception as e:
            logger.error(f"Error parsing MOEX ISS response: {e}")
        
        return results
    
    async def find_best_match(
        self,
        company_name: str,
        prefer_traded: bool = True,
        prefer_shares: bool = True
    ) -> Optional[MOEXSecurityInfo]:
        """
        Найти наилучшее совпадение для компании
        
        Args:
            company_name: Название компании из NER
            prefer_traded: Предпочитать торгуемые инструменты
            prefer_shares: Предпочитать акции
            
        Returns:
            Лучшее совпадение или None
        """
        results = await self.search_by_query(company_name, limit=20)
        
        if not results:
            return None
        
        # Применяем фильтры и сортировку
        scored_results = []
        
        for security in results:
            score = 0.0
            
            # Базовый счет - схожесть названий
            if company_name.lower() in security.shortname.lower():
                score += 50
            if company_name.lower() in security.name.lower():
                score += 30
            
            # Бонусы
            if prefer_traded and security.is_traded:
                score += 20
            
            if prefer_shares and security.market in ["shares", "stock"]:
                score += 15
            
            # Приоритет для основных режимов торгов
            if security.primary_boardid in ["TQBR", "TQTF"]:
                score += 10
            
            # Наличие ISIN - очень важно
            if security.isin:
                score += 25
            
            scored_results.append((score, security))
        
        # Сортируем по убыванию score
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        if scored_results and scored_results[0][0] > 0:
            best_match = scored_results[0][1]
            logger.info(
                f"Best match for '{company_name}': "
                f"{best_match.secid} ({best_match.shortname}) "
                f"[score: {scored_results[0][0]}]"
            )
            return best_match
        
        return None
    
    async def auto_learn_from_ner(
        self,
        entity_name: str,
        min_confidence_score: float = 50.0,
        save_alias: bool = True
    ) -> Optional[MOEXSecurityInfo]:
        """
        Автоматическое обучение: найти и запомнить связь NER сущности с MOEX инструментом
        
        Args:
            entity_name: Название организации из NER
            min_confidence_score: Минимальный score для автоматического запоминания
            save_alias: Сохранить ли алиас автоматически
            
        Returns:
            Найденный инструмент или None
        """
        # Проверяем, может уже знаем этот алиас
        known_ticker = self.alias_manager.get_ticker(entity_name)
        if known_ticker:
            logger.debug(f"Already know alias: {entity_name} -> {known_ticker}")
            # Все равно делаем поиск, чтобы вернуть полную информацию
            results = await self.search_by_query(known_ticker, limit=1)
            return results[0] if results else None
        
        # Ищем на MOEX
        best_match = await self.find_best_match(entity_name)
        
        if best_match:
            # Если нашли с хорошим score - запоминаем
            if save_alias:
                normalized_name = entity_name.lower().strip()
                self.alias_manager.add_learned_alias(
                    normalized_name,
                    best_match.secid,
                    auto_save=True
                )
                logger.info(
                    f"Auto-learned new alias: {normalized_name} -> {best_match.secid} "
                    f"(ISIN: {best_match.isin})"
                )
        
        return best_match
    
    async def get_security_details(self, secid: str) -> Optional[MOEXSecurityInfo]:
        """
        Получить детальную информацию об инструменте по тикеру
        
        Args:
            secid: Тикер инструмента (например, "SBER")
            
        Returns:
            Информация об инструменте или None
        """
        if not self.http_client:
            await self.initialize()
        
        try:
            # Запрос детальной информации
            # Документация: https://iss.moex.com/iss/reference/13
            url = f"{self.MOEX_ISS_BASE_URL}/securities/{secid}.json"
            params = {
                "iss.meta": "off",
                "iss.only": "description,boards"
            }
            
            response = await self.http_client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_security_details(data, secid)
            else:
                logger.error(f"MOEX ISS API error for {secid}: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting security details for {secid}: {e}")
            return None
    
    def _parse_security_details(self, data: Dict[str, Any], secid: str) -> Optional[MOEXSecurityInfo]:
        """Парсинг детальной информации об инструменте"""
        try:
            description = data.get("description", {})
            boards = data.get("boards", {})
            
            # Парсим описание
            desc_columns = description.get("columns", [])
            desc_data = description.get("data", [])
            
            info = {"secid": secid}
            
            for row in desc_data:
                if len(row) >= 3:
                    name = row[0]
                    value = row[2]
                    
                    if name == "SHORTNAME":
                        info["shortname"] = value
                    elif name == "NAME":
                        info["name"] = value
                    elif name == "ISIN":
                        info["isin"] = value
                    elif name == "REGNUMBER":
                        info["regnumber"] = value
                    elif name == "TYPE":
                        info["type"] = value
            
            # Находим основной режим торгов
            board_columns = boards.get("columns", [])
            board_data = boards.get("data", [])
            
            for row in board_data:
                row_dict = dict(zip(board_columns, row))
                if row_dict.get("is_primary") == 1:
                    info["primary_boardid"] = row_dict.get("boardid")
                    info["market"] = row_dict.get("market")
                    info["engine"] = row_dict.get("engine")
                    info["is_traded"] = row_dict.get("is_traded", 0) == 1
                    break
            
            return MOEXSecurityInfo(
                secid=info.get("secid", secid),
                shortname=info.get("shortname", ""),
                name=info.get("name", ""),
                isin=info.get("isin"),
                regnumber=info.get("regnumber"),
                is_traded=info.get("is_traded", False),
                market=info.get("market"),
                engine=info.get("engine"),
                type=info.get("type"),
                primary_boardid=info.get("primary_boardid")
            )
            
        except Exception as e:
            logger.error(f"Error parsing security details: {e}")
            return None
    
    def clear_cache(self):
        """Очистить кеш поисковых запросов"""
        self._search_cache.clear()
        logger.info("Search cache cleared")


# ============================================================================
# Пример использования
# ============================================================================

async def example_usage():
    """Пример автоматического поиска и обучения"""
    
    searcher = MOEXAutoSearch()
    await searcher.initialize()
    
    try:
        # Пример 1: Прямой поиск
        print("=== Прямой поиск ===")
        results = await searcher.search_by_query("Сбербанк", limit=5)
        for result in results:
            print(f"  {result.secid} - {result.shortname} (ISIN: {result.isin})")
        
        # Пример 2: Поиск лучшего совпадения
        print("\n=== Поиск лучшего совпадения ===")
        companies = ["Газпром", "Яндекс", "Норильский никель", "Группа ПИК"]
        for company in companies:
            match = await searcher.find_best_match(company)
            if match:
                print(f"  {company} -> {match.secid} ({match.shortname}) ISIN: {match.isin}")
            else:
                print(f"  {company} -> НЕ НАЙДЕНО")
        
        # Пример 3: Автообучение из NER сущностей
        print("\n=== Автообучение ===")
        ner_entities = [
            "ПАО Лукойл",
            "ВТБ банк",
            "Московская биржа",
            "X5 Retail Group"
        ]
        
        for entity in ner_entities:
            learned = await searcher.auto_learn_from_ner(entity, save_alias=True)
            if learned:
                print(f"  ✓ Learned: {entity} -> {learned.secid} (ISIN: {learned.isin})")
            else:
                print(f"  ✗ Failed to learn: {entity}")
        
        # Пример 4: Детальная информация
        print("\n=== Детальная информация ===")
        details = await searcher.get_security_details("SBER")
        if details:
            print(f"  Тикер: {details.secid}")
            print(f"  Название: {details.shortname}")
            print(f"  ISIN: {details.isin}")
            print(f"  Торгуется: {details.is_traded}")
            print(f"  Рынок: {details.market}")
            print(f"  Режим торгов: {details.primary_boardid}")
        
    finally:
        await searcher.close()


if __name__ == "__main__":
    asyncio.run(example_usage())

