# Topic Classifier - Классификация новостей по отраслям и странам

## 🎯 Назначение

`TopicClassifier` - это система для автоматической классификации новостей по:
- **Отраслям** (ICB/GICS/NACE таксономии)
- **Странам** (извлечение из текста и языка)
- **Типам новостей** (корпоративные, рыночные, регуляторные)
- **Дополнительным тегам** (дивиденды, AI, ESG и т.д.)

## 🏗️ Архитектура

### Основные компоненты:

1. **`TopicClassifier`** - главный класс классификатора
2. **`SectorMapper`** - маппинг компаний по отраслям
3. **`ClassificationResult`** - результат классификации
4. **Интеграция с Neo4j** - создание связей в графе

### Схема работы:

```
Новость + Компании + NER сущности
           ↓
    TopicClassifier
           ↓
    ┌─────────────────┬─────────────────┬─────────────────┐
    │   Секторы       │    Страны       │   Типы новостей │
    │   (ICB/GICS)    │   (извлечение)  │   (классификация)│
    └─────────────────┴─────────────────┴─────────────────┘
           ↓
    ClassificationResult
           ↓
    Создание связей в Neo4j
```

## 📦 Компоненты

### 1. `TopicClassifier`

**Основные методы:**
- `classify_news()` - классификация новости
- `create_graph_relationships()` - создание связей в графе

**Инициализация:**
```python
from Parser.src.services.enricher.topic_classifier import TopicClassifier, SectorTaxonomy

classifier = TopicClassifier(taxonomy=SectorTaxonomy.ICB)
await classifier.initialize()
```

### 2. `SectorMapper`

**Поддерживаемые таксономии:**
- **ICB** (Industry Classification Benchmark) - по умолчанию
- **GICS** (Global Industry Classification Standard)
- **NACE** (European Classification)

**Основные методы:**
- `get_sector_by_ticker()` - сектор по тикеру MOEX
- `get_sector_by_keywords()` - сектор по ключевым словам
- `get_sector_hierarchy()` - иерархия сектора

### 3. `ClassificationResult`

**Поля результата:**
```python
@dataclass
class ClassificationResult:
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
```

## 🚀 Использование

### Базовый пример:

```python
from Parser.src.services.enricher.topic_classifier import TopicClassifier
from Parser.src.graph_models import News, Company

# Инициализация
classifier = TopicClassifier()
await classifier.initialize()

# Создание новости
news = News(
    id="news_1",
    url="https://example.com/news1",
    title="Сбербанк отчитался о рекордной прибыли",
    text="ПАО Сбербанк объявил о росте прибыли на 25%...",
    lang_orig="ru",
    lang_norm="ru",
    published_at=datetime.utcnow(),
    source="test"
)

# Связанные компании
companies = [
    Company(id="sber", name="ПАО Сбербанк", ticker="SBER", country_code="RU")
]

# Классификация
result = await classifier.classify_news(news, companies)

print(f"Сектор: {result.primary_sector}")  # "9010" (Banks)
print(f"Страна: {result.primary_country}")  # "RU"
print(f"Тип: {result.news_type}")  # NewsType.ONE_COMPANY
print(f"Подтип: {result.news_subtype}")  # NewsSubtype.EARNINGS
print(f"Теги: {result.tags}")  # ["dividends", "quarterly"]

# Создание связей в графе
await classifier.create_graph_relationships(news, result, companies)

await classifier.close()
```

### Расширенный пример с NER:

```python
# NER сущности
entities = [
    {"type": "ORG", "text": "ПАО Сбербанк"},
    {"type": "LOC", "text": "Россия"},
    {"type": "MONEY", "text": "1.2 трлн рублей"}
]

# Классификация с NER
result = await classifier.classify_news(news, companies, entities)
```

## 🏭 Классификация по отраслям

### Поддерживаемые секторы (ICB):

**Level 1 - Industries:**
- `1000` - Oil & Gas
- `2000` - Basic Materials  
- `3000` - Industrials
- `4000` - Consumer Goods
- `5000` - Health Care
- `6000` - Consumer Services
- `7000` - Telecommunications
- `8000` - Utilities
- `9000` - Financials
- `9500` - Technology

