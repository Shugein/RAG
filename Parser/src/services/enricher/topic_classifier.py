#Parser.src/services/enricher/topic_classifier.py
"""
Классификатор новостей по отраслям, странам и типам
Интегрирован с графовой моделью Neo4j
"""

import re
import logging
import asyncio
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json

import httpx
from redis import asyncio as aioredis

from Parser.src.core.config import settings
from Parser.src.graph_models import (
    News, Company, Sector, Country, Market, 
    NewsType, NewsSubtype, GraphService
)
from Parser.src.services.enricher.sector_mapper import SectorMapper, SectorTaxonomy

logger = logging.getLogger(__name__)




@dataclass 
class ClassificationResult:
    """Результат классификации"""
    # Отрасли
    primary_sector: Optional[str] = None
    secondary_sector: Optional[str] = None
    sector_confidence: float = 0.0
    
    # Страны
    primary_country: Optional[str] = None
    countries_mentioned: List[str] = None
    
    # Тип новости
    news_type: Optional[NewsType] = None
    news_subtype: Optional[NewsSubtype] = None
    type_confidence: float = 0.0
    
    # Дополнительные метки
    tags: List[str] = None
    is_market_wide: bool = False
    is_regulatory: bool = False
    is_earnings: bool = False
    
    def __post_init__(self):
        if self.countries_mentioned is None:
            self.countries_mentioned = []
        if self.tags is None:
            self.tags = []


