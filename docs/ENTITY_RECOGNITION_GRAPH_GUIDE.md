# Руководство по использованию расширенного Entity Recognition для построения Neo4j графа

## Обзор

`entity_recognition.py` расширен для извлечения всех данных, необходимых для построения графа знаний из русских финансовых новостей. Поддерживается как базовое извлечение сущностей, так и расширенный режим для построения графа.

## Основные возможности

### 1. Базовое извлечение сущностей

```python
from entity_recognition import CachedFinanceNERExtractor

# Инициализация
extractor = CachedFinanceNERExtractor(api_key="your_api_key")

# Одиночная новость
entities = extractor.extract_entities(news_text)

# Batch обработка
results = extractor.extract_entities_batch(news_list, parallel=True)
```

### 2. Расширенное извлечение для графа

```python
# Извлечение данных для построения Neo4j графа
graph_entities = extractor.extract_graph_entities(news_text)

# Batch режим для графа
graph_results = extractor.extract_graph_entities_batch(news_list, parallel=True)
```

## Модели данных

### Базовые модели
- `Person` - Персоны с должностями и компаниями
- `Company` - Компании с тикерами и отраслями  
- `Market` - Рынки и биржи
- `FinancialMetric` - Финансовые показатели

### Расширенные модели для графа
- `MarketIndex` - Биржевые индексы с значениями
- `CurrencyRate` - Валютные курсы
- `FinancialInstrument` - Акции, облигации
- `Relationship` - Связи между сущностями
- `TemporalEvent` - Временные события
- `CausalRelation` - Причинно-следственные связи
- `ImpactEstimate` - Оценки влияния

### Комплексная модель
```python
class GraphReadyEntities(BaseModel):
    # Основные сущности
    people: List[Person]
    companies: List[Company] 
    markets: List[Market]
    financial_metrics: List[FinancialMetric]
    
    # Дополнительные данные для графа
    market_indices: List[MarketIndex]
    currency_rates: List[CurrencyRate]
    financial_instruments: List[FinancialInstrument]
    sectors: List[Sector]
    
    # Связи и отношения
    relationships: List[Relationship]
    temporal_events: List[TemporalEvent] 
    causal_relations: List[CausalRelation]
    
    # Оценки влияния
    impact_estimates: List[ImpactEstimate]
    
    # Контекстная информация
    sentiment_score: Optional[float]
    urgency_level: str
    news_type: Optional[str]
    geographic_scope: List[str]
```

## Преобразование в Neo4j

```python
from entity_recognition import GraphDataMapper

mapper = GraphDataMapper()

# Извлечение данных
graph_entities = extractor.extract_graph_entities(news_text)

# Преобразование в формат Neo4j
neo4j_nodes = mapper.map_to_neo4j_nodes(graph_entities, network_id="news_001")
neo4j_relationships = mapper.map_to_neo4j_relationships(graph_entities)
neo4j_impacts = mapper.map_to_impact_estimates(graph_entities)
```

## Производительность

### Batch обработка
- **Параллельная обработка**: все новости анализируются одновременно
- **Кэширование**: статичные части промптов кэшируются автоматически
- **Скорость**: ~2-5 новостей/сек в зависимости от сложности
- **Экономия**: до 50% снижение стоимости за счет кэширования

### Кэширование
```python
# Статистика кэширования
stats = extractor.get_stats_summary()
print(f"Кэш-хиты: {stats['cache_hit_rate_percent']:.1f}%")
print(f"Экономия токенов: {stats['token_savings_percent']:.1f}%")
print(f"Сохранено средств: ${stats['estimated_savings_usd']:.4f}")
```

## Примеры использования

### Простой анализ
```python
news = "Сбербанк объявил дивиденды в размере 25 рублей на акцию."
entities = extractor.extract_entities(news)

print(f"Компании: {len(entities.companies)}")
print(f"Метрики: {len(entities.financial_metrics)}")
```

