# Миграция с Natasha на GPT-based NER для системы CEG

## Обзор изменений

Система событий (CEG) требует полных данных для корректной работы системы предсказаний и построения причинно-следственных графов. Старый NER на базе Natasha не может предоставить все необходимые данные.

## Обновленный NER в `entity_recognition.py`

### Новые поля для системы событий:

```python
class ExtractedEntities(BaseModel):
    # Стандартные NER поля
    publication_date: Optional[str]
    people: List[Person]
    companies: List[Company]
    markets: List[Market]
    financial_metrics: List[FinancialMetric]
    
    # 🆕 Новые поля для CEG системы
    sector: Optional[str]                    # Основная отрасль события
    country: Optional[str]                   # Страна события
    event_types: List[str]                   # Типы событий (sanctions, rate_hike, earnings, etc.)
    event: Optional[str]                     # Описание события
    
    # 🆕 Метаданные для анализа влияния
    confidence_score: float = 0.8           # Общая уверенность [0, 1]
    language: str = "ru"                    # Язык документа
    
    # 🆕 Флаги для обработки CEG
    is_anchor_event: bool = False            # Является ли якорным событием
    requires_market_data: bool = False       # Требует анализ рыночных данных
    urgency_level: str = "normal"           # Срочность: low/normal/high/critical
```

### Расширенный глоссарий событий:

```python
# Типы событий для автоматической классификации
event_types = {
    "sanctions": ["санкции", "ограничени", "запрет"],
    "rate_hike": ["ключевая ставка", "повысил ставку", "цб повысил"],
    "earnings": ["прибыль", "выручка", "отчетность", "результаты"],
    "m&a": ["слияние", "поглощение", "сделка", "приобрет"],
    "default': ["дефолт", "банкротство", "невыплата"],
    "dividends": ["дивиденды", "выплата дивидендов"],
    "ipo": ["ipo", "размещение", "первичное размещение"],
    "regulatory": ["регулятор", "закон", "постановление"],
    "management_change": ["новый директор", "смена руководства"],
    # ... и другие типы
}

# Секторы экономики
sectors = {
    "oil_gas": ["нефть", "газ", "энергетика"],
    "financial": ["банк", "финансы", "кредит"],
    "technology": ["технологии", "IT", "цифр"],
    # ... и другие секторы
}
```

## Интеграция с enrichment_service.py

### Обновленное извлечение данных:

```python
# В EnrichmentService.enrich_news()
ai_extracted = await self.ai_ner.extract_entities_async(full_text, verbose=False)

# Добавляем новые поля для CEG системы
enrichment["event_types"] = ai_extracted.event_types
enrichment["ceg_flags"] = {
    "is_anchor_event": ai_extracted.is_anchor_event,
    "requires_market_data": ai_extracted.requires_market_data,
    "urgency_level": ai_extracted.urgency_level,
    "confidence_score": ai_extracted.confidence_score
}
enrichment["sector"] = ai_extracted.sector
enrichment["country"] = ai_extracted.country
```

## Совместимость со старой системой

### CompatibilityWrapper для поэтапной миграции:

```python
# Обеспечивает совместимость с кодом, использующим Natasha
class CompatibilityWrapper:
    def __init__(self, extractor):
        self.extractor = extractor
        
    async def extract_entities(self, text, news_meta=None):
        # Извлекаем через новый NER
        extracted = await self.extractor.extract_entities_async(text)
        
        # Преобразуем в старый формат Natasha
        return {
            'matches': [...],  # Сущности в формате Natasha
            'norm': {...},     # Нормализованные данные
            'fact': {...},     # Факты
            'meta': {
                **news_meta,
                'event_types': extracted.event_types,
                'is_anchor': extracted.is_anchor_event,
                'urgency': extracted.urgency_level
            }
        }
```

## Данные для работы CEG системы

### Минимальный набор данных из новости:

1. **Заголовок и текст** - для понимания контента
2. **Время публикации** - для временных связей в CEG
3. **Компании/тикеры** - для линковки к рынкам
4. **Типы событий** - для классификации в CEG
5. **Флаг якорности** - для определения значимости
6. **Уровень срочности** - для приоритизации

### Для EventPredictionEngine:

```python
# Извлеченные типы событий автоматически определяют предсказания
if "sanctions" in ai_extracted.event_types:
    predictions.append({
        "type": "follow_up_events",
        "predicted": ["sanctions_compliance", "trade_restrictions"],
        "probability": 0.7,
        "window_days": 7
    })
```

### Для ImpactCalculator:

```python
# Автоматический запуск для событий с requires_market_data = True
if ai_extracted.requires_market_data:
    impacts = await calculate_impact(
        news_id=str(news.id),
        company_ids=company_tickers,
        published_at=news.published_at
    )
```

### Для ImportanceCalculator:

```python
# Использует новые поля для расчета важности
importance_score = calculate_importance({
    "novelty": ai_extracted.event_types in rare_events,
    "burst": frequency_in_time_window,
    "credibility": source_trust_level,
    "breadth": len(companies),
    "price_impact": market_reaction
})
```

## Пример работы обновленного NER

### Входная новость:
```
"ЦБ РФ повысил ключевую ставку до 16%. Акции банков упали: Сбербанк -5%, ВТБ -8%. 
Аналитики ожидают замедления экономического роста."
```

### Вывод нового NER:
```python
{
    "companies": [
        {"name": "Сбербанк", "ticker": "SBER", "sector": "финансы"},
        {"name": "ВТБ", "ticker": "VTBR", "sector": "финансы"}
    ],
    "financial_metrics": [
        {"metric_type": "процент_изменения", "value": "-5%", "company": "Сбербанк"},
        {"metric_type": "процент_изменения", "value": "-8%", "company": "ВТБ"}
    ],
    "event_types": ["rate_hike"],
    "sector": "финансы",
    "country": "Россия",
    "is_anchor_event": true,           # Якорное событие - влияет на другие
    "requires_market_data": true,       # Требует анализ рыночных данных
    "urgency_level": "high",           # Высокий приоритет
    "confidence_score": 0.95
}
```

### Результат для CEG системы:

1. **EventExtractor** создает событие типа "rate_hike"
2. **EventPredictionEngine** предсказывает события финансового типа
3. **ImpactCalculator** анализирует влияние на банки
4. **ImportanceCalculator** присваивает высокую важность
5. **Граф** связывает событие с банками и предсказаниями

## Техническая реализация

### Prompt caching:
- Кэшируется глоссарий (~1024 токена)
- Экономия до 90% на входных токенах
- Стоимость: ~$0.003/новость

### Асинхронная обработка:
```python
# Обрабатывает все новости параллельно
results = await extractor.extract_entities_batch_async(news_list)
```

### Fallback система:
```python
try:
    entities = await extractor.extract_entities_async(text)
except Exception:
    entities = ExtractedEntities()  # Пустая структура
```

## Статистика и мониторинг

```python
stats = extractor.get_stats_summary()
print(f"Cache hit rate: {stats['cache_hit_rate_percent']}%")
print(f"Token savings: {stats['token_savings_percent']}%")
print(f"Total cost: ${stats['total_cost']:.4f}")
```

## Мониторинг работы системы CEG

Новая система предоставляет детальную статистику:

- **Извлечено событий**: количество типов событий
- **Якорные события**: процент важных событий
- **Требующие анализ**: процент с requires_market_data=true
- **По срочности**: распределение low/normal/high/critical
- **По секторам**: эффективность классификации

---

Система готова к полноценной работе CEG с расширенными возможностями извлечения событий!
