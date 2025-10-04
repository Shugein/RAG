# CEG + CMNLN Implementation

## Обзор

Реализация **Causal Event Graph (CEG)** + **CMNLN** (Causal Mining of News & Links Networks) для анализа причинно-следственных связей в финансовых новостях.

## Архитектура

### Компоненты

1. **Event Extractor** ([src/services/events/event_extractor.py](src/services/events/event_extractor.py))
   - Извлечение событий из новостей на основе AI-extracted сущностей
   - Использует причинно-следственные маркеры (из ТЗ раздел 11)
   - Определяет якорные события (AnchorEvent)
   - Типы событий: sanctions, rate_hike, rate_cut, earnings, m&a, default, и др.

2. **CMNLN Engine** ([src/services/events/cmnln_engine.py](src/services/events/cmnln_engine.py))
   - Определение причинности между событиями
   - Domain Priors (причинно-следственные правила из ТЗ раздел 9)
   - Анализ текстовых маркеров причинности
   - Расчет уверенности: `conf_total = W1*conf_prior + W2*conf_text + W3*conf_market`
   - Построение причинных цепочек (BFS, max_depth=3)
   - Поиск Evidence Events

3. **MOEX Price Service** ([src/services/moex/moex_prices.py](src/services/moex/moex_prices.py))
   - Получение цен с MOEX ISS API
   - Event Study Analysis:
     - AR (Abnormal Return)
     - CAR (Cumulative Abnormal Return)
     - Volume Spike detection
   - Интеграция с причинностью (conf_market)

4. **Graph Models** ([src/graph_models.py](src/graph_models.py))
   - Neo4j узлы: EventNode, AnchorEvent
   - Связи: PRECEDES, CAUSES, IMPACTS, ALIGNS_TO, EVIDENCE_OF
   - GraphService с методами для CEG:
     - `create_event_ceg()` - создание события в графе
     - `link_events_causes()` - создание причинной связи
     - `find_causal_chain()` - поиск причинных цепочек
     - `find_anchor_events()` - поиск якорных событий

5. **REST API** ([src/api/endpoints/ceg.py](src/api/endpoints/ceg.py))
   - `GET /ceg/events` - список событий с фильтрами
   - `GET /ceg/events/{id}` - событие по ID
   - `GET /ceg/events/{id}/causal-context` - причинный контекст
   - `GET /ceg/events/{id}/causal-chains` - причинные цепочки
   - `GET /ceg/events/{id}/similar` - похожие события
   - `GET /ceg/anchor-events` - якорные события
   - `GET /ceg/stats` - статистика CEG

## База данных

### PostgreSQL

**Таблица `events`** (создана миграцией [migrations/versions/add_events_table.py](migrations/versions/add_events_table.py)):

```sql
CREATE TABLE events (
    id UUID PRIMARY KEY,
    news_id UUID NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,  -- sanctions, rate_hike, earnings, etc.
    title TEXT NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    attrs JSONB DEFAULT '{}',  -- {companies, tickers, people, markets, financial_metrics}
    is_anchor BOOLEAN DEFAULT FALSE,
    confidence FLOAT DEFAULT 0.8,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_events_event_type ON events(event_type);
CREATE INDEX ix_events_is_anchor ON events(is_anchor);
CREATE INDEX ix_events_ts ON events(ts);
```

### Neo4j

**Узлы:**

- `EventNode` - события из новостей
- `Instrument` - финансовые инструменты (акции, облигации)
- `Company` - компании
- `CausalChain` - причинные цепочки

**Связи:**

- `PRECEDES` - временная последовательность (event1 → event2)
- `CAUSES` - причинная связь с атрибутами:
  - `kind`: HYPOTHESIS | RETRO | CONFIRMED
  - `sign`: + | - | ±
  - `expected_lag`: 0-1d, 1h-1d, 1-4w
  - `conf_text`, `conf_prior`, `conf_market`, `conf_total`
  - `evidence_set`: IDs Evidence Events
- `IMPACTS` - влияние на инструмент:
  - `price_impact`: AR (abnormal return)
  - `volume_impact`: объем спайк
  - `sentiment`: -1 to 1
- `ALIGNS_TO` - схожесть с якорным событием
- `EVIDENCE_OF` - связь с причинной цепочкой

## Domain Priors

Таблица причинно-следственных правил (из ТЗ раздел 9):

| Cause Type | Effect Type | Sign | Expected Lag | Conf Prior | Описание |
|-----------|-------------|------|--------------|-----------|----------|
| sanctions | market_drop | - | 0-1d | 0.75 | Санкции → падение рынка |
| rate_hike | rub_appreciation | + | 1h-1d | 0.65 | Повышение ставки → укрепление рубля |
| rate_hike | bank_stock_up | + | 0-3d | 0.60 | Повышение ставки → рост банковских акций |
| earnings_beat | stock_rally | + | 0-1d | 0.70 | Превышение ожиданий → рост акций |
| earnings_miss | stock_drop | - | 0-1d | 0.75 | Неоправданные ожидания → падение |
| m&a | target_stock_up | + | 0-1d | 0.80 | M&A → рост акций цели |
| default | bond_crash | - | 0-1h | 0.90 | Дефолт → обвал облигаций |
| ... | ... | ... | ... | ... | (см. полную таблицу в cmnln_engine.py) |

