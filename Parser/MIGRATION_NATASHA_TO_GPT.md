# Миграция с Natasha на GPT-based NER

## Обзор изменений

Система переходит с библиотеки Natasha (онлайн NER) на GPT-based извлечение сущностей для поддержки всех необходимых данных системы событий (CEG).

## Замененные компоненты

### 1. Старая система Natasha
```python
# Используемые модули Natasha
from natasha import (
    Segmenter, MorphVocab, NewsEmbedding, NewsNERTagger,
    NewsMorphTagger, Doc, OrtoCashersExecutor
)

# Инициализация
segmenter = Segmenter()
morph_vocab = MorphVocab()
emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)
ner_tagger = NewsNERTagger(emb)
news_casher = OrtoCashersExecutor()

# Использование
doc = Doc(text)
doc.segment(segmenter)
doc.tag_morph(morph_tagger)
doc.tag_ner(ner_tagger)
doc.cache(morph_vocab, news_casher)
```

### 2. Новая система GPT-based NER
```python
# Из entity_recognition.py
from entity_recognition import CachedFinanceNERExtractor, ExtractedEntities

# Инициализация
extractor = CachedFinanceNERExtractor(
    api_key=os.environ.get('OPENAI_API_KEY'),
    model="gpt-4o-mini",  # или gpt-5-nano-2025-08-07
    enable_caching=True
)

# Использование
entities = await extractor.extract_entities_async(text)
```

## Извлекаемые данные

### Старая версия (Natasha):
- ORG (организации)
- PER (персоны) 
- LOC (локации)
- Общие NER сущности

### Новая версия (GPT):
```python
{
    "people": [{"name": "ФИО", "position": "должность", "company": "компания"}],
    "companies": [{"name": "название", "ticker": "тикер", "sector": "отрасль"}],
    "markets": [{"name": "рынок", "type": "тип", "value": значение, "change": "изменение"}],
    "financial_metrics": [{"metric_type": "тип", "value": "значение", "company": "компания"}],
    "event_types": ["sanctions", "rate_hike", "earnings", ...],
    "sector": "отрасль",
    "country": "страна",
    "is_anchor_event": true/false,
    "requires_market_data": true/false,
    "urgency_level": "low/normal/high/critical",
    "confidence_score": 0.95
}
```

## Обратная совместимость

Создан класс `CompatibilityWrapper` для постепенной миграции:

```python
from entity_recognition import CachedFinanceNERExtractor, CompatibilityWrapper

extractor = CachedFinanceNERExtractor(api_key="...")
wrapper = CompatibilityWrapper(extractor)

# Использует старый интерфейс
result = await wrapper.extract_entities(text, news_meta)
# Возвращает данные в формате совместимом с существующим кодом
```

## Необходимые изменения в коде

### 1. Обновление enrichment_service.py
```python
# Было:
from natasha import Segmenter, MorphVocab, ..., NewsNERTagger

# Стало:
from entity_recognition import CachedFinanceNERExtractor

class EnrichmentService:
    def __init__(self, session):
        self.extractor = CachedFinanceNERExtractor(
            api_key=settings.OPENAI_API_KEY,
            model="gpt-4o-mini"
        )

    async def extract_and_save_entities(self, news_data, text):
        # Извлекаем через GPT
        entities_result = await self.extractor.extract_entities_async(text)
        
        # Извлекаем компании
        companies = entities_result.companies
        
        # Извлекаем финансовые показатели
        financial_metrics = entities_result.financial_metrics
```

### 2. Обновление event_extractor.py
```python
# Использование новых полей из ExtractedEntities
def extract_events_from_news(self, news, ai_extracted):
    # Определяем event_types из ai_extracted.event_types
    event_types = ai_extracted.event_types or ["general_news"]
    
    # Используем флаги CEG
    is_anchor = ai_extracted.is_anchor_event or False
    confidence = ai_extracted.confidence_score or 0.8
    
    # Сектор и страна
    sector = ai_extracted.sector
    country = ai_extracted.country
```

### 3. Обновление моделей данных
Новые поля добавлены в `entity_recognition.py` в модель `ExtractedEntities`.

## Преимущества новой системы

1. **Полная поддержка CEG**: Извлечение типов событий и метаданных для системы предсказаний
2. **GPT reasoning**: Лучшее понимание контекста и финансовых терминов
3. **Prompt caching**: Экономия до 90% на входных токенах (~$0.003/новость)
4. **Асинхронность**: Параллельная обработка новостей
5. **Расширяемость**: Легко добавлять новые типы данных

## Миграция зависимостей

### requirements.txt
```
# Удаляем старые зависимости Natasha:
# natasha

# Добавляем новые зависимости:
openai>=1.12.0
httpx>=0.25.0
```

### Статистики замены
- **Natasha**: ~50 мегабайт моделей, офлайн обработка
- **GPT-4o-mini**: API calls, но лучшее качество и полная интеграция с CEG

## Обработка ошибок

```python
try:
    entities = await extractor.extract_entities_async(text)
except Exception as e:
    logger.error(f"NER extraction failed: {e}")
    # Fallback на базовую обработку
    entities = ExtractedEntities(companies=[], people=[], ...)
```

## Мониторинг и статистика

Новая система предоставляет детальную статистику:

```python
# Получение статистики
stats = extractor.get_stats_summary()
print(f"Cache hit rate: {stats['cache_hit_rate_percent']}%")
print(f"Token savings: {stats['token_savings_percent']}%")
print(f"Cost per request: ${stats['avg_cost_per_request']:.6f}")
```

Готово к поэтапному переходу с сохранением обратной совместимости.
