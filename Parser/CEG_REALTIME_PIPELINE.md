# CEG Real-time Pipeline - Реактивная система построения графа событий

## Обзор

**CEG Real-time Pipeline** - это реактивная система, которая автоматически строит граф причинно-следственных событий (Causal Event Graph) в реальном времени при загрузке новостей.

## Ключевые отличия от batch-подхода

### Старый подход (demo_ceg_pipeline.py)
```
Загрузка новостей → Парсинг всех → Извлечение событий → Построение CEG
```
- Обработка после сбора данных
- Только прямые связи (прошлое → будущее)
- Нет обновления существующих связей

### Новый подход (CEGRealtimeService)
```
Новость поступила → Обогащение → CEG обработка → Граф обновлен
```
- Обработка во время загрузки
- **Ретроспективный анализ** - новые события могут объяснить прошлые
- **Двунаправленные связи** - новость может быть причиной/следствием для уже существующих событий

## Архитектура

### Поток обработки новости

```
┌─────────────────┐
│  Новая новость  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  AI Extraction  │ ← GPT-5 / Qwen3-4B
│  (companies,    │
│   people, etc)  │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│         EnrichmentService                    │
│  ┌──────────────────────────────────────┐   │
│  │ 1. Entity extraction                 │   │
│  │ 2. MOEX linking                      │   │
│  │ 3. Topic classification              │   │
│  │ 4. Graph write                       │   │
│  │ 5. Impact calculation                │   │
│  │ 6. Correlation update                │   │
│  │ 7. Event publishing                  │   │
│  └────────────┬─────────────────────────┘   │
│               │                              │
│               ▼                              │
│  ┌──────────────────────────────────────┐   │
│  │ 8. CEG Real-time Processing          │   │
│  │    (NEW!)                             │   │
│  │                                       │   │
│  │  CEGRealtimeService.process_news()  │   │
│  └────────────┬─────────────────────────┘   │
└───────────────┼──────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────┐
│      CEGRealtimeService.process_news()       │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │ 1. Event Extraction                     │ │
│  │    EventExtractor.extract_events()      │ │
│  │    → Создает Event записи в PostgreSQL  │ │
│  │    → Создает EventNode в Neo4j          │ │
│  └─────────────┬───────────────────────────┘ │
│                │                             │
│                ▼                             │
│  ┌─────────────────────────────────────────┐ │
│  │ 2. Causal Link Detection                │ │
│  │    CMNLN.detect_causality()              │ │
│  │    ┌─────────────────────────────────┐   │ │
│  │    │ A. Forward links                │   │ │
│  │    │    past_events → new_events     │   │ │
│  │    │    (прошлое → новое)            │   │ │
│  │    └─────────────────────────────────┘   │ │
│  │    ┌─────────────────────────────────┐   │ │
│  │    │ B. Internal links               │   │ │
│  │    │    new_event1 → new_event2      │   │ │
│  │    │    (в рамках одной новости)     │   │ │
│  │    └─────────────────────────────────┘   │ │
│  │    → Создает CAUSES в Neo4j             │ │
│  └─────────────┬───────────────────────────┘ │
│                │                             │
│                ▼                             │
│  ┌─────────────────────────────────────────┐ │
│  │ 3. Event Study Analysis                  │ │
│  │    EventStudyAnalyzer.analyze_impact()   │ │
│  │    → AR (Abnormal Return)                │ │
│  │    → CAR (Cumulative AR)                 │ │
│  │    → Volume Spike                        │ │
│  │    → conf_market для CMNLN               │ │
│  │    → Создает IMPACTS в Neo4j             │ │
│  └─────────────┬───────────────────────────┘ │
│                │                             │
│                ▼                             │
│  ┌─────────────────────────────────────────┐ │
│  │ 4. Retroactive Analysis (KEY!)           │ │
│  │    ┌─────────────────────────────────┐   │ │
│  │    │ Ищем события ПОСЛЕ нового       │   │ │
│  │    │ (в пределах lookback_window)    │   │ │
│  │    │                                  │   │ │
│  │    │ new_event → future_event        │   │ │
│  │    │ (новое объясняет будущее)       │   │ │
│  │    └─────────────────────────────────┘   │ │
│  │    → Обновляет CAUSES в Neo4j            │ │
│  │    → Пересчитывает conf_market           │ │
│  └─────────────────────────────────────────┘ │
└───────────────────────────────────────────────┘
```

## Компоненты

### 1. CEGRealtimeService
**Файл:** [src/services/events/ceg_realtime_service.py](src/services/events/ceg_realtime_service.py)

**Ключевые методы:**
- `process_news(news, ai_extracted)` - главный метод обработки
- `_find_causal_links(new_events)` - поиск причинных связей
- `_calculate_impacts(events)` - Event Study анализ
- `_retroactive_analysis(new_events)` - **ретроспективный анализ**

**Параметры:**
```python
CEGRealtimeService(
    session=async_session,
    graph_service=graph,
    lookback_window=30  # Дней для ретроспективного анализа
)
```