## Текстовые маркеры причинности

Русские:
- "из-за", "в результате", "вследствие" (0.8)
- "привело к", "вызвало", "стало причиной" (0.9)
- "на фоне" (0.6), "после" (0.5)

Английские:
- "due to", "because of", "as a result of" (0.8)
- "caused by", "led to", "resulted in" (0.8-0.9)

## Запуск

### 1. Миграция БД

```bash
# Запустить миграцию для создания таблицы events
alembic upgrade head
```

### 2. Запуск демо-пайплайна

```bash
# Демо-пайплайн: извлечение событий → CMNLN → Event Study → Neo4j
python demo_ceg_pipeline.py
```

**Пайплайн выполняет:**
1. Загрузка последних новостей из PostgreSQL
2. AI extraction (GPT-5 или Qwen3-4B локально)
3. Event extraction с определением типа и якорных событий
4. CMNLN - определение причинности между событиями
5. Event Study - анализ влияния на цены MOEX
6. Построение CEG в Neo4j

### 3. Запуск API

```bash
# Запустить FastAPI с CEG endpoints
uvicorn src.api.main:app --reload --port 8000
```

**API доступен:**
- Swagger UI: http://localhost:8000/docs
- CEG endpoints: http://localhost:8000/ceg/*

### 4. Визуализация графа

Откройте Neo4j Browser: http://localhost:7474

**Запросы Cypher:**

```cypher
// Все события и причинные связи
MATCH (e:EventNode)-[r:CAUSES]->(e2:EventNode)
RETURN *

// Якорные события
MATCH (e:EventNode)
WHERE e.is_anchor = true
RETURN e
ORDER BY e.ts DESC

// Причинные цепочки от санкций
MATCH path = (e:EventNode {type: "sanctions"})-[:CAUSES*1..3]->(e2:EventNode)
RETURN path

// События с рыночным влиянием
MATCH (e:EventNode)-[r:IMPACTS]->(i:Instrument)
WHERE r.price_impact > 0.02
RETURN e, r, i

// Найти Evidence Events для связи
MATCH (e1:EventNode)-[c:CAUSES {kind: "CONFIRMED"}]->(e2:EventNode)
MATCH (ev:EventNode)
WHERE e1.ts < ev.ts < e2.ts
RETURN e1, c, e2, ev
```

## Примеры использования API

### Получить все события

```bash
curl "http://localhost:8000/ceg/events?limit=10"
```

### Получить якорные события типа "sanctions"

```bash
curl "http://localhost:8000/ceg/anchor-events?event_type=sanctions&limit=5"
```

### Получить причинные цепочки от события

```bash
curl "http://localhost:8000/ceg/events/{event_id}/causal-chains?max_depth=3"
```

### Получить похожие события

```bash
curl "http://localhost:8000/ceg/events/{event_id}/similar?min_similarity=0.7"
```

### Получить причинный контекст события

```bash
curl "http://localhost:8000/ceg/events/{event_id}/causal-context"
```

## Конфигурация

### Environment Variables

```bash
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# AI Extraction
USE_LOCAL_AI=false  # true для Qwen3-4B, false для GPT-5
API_KEY_2=your_openai_api_key  # Для GPT-5

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/newsdb
```

### Веса уверенности (CMNLN)

В `cmnln_engine.py`:

```python
W_PRIOR = 0.4    # Вес domain priors
W_TEXT = 0.3     # Вес текстовых маркеров
W_MARKET = 0.3   # Вес рыночной реакции
```

Порог уверенности: `conf_total >= 0.3`

## Расширение

### Добавление новых типов событий

1. Добавьте маркеры в `EventExtractor.CAUSAL_MARKERS_RU`
2. Добавьте domain prior в `CMLNEngine.DOMAIN_PRIORS`
3. Обновите приоритеты в `_detect_event_types()`

### Добавление новых источников данных

1. Создайте сервис в `src/services/`
2. Интегрируйте в `demo_ceg_pipeline.py`
3. Добавьте API endpoint в `src/api/endpoints/ceg.py`

## TODO

## Ссылки

- [RADAR_AI_CEG_CMNLN_TZ.pdf](RADAR_AI_CEG_CMNLN_TZ.pdf) - Техническое задание
- [CLAUDE.md](CLAUDE.md) - Документация проекта
- [src/graph_models.py](src/graph_models.py) - Графовые модели Neo4j
- [src/services/events/](src/services/events/) - Сервисы событий
