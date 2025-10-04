# 🚀 РАСШИМННЫЕ ФУНКЦИИ НОВОЙ NER СИСТЕМЫ

## Обзор изменений

Обновленная NER система теперь поддерживает:

### ✅ НОВЫЕ ФИЛЬТРЫ И КАТЕГОРИИ

#### 🔍 Фильтр рекламы
```python
"is_advertisement": bool  # true если рекламный контент
```

**Маркеры рекламы:**
- "реклама", "промо", "акция", "скидка"
- "купи", "заказ", "инвестиционн", "консультант"
- "подписывайт", "телеграм", "@", "vk.com"

#### 📂 Типы контента
```python
"content_types": List[str]  # ["financial", "political", "legal", "natural_disaster"]
```

**Категории:**
- **financial**: финансы, банки, акции, валюта, курсы
- **political**: политика, правительство, президент, власть
- **legal**: законы, права, суд, иски, вердикты
- **natural_disaster**: стихийные бедствия, пожары, наводнения, землетрясения

### ✅ ОБНОВЛЕННЫЕ МОДЕЛИ ДАННЫХ

```python
class ExtractedEntities(BaseModel):
    # Базовые поля
    publication_date: Optional[str]
    people: List[Person]
    companies: List[Company]
    markets: List[Market]
    financial_metrics: List[FinancialMetric]
    
    # CEG поля
    sector: Optional[str]
    country: Optional[str]
    event_types: List[str]
    event: Optional[str]
    
    # 🆕 НОВЫЕ ФИЛЬТРЫ И КАТЕГОРИИ
    is_advertisement: bool = False                    # Фильтр рекламы
    content_types: List[str] = []                     # Типы контента
    
    # Метаданные (БЕЗ якорности!)
    confidence_score: float = 0.8
    language: str = "ru"
    requires_market_data: bool = False               # БЕЗ is_anchor_event
    urgency_level: str = "normal"
```

### ✅ BATCH ОБРАБОТКА JSON

#### Массивный input:
```json
[
  {"text": "ЦБ РФ повысил ставку до 16%", "source": "economy"},
  {"text": "Купите акции! Подписывайтесь!", "source": "ad"},
  {"text": "Землетрясение в Японии", "source": "disaster"}
]
```

#### Структурированный output:
```json
{
  "news_items": [
    {
      "publication_date": null,
      "event_types": ["rate_hike"],
      "is_advertisement": false,
      "content_types": ["financial"],
      "confidence_score": 0.95,
      "requires_market_data": true,
      "urgency_level": "high"
    },
    {
      "event_types": [],
      "is_advertisement": true,
      "content_types": ["advertisement"],
      "confidence_score": 0.9,
      "urgency_level": "low"
    }
  ],
  "total_processed": 3,
  "batch_id": null
}
```

#### Программный interface:
```python
# Batch обработка через enrichment_service
enrichment_service = EnrichmentService(session)
batch_result = await enrichment_service.enrich_news_batch(
    news_list=["новость1", "новость2", "новость3"],
    news_metadata=[{"priority": "high"}, {"priority": "normal"}]
)

# Прямой batch через NER
ner = CachedFinanceNERExtractor(api_key="...")
batch_result = ner.extract_entities_json_batch(news_list, metadata)
```

### ✅ УБРАННАЯ ПРОВЕРКА ЯКОРНОСТИ

**Старый подход:**
```python
is_anchor_event: bool = True  # Модель определяла якорность
```

**Новый подход:**
```python
# is_anchor_event УБРАНО из NER
# Якорность будет вычисляться отдельно через:
# - CEG engine
# - Important calculator
# - Специальные алгоритмы
```

### ✅ РАСШИРЕННЫЕ ПРОМПТЫ

#### Система промпт для одиночной обработки:
```
Ты эксперт анализа финансовых новостей. Извлеки JSON с полями:
  "is_advertisement": "true если реклама",
  "content_types": ["financial", "political", "legal", "natural_disaster"], 
  "requires_market_data": "true если нужны рыночные данные",
  ПРАВИЛА:
  1. is_advertisement = true если содержит рекламу
  2. content_types: financial/political/legal/natural_disaster
  3. Якорность НЕ определяй - будет вычисляться отдельно
```

#### Batch промпт:
```
Обработай массив новостей и верни в формате:
  "news_items": [массив с теми же полями],
  "total_processed": "число",
Максимум 50 новостей за раз.
```

### ✅ УЛУЧШЕННАЯ СОВМЕСТИМОСТЬ

```python
class CompatibilityWrapper:
    async def extract_entities(self, text: str, metadata: Dict[str, Any] = None):
        """Совместимость с Natasha форматом"""
        
        # Новые метаданные попадают в 'meta'
        result['meta']['is_advertisement'] = extracted.is_advertisement
        result['meta']['content_types'] = extracted.content_types
        result['meta']['requires_market_data'] = extracted.requires_market_data
        result['meta']['urgency_level'] = extracted.urgency_level
        
        # Убрано is_anchor_event - будет вычисляться отдельно
```

### ✅ ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

```python
# Тест фильтров
news_samples = [
    "ЦБ РФ повысил ставку до 16%",                                    # financial
    "Президент подписал новый закон о налогах",                      # political, legal  
    "Землетрясение в Японии нарушило поставки",                      # natural_disaster
    "Купите акции! Скидка 50%! Подписывайтесь на канал!",           # advertisement
    "Сбербанк показал рост прибыли на 30%"                           # financial, earnings
]

batch_result = ner.extract_entities_json_batch(news_samples)

for i, item in enumerate(batch_result['news_items']):
    print(f"Новость {i+1}:")
    print(f"  Реклама: {'ДА' if item.get('is_advertisement') else 'НЕТ'}")
    print(f"  Контент: {item.get('content_types', [])}")
    print(f"  События: {item.get('event_types', [])}")
    print(f"  Срочность: {item.get('urgency_level')}")
    print(f"  Рынок данные: {'ДА' if item.get('requires_market_data') else 'НЕТ'}")
```

### ✅ ПРЕИМУЩЕСТВА

1. **🚫 Фильтрация рекламы**: Автоматическое исключение рекламного контента
2. **📂 Классификация контента**: Разделение на финансовые/политические/юридические/стихийные бедствия
3. **📊 Batch обработка**: Эффективная обработка массивов новостей
4. **⚡ Производительность**: Prompt caching, parallel processing
5. **🎯 Точность**: Улучшенные промпты для финансовых новостей
6. **🔗 Совместимость**: Легкая замена существующей системы

### ✅ МИГРАЦИЯ

Для перехода на новую систему:

1. **Обновить NER вызовы:**
   ```python
   # Старый способ (Natasha)
   natasha_result = natasha.extract_entities(text)
   
   # Новый способ (AI)
   ai_result = await ai_ner.extract_entities_async(text)
   
   # Batch способ
   batch_result = ai_ner.extract_entities_json_batch(news_list)
   ```

2. **Обновить обработку результатов:**
   ```python
   # Новые поля доступны через:
   enrichment["is_advertisement"]
   enrichment["content_types"]
   enrichment["event_types"]
   enrichment["ceg_flags"]["requires_market_data"]  # БЕЗ is_anchor_event
   ```

3. **Настроить фильтры:**
   ```python
   # Фильтр рекламы
   if enrichment.get("is_advertisement"):
       continue  # Пропускаем рекламу
   
   # Фильтр по типам контента
   if not any(content_type in enrichment.get("content_types", []) 
              for content_type in ["financial", "political"]):
       continue  # Только финансовые/политические
   ```

Система готова к продуктивному использованию! 🎉