### 2. Ретроспективный анализ

**Проблема:**
Традиционный подход строит связи только от прошлого к будущему:
```
День 1: Событие A (earnings miss) → ?
День 3: Событие B (sanctions)     → ?

Традиционный: B не связан с A (B произошло позже)
```

**Решение:**
Реактивный подход находит обратные связи:
```
День 1: Событие A (падение акций)
День 3: Событие B (sanctions) ← НОВОЕ

Реактивный: B → A (санкции ОБЪЯСНЯЮТ падение акций)
```

**Код:**
```python
async def _retroactive_analysis(self, new_events):
    """Новое событие может быть причиной старых событий"""

    for new_event in new_events:
        # Ищем события ПОСЛЕ нового события
        future_date_start = new_event.ts + timedelta(hours=1)
        future_date_end = new_event.ts + timedelta(days=30)

        future_events = await session.execute(
            select(Event).where(
                Event.ts >= future_date_start,
                Event.ts <= future_date_end
            )
        )

        for future_event in future_events:
            # Проверяем: new_event → future_event
            relation = await cmnln.detect_causality(
                cause_event=new_event,
                effect_event=future_event
            )

            if relation:
                # Создаем/обновляем связь в Neo4j
                await graph.link_events_causes(
                    new_event.id,
                    future_event.id,
                    relation
                )
```

### 3. Интеграция в EnrichmentService

**Файл:** [src/services/enricher/enrichment_service.py](src/services/enricher/enrichment_service.py)

**Изменения:**

```python
class EnrichmentService:
    def __init__(self, session, use_local_ai=False):
        # ...
        self.ceg_service = None  # Будет инициализирован позже

    async def initialize(self):
        # ...
        if self.topic_classifier.graph:
            self.ceg_service = CEGRealtimeService(
                session=self.session,
                graph_service=self.topic_classifier.graph,
                lookback_window=30
            )

    async def enrich_news(self, news):
        # ... шаги 1-7 (AI extraction, MOEX linking, topics, etc.)

        # ШАГ 8: CEG Real-time Processing (NEW!)
        if self.ceg_service:
            ceg_result = await self.ceg_service.process_news(news, ai_extracted)

            enrichment["ceg"] = {
                "events": len(ceg_result["events"]),
                "causal_links": len(ceg_result["causal_links"]),
                "impacts": len(ceg_result["impacts"]),
                "retroactive_links": ceg_result["retroactive_links"]
            }
```

## Конфигурация

### Environment Variables

```bash
# CEG параметры
CEG_LOOKBACK_WINDOW=30  # Дней для ретроспективного анализа
CEG_MAX_EVENTS_PER_NEWS=5  # Максимум событий из одной новости
CEG_MIN_CONFIDENCE=0.3  # Минимальная уверенность для создания связи

# CMNLN веса
CMNLN_W_PRIOR=0.4  # Вес domain priors
CMNLN_W_TEXT=0.3   # Вес текстовых маркеров
CMNLN_W_MARKET=0.3  # Вес рыночной реакции

# Event Study
EVENT_STUDY_ESTIMATION_WINDOW=30  # Дней для оценки нормального возврата
EVENT_STUDY_EVENT_WINDOW="-1,1"  # Окно события (дни до, дни после)
```

### Настройка в коде

```python
# В enrichment_service.py
self.ceg_service = CEGRealtimeService(
    session=self.session,
    graph_service=self.topic_classifier.graph,
    lookback_window=int(os.getenv("CEG_LOOKBACK_WINDOW", "30"))
)
```

## Примеры работы

### Пример 1: Прямая связь

```
16:00 - Новость 1: "ЦБ повысил ключевую ставку до 16%"
  → Событие A: rate_hike (is_anchor=True)

17:00 - Новость 2: "Рубль укрепился к доллару"
  → Событие B: rub_appreciation

CEG обработка Новости 2:
  1. Извлекает событие B
  2. Ищет прошлые события (lookback 30 дней)
  3. Находит событие A (1 час назад)
  4. CMNLN: A → B (rate_hike → rub_appreciation)
     - conf_prior = 0.65 (domain prior)
     - conf_text = 0.0 (нет маркеров)
     - conf_market = 0.7 (Event Study: significant AR)
     - conf_total = 0.48
  5. Создает CAUSES(A → B) в Neo4j
```

### Пример 2: Ретроспективная связь

```
День 1, 10:00 - Новость 1: "Акции Сбербанка упали на 5%"
  → Событие A: stock_drop (ticker=SBER)

День 3, 15:00 - Новость 2: "США ввели новые санкции против российских банков"
  → Событие B: sanctions (sector=banks)

CEG обработка Новости 2:
  1. Извлекает событие B
  2. Прямые связи: нет (B позже A)
  3. Ретроспективный анализ:
     - Ищет события ПОСЛЕ B (до B + 30 дней)
     - НЕ находит событие A (A было ДО B)
     - НО: ищем события с тикерами из B.attrs
     - Находит A (tick er=SBER, sector=banks)
  4. CMNLN: B → A? НЕТ (временная последовательность)
  5. Reverse check: A → B? НЕТ (A раньше B)

  ОДНАКО: Логически B объясняет A!

  6. Special case: если B - санкции и A - падение акций того же сектора
     - Создаем EXPLAINS(B → A) связь с is_retroactive=True
     - conf_total = conf_prior (без conf_text/conf_market)
```