class TopicClassifier:
    """
    Классификатор новостей по отраслям, странам и типам
    Интегрирован с графовой моделью для создания связей
    """
    
    def __init__(self, taxonomy: SectorTaxonomy = SectorTaxonomy.ICB):
        """
        Args:
            taxonomy: Используемая таксономия отраслей
        """
        self.taxonomy = taxonomy
        self.http_client: Optional[httpx.AsyncClient] = None
        self.redis: Optional[aioredis.Redis] = None
        self.graph: Optional[GraphService] = None
        
        # Маппер секторов
        self.sector_mapper = SectorMapper(taxonomy)
        
        # Кеш для классификаций
        self._classification_cache: Dict[str, ClassificationResult] = {}
        
        # Счетчики
        self.stats = {
            "total_classifications": 0,
            "cache_hits": 0,
            "sector_classifications": 0,
            "country_classifications": 0,
            "news_type_classifications": 0
        }
    
    async def initialize(self):
        """Инициализация сервиса"""
        
        # HTTP клиент для внешних API
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "RADAR-AI-TopicClassifier/1.0"},
            trust_env=False  # Ignore environment proxy settings
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
        
        # Создаем констрейнты если нужно
        await self.graph.create_constraints()
        
        logger.info(f"TopicClassifier initialized with {self.taxonomy} taxonomy")
    
    async def close(self):
        """Закрытие соединений"""
        if self.http_client:
            await self.http_client.aclose()
        if self.redis:
            await self.redis.close()
        if self.graph:
            await self.graph.close()
    
    async def classify_news(
        self,
        news: News, 
        companies: List[Company] = None,
        entities: List[Dict] = None
    ) -> ClassificationResult:
        """
        Классифицировать новость по отраслям, странам и типам
        
        Args:
            news: Объект новости
            companies: Список связанных компаний (опционально)
            entities: NER сущности (опционально)
            
        Returns:
            Результат классификации
        """
        self.stats["total_classifications"] += 1
        
        # Проверяем кеш
        cache_key = f"classification:{news.id}"
        cached = await self._get_cached_classification(cache_key)
        if cached:
            self.stats["cache_hits"] += 1
            return cached
        
        # Создаем результат
        result = ClassificationResult()
        
        # 1. Классификация по отраслям
        if companies:
            await self._classify_by_sectors(result, companies, news)
        
        # 2. Классификация по странам
        await self._classify_by_countries(result, news, entities)
        
        # 3. Классификация типа новости
        await self._classify_news_type(result, news, companies)
        
        # 4. Дополнительные теги
        await self._extract_additional_tags(result, news)
        
        # Кешируем результат
        await self._cache_classification(cache_key, result)
        
        return result
    
    async def _classify_by_sectors(
        self, 
        result: ClassificationResult, 
        companies: List[Company], 
        news: News
    ):
        """Классификация по отраслям на основе связанных компаний"""
        
        if not companies:
            return
        
        # Получаем секторы компаний из графа или определяем по тикеру
        company_sectors = {}
        for company in companies:
            sector = await self._get_company_sector(company)
            if sector:
                company_sectors[company.id] = sector
        
        if not company_sectors:
            return
        
        # Определяем основной сектор (по количеству упоминаний)
        sector_counts = {}
        for sector in company_sectors.values():
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        
        # Сортируем по частоте
        sorted_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_sectors:
            result.primary_sector = sorted_sectors[0][0]
            result.sector_confidence = min(sorted_sectors[0][1] / len(companies), 1.0)
            
            if len(sorted_sectors) > 1:
                result.secondary_sector = sorted_sectors[1][0]
        
        self.stats["sector_classifications"] += 1
        
        # Создаем связи в графе
        await self._create_sector_relationships(news, company_sectors)
    
    async def _get_company_sector(self, company: Company) -> Optional[str]:
        """Получить сектор компании из графа или определить по тикеру"""
        
        # Сначала пробуем получить из графа
        if self.graph:
            try:
                async with self.graph.driver.session() as session:
                    query = """
                    MATCH (c:Company {id: $company_id})-[:BELONGS_TO]->(s:Sector)
                    RETURN s.id as sector_id, s.name as sector_name
                    """
                    result = await session.run(query, company_id=company.id)
                    record = await result.single()
                    
                    if record:
                        return record["sector_id"]
            except Exception as e:
                logger.debug(f"Error getting company sector from graph: {e}")
        
        # Если не найдено в графе, определяем по тикеру
        if company.ticker:
            sector_info = self.sector_mapper.get_sector_by_ticker(company.ticker)
            if sector_info:
                # Сохраняем в граф для будущего использования
                await self._save_company_sector_to_graph(company, sector_info)
                return sector_info.id
        
        return None
    
    async def _save_company_sector_to_graph(self, company: Company, sector_info):
        """Сохранить сектор компании в граф"""
        
        if not self.graph:
            return
        
        try:
            async with self.graph.driver.session() as session:
                # Создаем сектор если его нет
                await session.run("""
                    MERGE (s:Sector {id: $sector_id})
                    SET s.name = $sector_name,
                        s.taxonomy = $taxonomy,
                        s.level = $level,
                        s.parent_id = $parent_id,
                        s.description = $description,
                        s.updated_at = datetime()
                """, 
                sector_id=sector_info.id,
                sector_name=sector_info.name,
                taxonomy=self.taxonomy.value,
                level=sector_info.level,
                parent_id=sector_info.parent_id,
                description=sector_info.description
                )
                
                # Связываем компанию с сектором
                await session.run("""
                    MATCH (c:Company {id: $company_id})
                    MATCH (s:Sector {id: $sector_id})
                    MERGE (c)-[:BELONGS_TO]->(s)
                    SET c.updated_at = datetime()
                """, company_id=company.id, sector_id=sector_info.id)
        
        except Exception as e:
            logger.error(f"Error saving company sector to graph: {e}")
    
    async def _create_sector_relationships(self, news: News, company_sectors: Dict[str, str]):
        """Создать связи новости с секторами в графе"""
        
        if not self.graph:
            return
        
        try:
            async with self.graph.driver.session() as session:
                # Создаем секторы если их нет
                for sector_id in set(company_sectors.values()):
                    await session.run("""
                        MERGE (s:Sector {id: $sector_id})
                        SET s.taxonomy = $taxonomy,
                            s.updated_at = datetime()
                    """, sector_id=sector_id, taxonomy=self.taxonomy.value)
                
                # Связываем новость с секторами
                for company_id, sector_id in company_sectors.items():
                    await session.run("""
                        MATCH (n:News {id: $news_id})
                        MATCH (s:Sector {id: $sector_id})
                        MERGE (n)-[:ABOUT_SECTOR]->(s)
                        SET s.updated_at = datetime()
                    """, news_id=news.id, sector_id=sector_id)
        
        except Exception as e:
            logger.error(f"Error creating sector relationships: {e}")
    
    async def _classify_by_countries(
        self, 
        result: ClassificationResult, 
        news: News, 
        entities: List[Dict] = None
    ):
        """Классификация по странам"""
        
        countries = set()
        
        # 1. Извлекаем страны из текста
        text_countries = await self._extract_countries_from_text(news.text)
        countries.update(text_countries)
        
        # 2. Извлекаем из заголовка
        title_countries = await self._extract_countries_from_text(news.title)
        countries.update(title_countries)
        
        # 3. Из NER сущностей
        if entities:
            for entity in entities:
                if entity.get("type") == "LOC":
                    country = await self._normalize_country_name(entity.get("text", ""))
                    if country:
                        countries.add(country)
        
        # 4. Из языка новости
        if news.lang_norm:
            country_from_lang = self._get_country_from_language(news.lang_norm)
            if country_from_lang:
                countries.add(country_from_lang)
        
        if countries:
            result.countries_mentioned = list(countries)
            result.primary_country = result.countries_mentioned[0]  # Первая как основная
            
            # Создаем связи в графе
            await self._create_country_relationships(news, countries)
        
        self.stats["country_classifications"] += 1
    
    async def _extract_countries_from_text(self, text: str) -> Set[str]:
        """Извлечь упоминания стран из текста"""
        
        countries = set()
        
        # Словарь стран и их вариантов
        country_patterns = {
            # Россия
            "RU": [r"\bросси[яи]\b", r"\bроссийск[аяой]\b", r"\bрф\b", r"\bроссия\b"],
            # США
            "US": [r"\bсша\b", r"\bамерик[аи]\b", r"\bамериканск[аяой]\b", r"\busa\b"],
            # Китай
            "CN": [r"\bкита[йя]\b", r"\bкитайск[аяой]\b", r"\bchina\b"],
            # Германия
            "DE": [r"\bгермани[яи]\b", r"\bнемецк[аяой]\b", r"\bgermany\b"],
            # Великобритания
            "GB": [r"\bвеликобритани[яи]\b", r"\bбритани[яи]\b", r"\bангли[яи]\b", r"\buk\b"],
            # Франция
            "FR": [r"\bфранци[яи]\b", r"\bфранцузск[аяой]\b", r"\bfrance\b"],
            # Япония
            "JP": [r"\bяпони[яи]\b", r"\bяпонск[аяой]\b", r"\bjapan\b"],
            # Канада
            "CA": [r"\bканад[аы]\b", r"\bканадск[аяой]\b", r"\bcanada\b"],
            # Индия
            "IN": [r"\bинди[яи]\b", r"\bиндийск[аяой]\b", r"\bindia\b"],
            # Бразилия
            "BR": [r"\bбразили[яи]\b", r"\bбразильск[аяой]\b", r"\bbrazil\b"],
        }
        
        text_lower = text.lower()
        
        for country_code, patterns in country_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    countries.add(country_code)
                    break
        
        return countries
    
    async def _normalize_country_name(self, country_name: str) -> Optional[str]:
        """Нормализовать название страны к коду"""
        
        country_mapping = {
            "россия": "RU", "российская федерация": "RU", "рф": "RU",
            "сша": "US", "америка": "US", "соединенные штаты": "US",
            "китай": "CN", "китайская народная республика": "CN",
            "германия": "DE", "немецкая федеративная республика": "DE",
            "великобритания": "GB", "британия": "GB", "англия": "GB",
            "франция": "FR", "французская республика": "FR",
            "япония": "JP", "японская империя": "JP",
            "канада": "CA", "канадская конфедерация": "CA",
            "индия": "IN", "республика индия": "IN",
            "бразилия": "BR", "федеративная республика бразилия": "BR",
        }
        
        normalized = country_name.lower().strip()
        return country_mapping.get(normalized)
    
    def _get_country_from_language(self, lang_code: str) -> Optional[str]:
        """Получить страну по коду языка"""
        
        lang_to_country = {
            "ru": "RU", "en": "US", "zh": "CN", "de": "DE", 
            "fr": "FR", "ja": "JP", "es": "ES", "pt": "BR",
            "it": "IT", "ko": "KR", "ar": "SA", "hi": "IN"
        }
        
        return lang_to_country.get(lang_code.lower())
    
    async def _create_country_relationships(self, news: News, countries: Set[str]):
        """Создать связи новости со странами в графе"""
        
        if not self.graph:
            return
        
        try:
            async with self.graph.driver.session() as session:
                # Создаем страны если их нет
                for country_code in countries:
                    country_name = self._get_country_name(country_code)
                    await session.run("""
                        MERGE (c:Country {code: $country_code})
                        SET c.name = $country_name,
                            c.updated_at = datetime()
                    """, country_code=country_code, country_name=country_name)
                
                # Связываем новость со странами
                for country_code in countries:
                    await session.run("""
                        MATCH (n:News {id: $news_id})
                        MATCH (c:Country {code: $country_code})
                        MERGE (n)-[:ABOUT_COUNTRY]->(c)
                    """, news_id=news.id, country_code=country_code)
        
        except Exception as e:
            logger.error(f"Error creating country relationships: {e}")
    
    def _get_country_name(self, country_code: str) -> str:
        """Получить полное название страны по коду"""
        
        country_names = {
            "RU": "Россия", "US": "США", "CN": "Китай", "DE": "Германия",
            "GB": "Великобритания", "FR": "Франция", "JP": "Япония",
            "CA": "Канада", "IN": "Индия", "BR": "Бразилия",
            "ES": "Испания", "IT": "Италия", "KR": "Южная Корея",
            "SA": "Саудовская Аравия"
        }
        
        return country_names.get(country_code, country_code)
    
    async def _classify_news_type(
        self, 
        result: ClassificationResult, 
        news: News, 
        companies: List[Company] = None
    ):
        """Классификация типа новости"""
        
        text = f"{news.title} {news.text}".lower()
        
        # Определяем тип новости
        news_type = None
        news_subtype = None
        confidence = 0.0
        
        # 1. Проверяем на корпоративные новости
        if companies and len(companies) == 1:
            # Новость об одной компании
            news_type = NewsType.ONE_COMPANY
            confidence = 0.8
            
            # Определяем подтип
            if any(word in text for word in ["прибыль", "убыток", "выручка", "earnings", "revenue"]):
                news_subtype = NewsSubtype.EARNINGS
            elif any(word in text for word in ["прогноз", "forecast", "guidance", "ожидания"]):
                news_subtype = NewsSubtype.GUIDANCE
            elif any(word in text for word in ["слияние", "поглощение", "m&a", "acquisition"]):
                news_subtype = NewsSubtype.MA
            elif any(word in text for word in ["дефолт", "банкротство", "default", "bankruptcy"]):
                news_subtype = NewsSubtype.DEFAULT
            elif any(word in text for word in ["руководство", "менеджмент", "ceo", "cfo"]):
                news_subtype = NewsSubtype.MANAGEMENT_CHANGE
        
        # 2. Проверяем на рыночные новости
        elif any(word in text for word in ["рынок", "индекс", "market", "index", "торги"]):
            news_type = NewsType.MARKET
            result.is_market_wide = True
            confidence = 0.7
        
        # 3. Проверяем на регуляторные новости
        elif any(word in text for word in ["цб", "цб рф", "банк россии", "регулятор", "санкции", "санкции"]):
            news_type = NewsType.REGULATORY
            result.is_regulatory = True
            confidence = 0.9
            
            if any(word in text for word in ["санкции", "sanctions"]):
                news_subtype = NewsSubtype.SANCTIONS
        
        # 4. Дополнительные подтипы
        if any(word in text for word in ["хак", "взлом", "hack", "breach", "кибератака"]):
            news_subtype = NewsSubtype.HACK
        elif any(word in text for word in ["суд", "иск", "court", "lawsuit", "правовой"]):
            news_subtype = NewsSubtype.LEGAL
        elif any(word in text for word in ["экология", "esg", "устойчивость", "sustainability"]):
            news_subtype = NewsSubtype.ESG
        elif any(word in text for word in ["логистика", "поставки", "supply chain", "цепочка"]):
            news_subtype = NewsSubtype.SUPPLY_CHAIN
        elif any(word in text for word in ["технический сбой", "outage", "сбой системы"]):
            news_subtype = NewsSubtype.TECH_OUTAGE
        
        result.news_type = news_type
        result.news_subtype = news_subtype
        result.type_confidence = confidence
        
        self.stats["news_type_classifications"] += 1
    
    async def _extract_additional_tags(self, result: ClassificationResult, news: News):
        """Извлечь дополнительные теги"""
        
        text = f"{news.title} {news.text}".lower()
        tags = []
        
        # Финансовые теги
        if any(word in text for word in ["дивиденды", "dividend", "выплата"]):
            tags.append("dividends")
        
        if any(word in text for word in ["облигации", "bonds", "долг"]):
            tags.append("bonds")
        
        if any(word in text for word in ["акции", "shares", "equity"]):
            tags.append("equity")
        
        # Технологические теги
        if any(word in text for word in ["ии", "искусственный интеллект", "ai", "машинное обучение"]):
            tags.append("ai")
        
        if any(word in text for word in ["блокчейн", "криптовалюта", "blockchain", "crypto"]):
            tags.append("crypto")
        
        # ESG теги
        if any(word in text for word in ["зеленые", "green", "энергия", "renewable"]):
            tags.append("green")
        
        if any(word in text for word in ["социальная ответственность", "social responsibility"]):
            tags.append("social")
        
        # Временные теги
        if any(word in text for word in ["квартал", "quarter", "q1", "q2", "q3", "q4"]):
            tags.append("quarterly")
        
        if any(word in text for word in ["год", "year", "годовой", "annual"]):
            tags.append("annual")
        
        result.tags = tags
    
    async def _get_cached_classification(self, cache_key: str) -> Optional[ClassificationResult]:
        """Получить классификацию из кеша"""
        
        if not self.redis:
            return None
        
        try:
            cached = await self.redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return ClassificationResult(**data)
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
        
            return None
    
    async def _cache_classification(self, cache_key: str, result: ClassificationResult):
        """Сохранить классификацию в кеш"""
        
        if not self.redis:
            return
        
        try:
            data = json.dumps(result.__dict__, default=str)
            await self.redis.setex(cache_key, 3600, data)  # 1 час
        except Exception as e:
            logger.debug(f"Cache set error: {e}")
    
    async def create_graph_relationships(
        self, 
        news: News, 
        classification: ClassificationResult,
        companies: List[Company] = None
    ):
        """Создать все связи в графе на основе классификации"""
        
        if not self.graph:
            return
        
        try:
            async with self.graph.driver.session() as session:
                # 1. Обновляем новость с классификацией
                await session.run("""
                    MATCH (n:News {id: $news_id})
                    SET n.news_type = $news_type,
                        n.news_subtype = $news_subtype,
                        n.is_market_wide = $is_market_wide,
                        n.is_regulatory = $is_regulatory,
                        n.tags = $tags,
                        n.classified_at = datetime()
                """, 
                news_id=news.id,
                news_type=classification.news_type.value if classification.news_type else None,
                news_subtype=classification.news_subtype.value if classification.news_subtype else None,
                is_market_wide=classification.is_market_wide,
                is_regulatory=classification.is_regulatory,
                tags=classification.tags
                )
                
                # 2. Связи с секторами уже созданы в _create_sector_relationships
                # 3. Связи со странами уже созданы в _create_country_relationships
                
                # 4. Создаем связи с компаниями если есть
                if companies:
                    for company in companies:
                        await session.run("""
                            MATCH (n:News {id: $news_id})
                            MERGE (c:Company {id: $company_id})
                            MERGE (n)-[:ABOUT]->(c)
                            SET c.updated_at = datetime()
                        """, news_id=news.id, company_id=company.id)
        
        except Exception as e:
            logger.error(f"Error creating graph relationships: {e}")
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику работы"""
        return self.stats.copy()


# ============================================================================
# Пример использования
# ============================================================================

async def example_usage():
    """Пример использования TopicClassifier"""
    
    classifier = TopicClassifier(taxonomy=SectorTaxonomy.ICB)
    await classifier.initialize()
    
    try:
        # Создаем тестовую новость
        news = News(
            id="test_news_1",
            url="https://example.com/news1",
            title="Сбербанк отчитался о рекордной прибыли в третьем квартале",
            text="ПАО Сбербанк объявил о росте чистой прибыли на 25% в третьем квартале 2024 года. Выручка банка составила 1.2 трлн рублей.",
            lang_orig="ru",
            lang_norm="ru",
            published_at=datetime.utcnow(),
            source="test"
        )
        
        # Создаем тестовые компании
        companies = [
            Company(
                id="sber",
                name="ПАО Сбербанк",
                ticker="SBER",
                country_code="RU"
            )
        ]
        
        # Классифицируем
        result = await classifier.classify_news(news, companies)
        
        print("Результат классификации:")
        print(f"  Основной сектор: {result.primary_sector}")
        print(f"  Уверенность в секторе: {result.sector_confidence}")
        print(f"  Основная страна: {result.primary_country}")
        print(f"  Упоминаемые страны: {result.countries_mentioned}")
        print(f"  Тип новости: {result.news_type}")
        print(f"  Подтип: {result.news_subtype}")
        print(f"  Теги: {result.tags}")
        print(f"  Рыночная новость: {result.is_market_wide}")
        print(f"  Регуляторная: {result.is_regulatory}")
        
        # Создаем связи в графе
        await classifier.create_graph_relationships(news, result, companies)
        
        # Статистика
        print(f"\nСтатистика: {classifier.get_stats()}")
        
    finally:
        await classifier.close()


if __name__ == "__main__":
    asyncio.run(example_usage())