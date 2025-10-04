"""
Графовая модель данных для Neo4j согласно Project Charter
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import uuid4
import hashlib

from neo4j import AsyncGraphDatabase
from pydantic import BaseModel, Field
from enum import Enum

# ============================================================================
# ENUMS
# ============================================================================

class InstrumentType(str, Enum):
    EQUITY = "equity"
    ADR = "adr"
    BOND = "bond"
    FUTURE = "future"
    OPTION = "option"
    TOKEN = "token"

class NewsType(str, Enum):
    ONE_COMPANY = "one_company"
    MARKET = "market"
    REGULATORY = "regulatory"
    
class NewsSubtype(str, Enum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    MA = "m&a"
    DEFAULT = "default"
    MACRO = "macro"
    SANCTIONS = "sanctions"
    TECH_OUTAGE = "tech_outage"
    HACK = "hack"
    LEGAL = "legal"
    ESG = "esg"
    SUPPLY_CHAIN = "supply_chain"
    MANAGEMENT_CHANGE = "management_change"

# ============================================================================
# NODE MODELS
# ============================================================================

class Market(BaseModel):
    """Рынок (MOEX, NYSE, NASDAQ, etc.)"""
    id: str
    name: str
    country_code: str
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Sector(BaseModel):
    """Сектор экономики"""
    id: str
    name: str
    taxonomy: str  # ICB/GICS/NACE

class Country(BaseModel):
    """Страна"""
    code: str
    name: str

class Regulator(BaseModel):
    """Регулятор (ЦБ РФ, SEC, etc.)"""
    id: str
    name: str
    country_code: str

class Company(BaseModel):
    """Компания"""
    id: str
    name: str
    ticker: Optional[str] = None
    isin: Optional[str] = None
    country_code: str
    spark_id: Optional[str] = None
    moex_board: Optional[str] = None

class Instrument(BaseModel):
    """Финансовый инструмент"""
    id: str  # exchange+symbol
    symbol: str
    type: InstrumentType
    exchange: str
    currency: str
    
class News(BaseModel):
    """Новость"""
    id: str  # hash(url) или внешний ID
    url: str
    title: str
    text: str
    lang_orig: str
    lang_norm: str
    published_at: datetime
    source: str
    no_impact: bool = False
    news_type: Optional[NewsType] = None
    news_subtype: Optional[NewsSubtype] = None
    
    @classmethod
    def generate_id(cls, url: str) -> str:
        """Генерация ID на основе URL"""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

class Event(BaseModel):
    """Событие (группа связанных новостей)"""
    id: str
    title: str
    from_date: datetime
    to_date: datetime
    type: str

class EventNode(BaseModel):
    """Узел события в CEG (Causal Event Graph)"""
    id: str
    title: str
    ts: datetime  # Время события
    type: str  # sanctions, rate_hike, earnings, etc.
    attrs: Dict[str, Any] = {}  # Атрибуты события
    is_anchor: bool = False
    confidence: float = 0.8

class AnchorEvent(BaseModel):
    """Якорное событие (референсное для CMNLN)"""
    id: str
    title: str
    ts: datetime
    type: str
    is_anchor: bool = True
    usage_count: int = 0  # Сколько раз использовалось

# ============================================================================
# RELATIONSHIP MODELS
# ============================================================================

class AffectsRelation(BaseModel):
    """Связь News -> Company с весом влияния"""
    weight: float  # Вес влияния [-1, 1]
    window: str    # Временное окно (15m, 60m, 1d, 5d)
    dt: datetime   # Время расчета
    method: str    # Метод расчета

class CovariatesRelation(BaseModel):
    """Корреляция между компаниями"""
    rho: float     # Коэффициент корреляции
    window: str    # Окно расчета
    updated_at: datetime

class PrecedesRelation(BaseModel):
    """Временная последовательность Event -> Event"""
    time_diff: float  # Разница во времени (секунды)

class CausesRelation(BaseModel):
    """Причинная связь Event -> Event (CEG)"""
    kind: str  # HYPOTHESIS | RETRO | CONFIRMED
    sign: str  # + | - | ±
    expected_lag: str  # 0-1d, 1h-1d, 1-4w, etc.
    conf_text: float = 0.0  # Уверенность из текстовых маркеров
    conf_prior: float = 0.0  # Из доменных priors
    conf_market: float = 0.0  # Из рыночной реакции
    conf_total: float = 0.0  # Общая уверенность
    evidence_set: List[str] = []  # IDs Evidence Events

class ImpactsRelation(BaseModel):
    """Влияние события на инструмент"""
    price_impact: float = 0.0  # AR (abnormal return)
    volume_impact: float = 0.0  # Volume spike
    sentiment: float = 0.0  # [-1, 1]
    window: str = "1d"  # Окно наблюдения

class AlignsToRelation(BaseModel):
    """Связь Event -> AnchorEvent (схожесть)"""
    sim: float  # Similarity score [0, 1]

class EvidenceOfRelation(BaseModel):
    """Event -> Chain (Evidence Event в цепочке)"""
    chain_id: str
    order: int  # Порядковый номер в цепочке

# ============================================================================
# NEO4J SERVICE
# ============================================================================

class GraphService:
    """Сервис для работы с графовой БД Neo4j"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def close(self):
        await self.driver.close()
    
    async def create_constraints(self):
        """Создание уникальных констрейнтов"""
        async with self.driver.session() as session:
            queries = [
                "CREATE CONSTRAINT news_id IF NOT EXISTS FOR (n:News) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
                "CREATE CONSTRAINT instrument_id IF NOT EXISTS FOR (i:Instrument) REQUIRE i.id IS UNIQUE",
                "CREATE CONSTRAINT market_id IF NOT EXISTS FOR (m:Market) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT sector_id IF NOT EXISTS FOR (s:Sector) REQUIRE s.id IS UNIQUE",
                "CREATE CONSTRAINT country_code IF NOT EXISTS FOR (c:Country) REQUIRE c.code IS UNIQUE",
                "CREATE CONSTRAINT regulator_id IF NOT EXISTS FOR (r:Regulator) REQUIRE r.id IS UNIQUE",
                "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
                "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
                "CREATE INDEX news_published_at IF NOT EXISTS FOR (n:News) ON (n.published_at)",
                "CREATE INDEX company_ticker IF NOT EXISTS FOR (c:Company) ON (c.ticker)",
                "CREATE INDEX company_country IF NOT EXISTS FOR (c:Company) ON (c.country_code)",
                "CREATE INDEX instrument_exchange IF NOT EXISTS FOR (i:Instrument) ON (i.exchange)",
                "CREATE INDEX instrument_symbol IF NOT EXISTS FOR (i:Instrument) ON (i.symbol)",
                "CREATE INDEX regulator_country IF NOT EXISTS FOR (r:Regulator) ON (r.country_code)",
                "CREATE INDEX event_type IF NOT EXISTS FOR (e:Event) ON (e.type)",
                "CREATE INDEX event_dates IF NOT EXISTS FOR (e:Event) ON (e.from_date, e.to_date)",
            ]
            for query in queries:
                await session.run(query)
    
    async def upsert_news(self, news: News):
        """Upsert новости"""
        async with self.driver.session() as session:
            query = """
            MERGE (n:News {id: $id})
            ON CREATE SET 
                n.url = $url, 
                n.title = $title, 
                n.text = $text,
                n.published_at = datetime($published_at),
                n.source = $source, 
                n.lang_orig = $lang_orig, 
                n.lang_norm = $lang_norm,
                n.no_impact = $no_impact,
                n.news_type = $news_type,
                n.news_subtype = $news_subtype
            ON MATCH SET 
                n.title = $title, 
                n.published_at = datetime($published_at), 
                n.source = $source
            RETURN n
            """
            await session.run(query, **news.dict())
    
    async def link_news_to_company(self, news_id: str, company_id: str, affects: AffectsRelation):
        """Связать новость с компанией и установить вес влияния"""
        async with self.driver.session() as session:
            query = """
            MATCH (n:News {id: $news_id})
            MERGE (c:Company {id: $company_id})
            MERGE (n)-[r:AFFECTS]->(c)
            SET r.weight = $weight,
                r.window = $window,
                r.dt = datetime($dt),
                r.method = $method
            RETURN n, r, c
            """
            await session.run(
                query,
                news_id=news_id,
                company_id=company_id,
                weight=affects.weight,
                window=affects.window,
                dt=affects.dt.isoformat(),
                method=affects.method
            )
    
    async def update_covariance(self, company1_id: str, company2_id: str, covar: CovariatesRelation):
        """Обновить корреляцию между компаниями"""
        async with self.driver.session() as session:
            query = """
            MERGE (c1:Company {id: $c1})
            MERGE (c2:Company {id: $c2})
            MERGE (c1)-[cv:COVARIATES_WITH]-(c2)
            SET cv.rho = $rho,
                cv.window = $window,
                cv.updated_at = datetime($updated_at)
            RETURN cv
            """
            await session.run(
                query,
                c1=company1_id,
                c2=company2_id,
                rho=covar.rho,
                window=covar.window,
                updated_at=covar.updated_at.isoformat()
            )
    
    async def get_correlated_companies(self, company_id: str, min_correlation: float = 0.3, limit: int = 10):
        """Получить скоррелированные компании"""
        async with self.driver.session() as session:
            query = """
            MATCH (c:Company {id: $company_id})-[cv:COVARIATES_WITH]-(other:Company)
            WHERE abs(cv.rho) >= $min_correlation
            RETURN other, cv.rho as correlation
            ORDER BY abs(cv.rho) DESC
            LIMIT $limit
            """
            result = await session.run(
                query,
                company_id=company_id,
                min_correlation=min_correlation,
                limit=limit
            )
            return [record async for record in result]
    
    async def spread_impact(self, news_id: str, source_company_id: str, max_depth: int = 2):
        """Распространение эффекта новости на скоррелированные компании"""
        async with self.driver.session() as session:
            # Защита от циклов через visited
            query = """
            MATCH (n:News {id: $news_id})-[r:AFFECTS]->(source:Company {id: $source_company_id})
            WITH n, source, r.weight as base_weight
            MATCH path = (source)-[:COVARIATES_WITH*1..""" + str(max_depth) + """]->(target:Company)
            WHERE NOT (n)-[:AFFECTS]->(target)
            WITH n, target, base_weight, 
                 reduce(rho = 1.0, rel in relationships(path) | rho * rel.rho) as total_correlation
            WHERE abs(total_correlation) > 0.1
            MERGE (n)-[new_r:AFFECTS]->(target)
            SET new_r.weight = base_weight * total_correlation * 0.5,  // Decay factor
                new_r.window = '60m',
                new_r.dt = datetime(),
                new_r.method = 'correlation_spread'
            RETURN target.id as company_id, new_r.weight as impact_weight
            """
            result = await session.run(
                query,
                news_id=news_id,
                source_company_id=source_company_id
            )
            return [record async for record in result]
    
    async def create_news_node(self, news: News):
        """Создать узел новости в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (n:News {id: $id})
            SET n.url = $url,
                n.title = $title,
                n.text = $text,
                n.published_at = datetime($published_at),
                n.source = $source,
                n.lang_orig = $lang_orig,
                n.lang_norm = $lang_norm,
                n.no_impact = $no_impact,
                n.news_type = $news_type,
                n.news_subtype = $news_subtype,
                n.created_at = datetime()
            RETURN n
            """
            await session.run(query, 
                id=str(news.id),
                url=news.url,
                title=news.title,
                text=news.text_plain or news.text_html or "",
                published_at=news.published_at.isoformat(),
                source=str(news.source_id),
                lang_orig=news.lang,
                lang_norm=news.lang,
                no_impact=False,
                news_type="news",
                news_subtype=None
            )
    
    async def create_entity_node(self, entity_id: str, text: str, entity_type: str, confidence: float):
        """Создать узел сущности в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (e:Entity {id: $entity_id})
            SET e.text = $text,
                e.type = $entity_type,
                e.confidence = $confidence,
                e.created_at = datetime()
            RETURN e
            """
            await session.run(query, 
                entity_id=entity_id,
                text=text,
                entity_type=entity_type,
                confidence=confidence
            )
    
    async def create_company_node(self, company_id: str, name: str, ticker: str, is_traded: bool):
        """Создать узел компании в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (c:Company {id: $company_id})
            ON CREATE SET 
                c.name = $name,
                c.ticker = $ticker,
                c.is_traded = $is_traded,
                c.created_at = datetime(),
                c.country_code = 'RU'
            ON MATCH SET 
                c.name = $name,
                c.ticker = $ticker,
                c.is_traded = $is_traded,
                c.updated_at = datetime()
            RETURN c
            """
            await session.run(query,
                company_id=company_id,
                name=name,
                ticker=ticker,
                is_traded=is_traded
            )
    
    async def create_topic_node(self, topic_id: str, topic_name: str, confidence: float):
        """Создать узел темы в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (t:Topic {id: $topic_id})
            ON CREATE SET 
                t.name = $topic_name,
                t.confidence = $confidence,
                t.created_at = datetime()
            ON MATCH SET 
                t.name = $topic_name,
                t.confidence = $confidence,
                t.updated_at = datetime()
            RETURN t
            """
            await session.run(query,
                topic_id=topic_id,
                topic_name=topic_name,
                confidence=confidence
            )
    
    async def link_news_to_entity(self, news_id: str, entity_id: str):
        """Связать новость с сущностью"""
        async with self.driver.session() as session:
            query = """
            MATCH (n:News {id: $news_id})
            MATCH (e:Entity {id: $entity_id})
            MERGE (n)-[:MENTIONS]->(e)
            RETURN n, e
            """
            await session.run(query, news_id=news_id, entity_id=entity_id)
    
    async def link_news_to_company(self, news_id: str, company_id: str):
        """Связать новость с компанией"""
        async with self.driver.session() as session:
            query = """
            MATCH (n:News {id: $news_id})
            MATCH (c:Company {id: $company_id})
            MERGE (n)-[:ABOUT]->(c)
            RETURN n, c
            """
            await session.run(query, news_id=news_id, company_id=company_id)
    
    async def link_news_to_topic(self, news_id: str, topic_id: str):
        """Связать новость с темой"""
        async with self.driver.session() as session:
            query = """
            MATCH (n:News {id: $news_id})
            MATCH (t:Topic {id: $topic_id})
            MERGE (n)-[:HAS_TOPIC]->(t)
            RETURN n, t
            """
            await session.run(query, news_id=news_id, topic_id=topic_id)
    
    async def create_sector_node(self, sector_id: str, sector_name: str, taxonomy: str = "ICB"):
        """Создать узел сектора в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (s:Sector {id: $sector_id})
            ON CREATE SET 
                s.name = $sector_name,
                s.taxonomy = $taxonomy,
                s.created_at = datetime()
            ON MATCH SET 
                s.name = $sector_name,
                s.taxonomy = $taxonomy,
                s.updated_at = datetime()
            RETURN s
            """
            await session.run(query,
                sector_id=sector_id,
                sector_name=sector_name,
                taxonomy=taxonomy
            )
    
    async def link_company_to_sector(self, company_id: str, sector_id: str):
        """Связать компанию с сектором"""
        async with self.driver.session() as session:
            query = """
            MATCH (c:Company {id: $company_id})
            MATCH (s:Sector {id: $sector_id})
            MERGE (c)-[:IN_SECTOR]->(s)
            RETURN c, s
            """
            await session.run(query, company_id=company_id, sector_id=sector_id)
    
    async def create_market_node(self, market_id: str, market_name: str, country_code: str, source: str):
        """Создать узел рынка в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (m:Market {id: $market_id})
            ON CREATE SET 
                m.name = $market_name,
                m.country_code = $country_code,
                m.source = $source,
                m.created_at = datetime()
            ON MATCH SET 
                m.name = $market_name,
                m.country_code = $country_code,
                m.source = $source,
                m.updated_at = datetime()
            RETURN m
            """
            await session.run(query,
                market_id=market_id,
                market_name=market_name,
                country_code=country_code,
                source=source
            )
    
    async def link_company_to_market(self, company_id: str, market_id: str):
        """Связать компанию с рынком"""
        async with self.driver.session() as session:
            query = """
            MATCH (c:Company {id: $company_id})
            MATCH (m:Market {id: $market_id})
            MERGE (m)-[:HAS_COMPANY]->(c)
            RETURN m, c
            """
            await session.run(query, company_id=company_id, market_id=market_id)
    
    async def create_country_node(self, country_code: str, country_name: str):
        """Создать узел страны в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (c:Country {code: $country_code})
            ON CREATE SET 
                c.name = $country_name,
                c.created_at = datetime()
            ON MATCH SET 
                c.name = $country_name,
                c.updated_at = datetime()
            RETURN c
            """
            await session.run(query,
                country_code=country_code,
                country_name=country_name
            )
    
    async def link_company_to_country(self, company_id: str, country_code: str):
        """Связать компанию со страной"""
        async with self.driver.session() as session:
            query = """
            MATCH (c:Company {id: $company_id})
            MATCH (country:Country {code: $country_code})
            MERGE (c)-[:IN_COUNTRY]->(country)
            RETURN c, country
            """
            await session.run(query, company_id=company_id, country_code=country_code)
    
    async def create_regulator_node(self, regulator_id: str, regulator_name: str, country_code: str):
        """Создать узел регулятора в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (r:Regulator {id: $regulator_id})
            ON CREATE SET 
                r.name = $regulator_name,
                r.country_code = $country_code,
                r.created_at = datetime()
            ON MATCH SET 
                r.name = $regulator_name,
                r.country_code = $country_code,
                r.updated_at = datetime()
            RETURN r
            """
            await session.run(query,
                regulator_id=regulator_id,
                regulator_name=regulator_name,
                country_code=country_code
            )
    
    async def link_regulator_covers_market(self, regulator_id: str, market_id: str):
        """Связать регулятора с рынком"""
        async with self.driver.session() as session:
            query = """
            MATCH (r:Regulator {id: $regulator_id})
            MATCH (m:Market {id: $market_id})
            MERGE (r)-[:COVERS]->(m)
            RETURN r, m
            """
            await session.run(query, regulator_id=regulator_id, market_id=market_id)
    
    async def link_regulator_covers_company(self, regulator_id: str, company_id: str):
        """Связать регулятора с компанией"""
        async with self.driver.session() as session:
            query = """
            MATCH (r:Regulator {id: $regulator_id})
            MATCH (c:Company {id: $company_id})
            MERGE (r)-[:COVERS]->(c)
            RETURN r, c
            """
            await session.run(query, regulator_id=regulator_id, company_id=company_id)
    
    async def link_regulator_covers_sector(self, regulator_id: str, sector_id: str):
        """Связать регулятора с сектором"""
        async with self.driver.session() as session:
            query = """
            MATCH (r:Regulator {id: $regulator_id})
            MATCH (s:Sector {id: $sector_id})
            MERGE (r)-[:COVERS]->(s)
            RETURN r, s
            """
            await session.run(query, regulator_id=regulator_id, sector_id=sector_id)
    
    async def create_instrument_node(self, instrument_id: str, symbol: str, instrument_type: str, exchange: str, currency: str):
        """Создать узел финансового инструмента в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (i:Instrument {id: $instrument_id})
            ON CREATE SET 
                i.symbol = $symbol,
                i.type = $instrument_type,
                i.exchange = $exchange,
                i.currency = $currency,
                i.created_at = datetime()
            ON MATCH SET 
                i.symbol = $symbol,
                i.type = $instrument_type,
                i.exchange = $exchange,
                i.currency = $currency,
                i.updated_at = datetime()
            RETURN i
            """
            await session.run(query,
                instrument_id=instrument_id,
                symbol=symbol,
                instrument_type=instrument_type,
                exchange=exchange,
                currency=currency
            )
    
    async def link_company_to_instrument(self, company_id: str, instrument_id: str):
        """Связать компанию с финансовым инструментом"""
        async with self.driver.session() as session:
            query = """
            MATCH (c:Company {id: $company_id})
            MATCH (i:Instrument {id: $instrument_id})
            MERGE (c)-[:HAS_INSTRUMENT]->(i)
            RETURN c, i
            """
            await session.run(query, company_id=company_id, instrument_id=instrument_id)
    
    async def create_event_node(self, event_id: str, event_title: str, from_date: str, to_date: str, event_type: str):
        """Создать узел события в графе"""
        async with self.driver.session() as session:
            query = """
            MERGE (e:Event {id: $event_id})
            ON CREATE SET 
                e.title = $event_title,
                e.from_date = datetime($from_date),
                e.to_date = datetime($to_date),
                e.type = $event_type,
                e.created_at = datetime()
            ON MATCH SET 
                e.title = $event_title,
                e.from_date = datetime($from_date),
                e.to_date = datetime($to_date),
                e.type = $event_type,
                e.updated_at = datetime()
            RETURN e
            """
            await session.run(query,
                event_id=event_id,
                event_title=event_title,
                from_date=from_date,
                to_date=to_date,
                event_type=event_type
            )
    
    async def link_news_to_event(self, news_id: str, event_id: str):
        """Связать новость с событием"""
        async with self.driver.session() as session:
            query = """
            MATCH (n:News {id: $news_id})
            MATCH (e:Event {id: $event_id})
            MERGE (n)-[:PART_OF]->(e)
            RETURN n, e
            """
            await session.run(query, news_id=news_id, event_id=event_id)
    
    async def link_news_to_market(self, news_id: str, market_id: str):
        """Связать новость с рынком"""
        async with self.driver.session() as session:
            query = """
            MATCH (n:News {id: $news_id})
            MATCH (m:Market {id: $market_id})
            MERGE (n)-[:ABOUT_MARKET]->(m)
            RETURN n, m
            """
            await session.run(query, news_id=news_id, market_id=market_id)
    
    async def link_news_affects_company(self, news_id: str, company_id: str, weight: float, window: str, method: str):
        """Создать связь влияния новости на компанию с весом"""
        async with self.driver.session() as session:
            query = """
            MATCH (n:News {id: $news_id})
            MATCH (c:Company {id: $company_id})
            MERGE (n)-[r:AFFECTS]->(c)
            SET r.weight = $weight,
                r.window = $window,
                r.dt = datetime(),
                r.method = $method
            RETURN n, r, c
            """
            await session.run(query,
                news_id=news_id,
                company_id=company_id,
                weight=weight,
                window=window,
                method=method
            )
    
    async def link_company_covariates_with(self, company1_id: str, company2_id: str, rho: float, window: str):
        """Создать связь корреляции между компаниями"""
        async with self.driver.session() as session:
            query = """
            MATCH (c1:Company {id: $company1_id})
            MATCH (c2:Company {id: $company2_id})
            MERGE (c1)-[cv:COVARIATES_WITH]-(c2)
            SET cv.rho = $rho,
                cv.window = $window,
                cv.updated_at = datetime()
            RETURN cv
            """
            await session.run(query,
                company1_id=company1_id,
                company2_id=company2_id,
                rho=rho,
                window=window
            )

    # ============================================================================
    # CEG (Causal Event Graph) Methods
    # ============================================================================

    async def create_event_ceg(self, event: EventNode):
        """Создать узел события CEG в Neo4j"""
        async with self.driver.session() as session:
            query = """
            MERGE (e:EventNode {id: $id})
            ON CREATE SET
                e.title = $title,
                e.ts = datetime($ts),
                e.type = $type,
                e.attrs = $attrs,
                e.is_anchor = $is_anchor,
                e.confidence = $confidence,
                e.created_at = datetime()
            ON MATCH SET
                e.title = $title,
                e.ts = datetime($ts),
                e.type = $type,
                e.attrs = $attrs,
                e.is_anchor = $is_anchor,
                e.confidence = $confidence,
                e.updated_at = datetime()
            RETURN e
            """
            await session.run(query,
                id=event.id,
                title=event.title,
                ts=event.ts.isoformat(),
                type=event.type,
                attrs=event.attrs,
                is_anchor=event.is_anchor,
                confidence=event.confidence
            )

    async def link_events_precedes(self, event1_id: str, event2_id: str, time_diff: float):
        """Создать связь PRECEDES между событиями (временная последовательность)"""
        async with self.driver.session() as session:
            query = """
            MATCH (e1:EventNode {id: $event1_id})
            MATCH (e2:EventNode {id: $event2_id})
            MERGE (e1)-[r:PRECEDES]->(e2)
            SET r.time_diff = $time_diff
            RETURN r
            """
            await session.run(query,
                event1_id=event1_id,
                event2_id=event2_id,
                time_diff=time_diff
            )

    async def link_events_causes(self, cause_id: str, effect_id: str, causes: CausesRelation):
        """Создать причинную связь CAUSES между событиями"""
        async with self.driver.session() as session:
            query = """
            MATCH (cause:EventNode {id: $cause_id})
            MATCH (effect:EventNode {id: $effect_id})
            MERGE (cause)-[r:CAUSES]->(effect)
            SET r.kind = $kind,
                r.sign = $sign,
                r.expected_lag = $expected_lag,
                r.conf_text = $conf_text,
                r.conf_prior = $conf_prior,
                r.conf_market = $conf_market,
                r.conf_total = $conf_total,
                r.evidence_set = $evidence_set,
                r.updated_at = datetime()
            RETURN r
            """
            await session.run(query,
                cause_id=cause_id,
                effect_id=effect_id,
                kind=causes.kind,
                sign=causes.sign,
                expected_lag=causes.expected_lag,
                conf_text=causes.conf_text,
                conf_prior=causes.conf_prior,
                conf_market=causes.conf_market,
                conf_total=causes.conf_total,
                evidence_set=causes.evidence_set
            )

    async def link_event_impacts_instrument(self, event_id: str, instrument_id: str, impacts: ImpactsRelation):
        """Создать связь IMPACTS между событием и инструментом"""
        async with self.driver.session() as session:
            query = """
            MATCH (e:EventNode {id: $event_id})
            MATCH (i:Instrument {id: $instrument_id})
            MERGE (e)-[r:IMPACTS]->(i)
            SET r.price_impact = $price_impact,
                r.volume_impact = $volume_impact,
                r.sentiment = $sentiment,
                r.window = $window,
                r.updated_at = datetime()
            RETURN r
            """
            await session.run(query,
                event_id=event_id,
                instrument_id=instrument_id,
                price_impact=impacts.price_impact,
                volume_impact=impacts.volume_impact,
                sentiment=impacts.sentiment,
                window=impacts.window
            )

    async def link_event_aligns_to_anchor(self, event_id: str, anchor_id: str, sim: float):
        """Создать связь ALIGNS_TO между событием и якорным событием"""
        async with self.driver.session() as session:
            query = """
            MATCH (e:EventNode {id: $event_id})
            MATCH (a:EventNode {id: $anchor_id})
            WHERE a.is_anchor = true
            MERGE (e)-[r:ALIGNS_TO]->(a)
            SET r.sim = $sim,
                r.updated_at = datetime()
            RETURN r
            """
            await session.run(query,
                event_id=event_id,
                anchor_id=anchor_id,
                sim=sim
            )

    async def link_event_evidence_of(self, event_id: str, chain_id: str, order: int):
        """Создать связь EVIDENCE_OF для Evidence Event в причинной цепочке"""
        async with self.driver.session() as session:
            query = """
            MATCH (e:EventNode {id: $event_id})
            MERGE (chain:CausalChain {id: $chain_id})
            MERGE (e)-[r:EVIDENCE_OF]->(chain)
            SET r.order = $order
            RETURN r
            """
            await session.run(query,
                event_id=event_id,
                chain_id=chain_id,
                order=order
            )

    async def find_anchor_events(self, event_type: str = None, limit: int = 5):
        """Найти якорные события для CMNLN"""
        async with self.driver.session() as session:
            if event_type:
                query = """
                MATCH (e:EventNode)
                WHERE e.is_anchor = true AND e.type = $event_type
                RETURN e
                ORDER BY e.ts DESC
                LIMIT $limit
                """
                result = await session.run(query, event_type=event_type, limit=limit)
            else:
                query = """
                MATCH (e:EventNode)
                WHERE e.is_anchor = true
                RETURN e
                ORDER BY e.ts DESC
                LIMIT $limit
                """
                result = await session.run(query, limit=limit)

            return [record async for record in result]

    async def find_causal_chain(self, from_event_id: str, max_depth: int = 3):
        """Найти причинную цепочку с помощью BFS (поиск Evidence Events)"""
        async with self.driver.session() as session:
            query = """
            MATCH path = (start:EventNode {id: $from_event_id})-[:CAUSES*1..""" + str(max_depth) + """]->(end:EventNode)
            WITH path, relationships(path) as rels
            WHERE all(r in rels WHERE r.conf_total >= 0.3)
            RETURN path,
                   [node in nodes(path) | node.id] as event_ids,
                   length(path) as depth,
                   reduce(conf = 1.0, r in rels | conf * r.conf_total) as chain_confidence
            ORDER BY chain_confidence DESC
            LIMIT 10
            """
            result = await session.run(query, from_event_id=from_event_id)
            return [record async for record in result]

    async def find_similar_events(self, event_id: str, min_similarity: float = 0.5, limit: int = 5):
        """Найти похожие события на основе типа и атрибутов"""
        async with self.driver.session() as session:
            query = """
            MATCH (e1:EventNode {id: $event_id})
            MATCH (e2:EventNode)
            WHERE e1.id <> e2.id AND e1.type = e2.type
            RETURN e2,
                   CASE
                     WHEN e1.attrs.companies IS NOT NULL AND e2.attrs.companies IS NOT NULL
                     THEN size([c IN e1.attrs.companies WHERE c IN e2.attrs.companies]) * 1.0 /
                          size(e1.attrs.companies + [c IN e2.attrs.companies WHERE NOT c IN e1.attrs.companies])
                     ELSE 0.5
                   END as similarity
            ORDER BY similarity DESC
            LIMIT $limit
            """
            result = await session.run(query, event_id=event_id, limit=limit)
            return [record async for record in result]

    async def get_event_causal_context(self, event_id: str):
        """Получить полный причинный контекст события (предшественники и последователи)"""
        async with self.driver.session() as session:
            query = """
            MATCH (e:EventNode {id: $event_id})
            OPTIONAL MATCH (before)-[:CAUSES]->(e)
            OPTIONAL MATCH (e)-[:CAUSES]->(after)
            OPTIONAL MATCH (e)-[:IMPACTS]->(i:Instrument)
            RETURN e,
                   collect(DISTINCT before) as predecessors,
                   collect(DISTINCT after) as successors,
                   collect(DISTINCT {instrument: i, relation: properties(r)}) as impacts
            """
            result = await session.run(query, event_id=event_id)
            records = [record async for record in result]
            return records[0] if records else None