**Level 2 - Supersectors:**
- `9010` - Banks
- `1010` - Oil & Gas Producers
- `9510` - Software & Computer Services
- И многие другие...

### Маппинг тикеров MOEX:

```python
# Примеры маппинга
"SBER" → "9010" (Banks)
"GAZP" → "1010" (Oil & Gas Producers)  
"YNDX" → "9510" (Software)
"MGNT" → "6010" (General Retailers)
"GMKN" → "2040" (Mining)
```

### Определение по ключевым словам:

```python
keywords = ["банк", "кредит", "финансы"]
sector = mapper.get_sector_by_keywords(keywords)
# → "9010" (Banks)
```

## 🌍 Классификация по странам

### Извлечение из текста:

**Поддерживаемые страны:**
- `RU` - Россия
- `US` - США  
- `CN` - Китай
- `DE` - Германия
- `GB` - Великобритания
- `FR` - Франция
- `JP` - Япония
- И другие...

**Паттерны поиска:**
```python
# Русские варианты
"россия" → "RU"
"российский" → "RU" 
"рф" → "RU"

# Английские варианты
"usa" → "US"
"america" → "US"
"united states" → "US"
```

### Определение по языку:

```python
lang_to_country = {
    "ru": "RU",
    "en": "US", 
    "zh": "CN",
    "de": "DE"
}
```

## 📰 Классификация типов новостей

### Основные типы:

- **`ONE_COMPANY`** - новость об одной компании
- **`MARKET`** - рыночная новость
- **`REGULATORY`** - регуляторная новость

### Подтипы:

- **`EARNINGS`** - отчетность, прибыль
- **`GUIDANCE`** - прогнозы, ожидания
- **`MA`** - слияния и поглощения
- **`DEFAULT`** - дефолт, банкротство
- **`SANCTIONS`** - санкции
- **`HACK`** - кибератаки
- **`LEGAL`** - судебные дела
- **`ESG`** - экология, устойчивость
- **`SUPPLY_CHAIN`** - логистика, поставки
- **`TECH_OUTAGE`** - технические сбои
- **`MANAGEMENT_CHANGE`** - смена руководства

### Примеры классификации:

```python
# Корпоративная новость
"Сбербанк отчитался о прибыли" 
→ NewsType.ONE_COMPANY, NewsSubtype.EARNINGS

# Рыночная новость  
"Индекс МосБиржи вырос на 2%"
→ NewsType.MARKET

# Регуляторная новость
"ЦБ РФ повысил ключевую ставку"
→ NewsType.REGULATORY

# Санкции
"США ввели санкции против российских банков"
→ NewsType.REGULATORY, NewsSubtype.SANCTIONS
```

## 🏷️ Дополнительные теги

Система автоматически извлекает теги:

**Финансовые:**
- `dividends` - дивиденды
- `bonds` - облигации  
- `equity` - акции

**Технологические:**
- `ai` - искусственный интеллект
- `crypto` - криптовалюты

**ESG:**
- `green` - зеленые технологии
- `social` - социальная ответственность

**Временные:**
- `quarterly` - квартальные отчеты
- `annual` - годовые отчеты

## 🔗 Интеграция с графом

### Создаваемые узлы:

**Sector:**
```cypher
CREATE (s:Sector {
  id: "9010",
  name: "Banks", 
  taxonomy: "ICB",
  level: 2,
  parent_id: "9000"
})
```

**Country:**
```cypher
CREATE (c:Country {
  code: "RU",
  name: "Россия"
})
```

### Создаваемые связи:

**Новость → Сектор:**
```cypher
(n:News)-[:ABOUT_SECTOR]->(s:Sector)
```

**Новость → Страна:**
```cypher
(n:News)-[:ABOUT_COUNTRY]->(c:Country)
```

**Компания → Сектор:**
```cypher
(c:Company)-[:BELONGS_TO]->(s:Sector)
```

**Новость → Компания:**
```cypher
(n:News)-[:ABOUT]->(c:Company)
```

### Обновление новости:

```cypher
MATCH (n:News {id: $news_id})
SET n.news_type = $news_type,
    n.news_subtype = $news_subtype,
    n.is_market_wide = $is_market_wide,
    n.is_regulatory = $is_regulatory,
    n.tags = $tags,
    n.classified_at = datetime()
```