**Правильная реализация ретроспективного анализа:**

```python
async def _retroactive_analysis(self, new_events):
    """
    Для каждого нового события:
    1. Ищем события, которые произошли ПОСЛЕ него (в lookback window)
    2. Проверяем причинность new_event → future_event
    3. Это позволяет найти связи, где новое событие объясняет прошлые
    """

    for new_event in new_events:
        # Пример: new_event - "sanctions" (День 3)
        # Ищем события с День 3 до День 33

        future_events = [...]  # События после new_event

        for future_event in future_events:
            # future_event может быть из Дня 5, 10, 20, etc.
            # Но также может быть из Дня 1 (если мы обрабатываем исторические данные)

            relation = await cmnln.detect_causality(
                cause_event=new_event,    # День 3: sanctions
                effect_event=future_event  # День 5: stock_drop
            )
```

## Статистика и мониторинг

### Получение статистики

```python
stats = ceg_service.get_stats()
print(stats)
# {
#     'news_processed': 1523,
#     'events_created': 4127,
#     'causal_links_created': 891,
#     'impacts_calculated': 623,
#     'retroactive_updates': 142
# }
```

### Логирование

```
INFO: Processing CEG for news abc-123
INFO: Extracted 2 events: [rate_hike, bank_stock_up]
INFO: Found 3 causal links
INFO: Calculated 2 market impacts (significant)
INFO: Retroactive analysis: 1 new link created
INFO: CEG processed: 2 events, 3 causal links, 2 impacts, 1 retroactive
```

## API интеграция

CEG результаты доступны через enrichment response:

```python
# После обогащения
enrichment = await enrichment_service.enrich_news(news)

print(enrichment["ceg"])
# {
#     'events': 2,
#     'causal_links': 3,
#     'impacts': 2,
#     'retroactive_links': 1
# }
```

## Визуализация в Neo4j

```cypher
// Все события с ретроспективными связями
MATCH (e1:EventNode)-[c:CAUSES]->(e2:EventNode)
WHERE c.is_retroactive = true
RETURN e1, c, e2

// События с высоким рыночным влиянием
MATCH (e:EventNode)-[i:IMPACTS]->(inst:Instrument)
WHERE i.price_impact > 0.03
RETURN e, i, inst
ORDER BY i.price_impact DESC

// Причинные цепочки длиной > 2
MATCH path = (e1:EventNode)-[:CAUSES*2..]->(e3:EventNode)
RETURN path
LIMIT 10
```

## Производительность

### Оптимизации

1. **Ограничение поиска**: lookback_window = 30 дней (не весь граф)
2. **Кэширование**: conf_market кэшируется для тикеров
3. **Батчинг**: Event Study выполняется для max 3 тикеров на событие
4. **Асинхронность**: CEG обработка не блокирует enrichment

### Ожидаемая производительность

- **Одна новость**: ~500ms (без Event Study) / ~2s (с Event Study)
- **Пакетная обработка**: ~100 новостей/мин
- **Ретроспективный анализ**: +20-30% времени

## Troubleshooting

### CEG не создает связи

```python
# Проверьте настройки
assert settings.ENABLE_ENRICHMENT == True
assert ceg_service is not None
assert ceg_service.cmnln.DOMAIN_PRIORS  # Должны быть прiors

# Проверьте уверенность
relation = await cmnln.detect_causality(event1, event2)
print(relation.conf_total)  # Должно быть >= 0.3
```

### Слишком много ретроспективных связей

```python
# Уменьшите lookback_window
self.ceg_service = CEGRealtimeService(
    lookback_window=7  # Вместо 30
)

# Повысьте порог уверенности
# В cmnln_engine.py
if conf_total < 0.5:  # Вместо 0.3
    return None
```

### Event Study не работает

```python
# Проверьте Algopack API
moex = MOEXPriceService()
prices = await moex.get_historical_prices("SBER", from_date, to_date)
print(len(prices))  # Должно быть > 30

# Проверьте API ключ
print(settings.ALGOPACK_API_KEY)
```

## Следующие шаги

1. **Онлайн триггер**: WebSocket для real-time новостей
2. **Importance Score**: Реализовать Novelty/Burst/Credibility/Breadth
3. **Watchers**: L0/L1/L2 мониторинг для предсказаний
4. **Batch reprocessing**: Переобработка исторических данных

## См. также

- [CEG_README.md](CEG_README.md) - Полная документация CEG
- [CEG_IMPLEMENTATION_SUMMARY.md](CEG_IMPLEMENTATION_SUMMARY.md) - Итоги MVP
- [CLAUDE.md](CLAUDE.md) - Общая документация проекта