### Глубокий графовый анализ
```python
complex_news = """
ЦБ РФ повысил ключевую ставку до 16%. Это решение затронет 
крупнейшие банки - Сбербанк, ВТБ, Газпромбанк. Глава Сбербанка 
Герман Греф ожидает роста ставок по кредитам на 2-3 процентных пункта.
"""

graph_data = extractor.extract_graph_entities(complex_news)

print(f"Связи между сущностями: {len(graph_data.relationships)}")
print(f"Причинно-следственные связи: {len(graph_data.causal_relations)}")
print(f"Ознаки влияния: {len(graph_data.impact_estimates)}")
print(f"Тип новости: {graph_data.news_type}")
print(f"Sentiment: {graph_data.sentiment_score}")
```

### Batch обработка для интеграции в pipeline
```python
# Для больших объемов новостей
news_batch = [
    "Сбербанк объявил дивиденды...",
    "ЦБ повысил ключевую ставку...", 
    "Яндекс представил отчетность..."
] * 100  # 300 новостей

# Параллельная обработка
start_time = time.time()
results = extractor.extract_graph_entities_batch(news_batch, parallel=True)
elapsed = time.time() - start_time

print(f"Обработано {len(results)} новостей за {elapsed:.2f} сек")
print(f"Скорость: {len(results)/elapsed:.1f} новостей/сек")
```

## Интеграция с существующим проектом

### Замена старого NER
```python
# ВParser.src/services/enricher/enrichment_service.py
from entity_recognition import CachedFinanceNERExtractor

class EnrichmentService:
    def __init__(self, session: AsyncSession):
        # Используем расширенный извлекитель
        self.ai_ner = CachedFinanceNERExtractor(
            api_key=os.getenv("API_KEY_2"),
            enable_caching=True
        )
    
    async def enrich_news_for_graph(self, news_text: str) -> GraphReadyEntities:
        """Обогащение новости данными для графа"""
        return self.ai_ner.extract_graph_entities(news_text)
```

### Batch обогащение
```python
async def enrich_news_batch(self, news_items: List[str]) -> List[GraphReadyEntities]:
    """Массовое обогащение новостей"""
    return self.ai_ner.extract_graph_entities_batch(news_items, parallel=True)
```

## Демонстрационные скрипты

### Основная демонстрация
```bash
python entity_recognition.py
```

### Интеграция с графом
```bash 
python demo_graph_integration.py
```

### Графовый анализ
```python
from entity_recognition import demo_graph_extraction

# Демонстрация расширенного анализа
result = demo_graph_extraction()
```

## Конфигурация

### Переменные окружения
```bash
# Обязательные
API_KEY_2=your_openai_api_key

# Опциональные для Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### Настройки модели
```python
extractor = CachedFinanceNERExtractor(
    api_key="your_key",
    model="gpt-4o-mini",  # или "gpt-5-nano-2025-08-07"
    enable_caching=True
)
```

## Типы извлеченных связей

### Связи между сущностями
- `works_for` - Персона работает в компании
- `owns_stock_in` - Компания владеет долей
- `operates_in` - Компания работает в секторе
- `regulates` - Регулятор контролирует
- `competes_with` - Конкуренция между компаниями
- `supplies_to` - Поставки между компаниями

### Причинно-следственные связи
- `regulatory` - Регуляторные решения и их последствия
- `economic` - Макроэкономические факторы
- `market_correlation` - Корреляции на рынке
- `cascade_effect` - Каскадные эффекты

### Оценки влияния
- **На цены**: положительное/отрицательное влияние на стоимость акций
- **На объемы**: изменение торговых объемов  
- **На настроения**: влияние на инвесторские настроения
- **Временные окна**: от 15 минут до месяца

## Заключение

Расширенный Entity Recognition обеспечивает:
- ✅ Полное извлечение данных для Neo4j графа
- ✅ Высокую производительность batch обработки
- ✅ Встроенное кэширование для экономии
- ✅ Готовую интеграцию с существующим проектом
- ✅ Расширенный анализ связей и влияний

Поддерживайте регулярные обновления финансового глоссария для повышения точности извлечения сущностей.