## 📊 Статистика

```python
stats = classifier.get_stats()
# {
#   "total_classifications": 150,
#   "cache_hits": 45,
#   "sector_classifications": 120,
#   "country_classifications": 140,
#   "news_type_classifications": 150
# }
```

## ⚙️ Конфигурация

### Выбор таксономии:

```python
# ICB (по умолчанию)
classifier = TopicClassifier(SectorTaxonomy.ICB)

# GICS
classifier = TopicClassifier(SectorTaxonomy.GICS)

# NACE
classifier = TopicClassifier(SectorTaxonomy.NACE)
```

### Кеширование:

Результаты классификации кешируются в Redis на 1 час для повышения производительности.

## 🧪 Тестирование

Запуск тестов:

```bash
python scripts/test_topic_classifier.py
```

Тесты включают:
1. ✅ Классификацию по секторам
2. ✅ Классификацию по странам  
3. ✅ Классификацию типов новостей
4. ✅ Создание связей в графе
5. ✅ Работу с различными таксономиями

## 🔍 Примеры запросов к графу

### Найти все новости о банковском секторе:

```cypher
MATCH (n:News)-[:ABOUT_SECTOR]->(s:Sector {id: "9010"})
RETURN n.title, n.published_at
ORDER BY n.published_at DESC
```

### Найти новости о российских компаниях:

```cypher
MATCH (n:News)-[:ABOUT_COUNTRY]->(c:Country {code: "RU"})
RETURN n.title, n.news_type
```

### Найти новости о санкциях:

```cypher
MATCH (n:News)
WHERE n.news_subtype = "sanctions"
RETURN n.title, n.published_at
ORDER BY n.published_at DESC
```

### Найти компании в одном секторе:

```cypher
MATCH (c:Company)-[:BELONGS_TO]->(s:Sector {id: "9010"})
RETURN c.name, c.ticker
```

### Анализ по тегам:

```cypher
MATCH (n:News)
WHERE "dividends" IN n.tags
RETURN n.title, n.published_at
ORDER BY n.published_at DESC
```

## 🚀 Производительность

- **Классификация новости:** 50-200 мс
- **Кеш попадания:** < 1 мс
- **Создание связей в графе:** 100-300 мс
- **Общее время обработки:** 150-500 мс

## 🔧 Troubleshooting

### Проблема: Не определяется сектор компании

**Решение:** Проверьте тикер в `SectorMapper.ticker_to_sector`

### Проблема: Не извлекаются страны

**Решение:** Добавьте паттерны в `_extract_countries_from_text`

### Проблема: Неправильная классификация типа новости

**Решение:** Настройте ключевые слова в `_classify_news_type`

## 📈 Метрики качества

Рекомендуется отслеживать:
- Точность классификации секторов
- Полноту извлечения стран
- Правильность определения типов новостей
- Время обработки

## 🔄 Интеграция с pipeline

```python
# В enrichment_service.py
from Parser.src.services.enricher.topic_classifier import TopicClassifier

class EnrichmentService:
    def __init__(self):
        self.topic_classifier = TopicClassifier()
    
    async def process_news(self, news_event):
        # ... существующая логика ...
        
        # Классификация
        classification = await self.topic_classifier.classify_news(
            news, companies, entities
        )
        
        # Создание связей в графе
        await self.topic_classifier.create_graph_relationships(
            news, classification, companies
        )
        
        # Добавление в результат
        news_event["classification"] = classification.__dict__
        
        return news_event
```

## 📚 Дополнительные ресурсы

- [ICB Classification](https://www.ftserussell.com/data/industry-classification-benchmark-icb)
- [GICS Classification](https://www.msci.com/gics)
- [NACE Classification](https://ec.europa.eu/eurostat/statistics-explained/index.php/Glossary:Statistical_classification_of_economic_activities_in_the_European_Community_(NACE))
- [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/)

## 🤝 Вклад в проект

Для добавления новых секторов, стран или типов новостей:

1. Обновите соответствующие словари в `SectorMapper`
2. Добавьте тесты в `test_topic_classifier.py`
3. Обновите документацию
4. Проверьте интеграцию с графом
