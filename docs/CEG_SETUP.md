# CEG (Causal Event Graph) Setup Guide

## ✅ Что сделано

### 1. **Ядро CEG движка**

Реализованы все основные компоненты:

- ✅ **EventExtractor** (`src/services/events/event_extractor.py`)
  - Извлечение событий из новостей по маркерам
  - Определение якорных событий
  - Поддержка 15+ типов событий (sanctions, earnings, rate_hike, m&a и др.)

- ✅ **CMLNEngine** (`src/services/events/cmnln_engine.py`)
  - Определение причинности через domain priors
  - 15 готовых правил причинно-следственных связей
  - Анализ текстовых маркеров причинности
  - Расчет уверенности (conf_prior, conf_text, conf_market)
  - Интеграция с EnhancedEvidenceEngine и CausalChainsEngine

- ✅ **ImportanceScoreCalculator** (`src/services/events/importance_calculator.py`)
  - Многокомпонентная оценка важности событий:
    - **Novelty**: новизна события (25%)
    - **Burst**: частота упоминаний (20%)
    - **Credibility**: надежность источника (25%)
    - **Breadth**: широта охвата (15%)
    - **Price Impact**: влияние на рынки (15%)
  - ✅ **ИСПРАВЛЕНО**: заменены raw SQL на SQLAlchemy ORM запросы

- ✅ **WatchersSystem** (`src/services/events/watchers.py`)
  - Трехуровневая система мониторинга (L0/L1/L2)
  - Автоматическое срабатывание по правилам
  - Генерация уведомлений

- ✅ **EventPredictionEngine** (`src/services/events/event_prediction.py`)
  - Генерация прогнозов для L2 watcher'ов
  - Отслеживание выполнения предсказаний
  - Статистика точности

- ✅ **CEGRealtimeService** (`src/services/events/ceg_realtime_service.py`)
  - Real-time обработка новостей
  - Построение CEG в Neo4j
  - Ретроспективный анализ
  - Интеграция всех компонентов

### 2. **База данных**

- ✅ **Модели** (`src/core/models.py`)
  - `Event` - события с атрибутами
  - `EventImportance` - оценки важности
  - `TriggeredWatch` - сработавшие мониторы
  - `EventPrediction` - прогнозы событий

- ✅ **Миграция** (`migrations/versions/add_ceg_tables.py`)
  - Создание всех таблиц CEG
  - Индексы для быстрого поиска
  - Foreign keys и каскадные удаления

### 3. **API**

- ✅ **REST API** (`src/api/endpoints/ceg.py`)
  - `GET /ceg/events` - список событий
  - `GET /ceg/events/{id}` - детали события
  - `GET /ceg/events/{id}/causal-context` - причинный контекст
  - `GET /ceg/events/{id}/causal-chains` - причинные цепочки
  - `GET /ceg/events/{id}/similar` - похожие события

### 4. **Тесты и демо**

- ✅ **test_ceg_simple.py** - упрощенный тест без БД
- ✅ **demo_ceg_pipeline.py** - полный пайплайн с БД
- ✅ **demo_enhanced_ceg.py** - расширенная версия

---

## 🚀 Как запустить

### Шаг 1: Запустить инфраструктуру

```bash
# Запустить только Neo4j (БД - SQLite, не требует Docker)
docker compose up -d neo4j

# Опционально: Redis и RabbitMQ для продакшена
# docker compose up -d redis rabbitmq
```

### Шаг 2: Создать SQLite БД с CEG таблицами

**ВАЖНО:** Миграция создана для PostgreSQL и использует JSONB. Для SQLite нужна адаптация.

**Вариант 1: Использовать готовый SQLite (если есть)**
```bash
# Проверить, есть ли уже БД
ls newsdb.sqlite

# Если есть, пропустить этот шаг
```

**Вариант 2: Создать CEG таблицы вручную**
```python
# scripts/create_ceg_tables_sqlite.py
import sqlite3

conn = sqlite3.connect('newsdb.sqlite')
cursor = conn.cursor()

# Events table
cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    news_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    ts TIMESTAMP NOT NULL,
    attrs TEXT,  -- JSON as TEXT in SQLite
    is_anchor INTEGER DEFAULT 0,
    confidence REAL DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
);
""")

# Event Importance table
cursor.execute("""
CREATE TABLE IF NOT EXISTS event_importance (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    importance_score REAL NOT NULL,
    novelty REAL NOT NULL,
    burst REAL NOT NULL,
    credibility REAL NOT NULL,
    breadth REAL NOT NULL,
    price_impact REAL NOT NULL,
    components_details TEXT,  -- JSON as TEXT
    calculation_timestamp TIMESTAMP NOT NULL,
    weights_version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);
""")

# Triggered Watches table
cursor.execute("""
CREATE TABLE IF NOT EXISTS triggered_watches (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    watch_level TEXT NOT NULL,
    event_id TEXT NOT NULL,
    trigger_time TIMESTAMP NOT NULL,
    auto_expire_at TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'triggered',
    notifications_sent INTEGER DEFAULT 0,
    context TEXT,  -- JSON as TEXT
    alerts TEXT,   -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);
""")

# Event Predictions table
cursor.execute("""
CREATE TABLE IF NOT EXISTS event_predictions (
    id TEXT PRIMARY KEY,
    watch_id TEXT NOT NULL,
    base_event_id TEXT NOT NULL,
    predicted_event_type TEXT NOT NULL,
    prediction_probability REAL NOT NULL,
    prediction_window_days INTEGER NOT NULL,
    target_date_estimate TIMESTAMP NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    fulfilled_at TIMESTAMP,
    actual_event_id TEXT,
    prediction_context TEXT,  -- JSON as TEXT
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (watch_id) REFERENCES triggered_watches(id) ON DELETE CASCADE,
    FOREIGN KEY (base_event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (actual_event_id) REFERENCES events(id) ON DELETE SET NULL
);
""")

# Create indexes
cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_news ON events(news_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_is_anchor ON events(is_anchor);")

conn.commit()
conn.close()
print("✓ CEG tables created in SQLite")
```

Запустить:
```bash
cd Parser
python scripts/create_ceg_tables_sqlite.py
```

### Шаг 3: Создать таблицы CEG

Уже создано в предыдущем шаге! Проверить:
```bash
sqlite3 newsdb.sqlite "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%event%';"
```

Должно вывести:
```
events
event_importance
event_predictions
```

### Шаг 4: Проверить setup (без БД)

```bash
cd Parser
python test_ceg_simple.py
```

**Ожидаемый результат:**
```
✅ ВСЕ БАЗОВЫЕ ТЕСТЫ ПРОЙДЕНЫ
```

### Шаг 4: Запустить полный тест (с БД)

```bash
cd Parser
python demo_ceg_pipeline.py
```

Этот скрипт:
1. Загружает новости из PostgreSQL
2. Извлекает события
3. Определяет причинность
4. Анализирует рыночное влияние
5. Строит граф в Neo4j

### Шаг 5: Запустить Neo4j и запустить полный тест

**ВАЖНО:** Для полного теста нужен Neo4j. Запустить:

```bash
# Если Neo4j не запущен
docker compose up -d neo4j

# Проверить статус
docker ps | grep neo4j
```

Запустить полный тест:
```bash
cd Parser
python demo_ceg_pipeline.py
```

**Примечание:** Если у тебя нет новостей в БД, сначала запусти парсер:
```bash
python scripts/start_telegram_parser.py
```

### Шаг 6: Проверить граф в Neo4j

Откройте Neo4j Browser: http://localhost:7474

```cypher
# Показать все события
MATCH (e:EventNode) RETURN e LIMIT 25

# Показать причинные связи
MATCH (e1:EventNode)-[r:CAUSES]->(e2:EventNode)
RETURN e1, r, e2

# Показать события с высокой важностью
MATCH (e:EventNode)
WHERE e.importance_score > 0.7
RETURN e.title, e.importance_score
ORDER BY e.importance_score DESC
```

---

## 📊 Интеграция с основным пайплайном

### Вариант 1: Автоматическая обработка в enricher

Добавьте CEG обработку в enricher service:

```python
# src/services/enricher/enrichment_service.py

from Parser.src.services.events.ceg_realtime_service import CEGRealtimeService
from Parser.src.graph_models import GraphService
from Parser.src.core.config import settings

# В классе EnrichmentService
async def enrich_news(self, news: News):
    # ... существующая обработка ...

    # Извлекаем AI entities
    ai_extracted = await self.ner_extractor.extract(news.text_plain)

    # Обрабатываем CEG
    if settings.ENABLE_CEG:
        graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        ceg_service = CEGRealtimeService(
            session=self.session,
            graph_service=graph
        )

        result = await ceg_service.process_news(news, ai_extracted)

        logger.info(
            f"CEG processed news {news.id}: "
            f"{len(result['events'])} events, "
            f"{len(result['causal_links'])} links"
        )

        await graph.close()
```

### Вариант 2: Отдельный CEG worker

Создайте отдельный воркер для CEG обработки:

```python
# scripts/start_ceg_worker.py

import asyncio
from Parser.src.core.database import init_db, get_db_session
from Parser.src.services.events.ceg_realtime_service import CEGRealtimeService
from Parser.src.graph_models import GraphService
from Parser.src.core.config import settings
from Parser.src.core.models import News
from sqlalchemy import select

async def main():
    await init_db()

    graph = GraphService(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )

    async with get_db_session() as session:
        ceg = CEGRealtimeService(
            session=session,
            graph_service=graph,
            enable_watchers=True,
            enable_predictions=True
        )

        # Обработать последние новости
        stmt = select(News).order_by(News.published_at.desc()).limit(100)
        result = await session.execute(stmt)
        news_list = result.scalars().all()

        for news in news_list:
            # Загрузить AI entities из БД или пересоздать
            ai_extracted = ...

            await ceg.process_news(news, ai_extracted)

        # Показать статистику
        stats = ceg.get_stats()
        print(f"Processed: {stats}")

    await graph.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Вариант 3: API endpoint

Добавьте endpoint для ручного запуска CEG обработки:

```python
# src/api/endpoints/ceg.py

@router.post("/process-news/{news_id}")
async def process_news_ceg(
    news_id: UUID,
    session: AsyncSession = Depends(get_session),
    graph: GraphService = Depends(get_graph_service)
):
    """Обработать новость через CEG"""
    # Загрузить новость
    stmt = select(News).where(News.id == news_id)
    result = await session.execute(stmt)
    news = result.scalar_one_or_none()

    if not news:
        raise HTTPException(404, "News not found")

    # Обработать
    ceg = CEGRealtimeService(session, graph)
    ai_extracted = ...  # Загрузить из БД

    result = await ceg.process_news(news, ai_extracted)

    return {
        "news_id": str(news_id),
        "events_created": len(result['events']),
        "causal_links": len(result['causal_links']),
        "impacts": len(result['impacts'])
    }
```

---

## 🔧 Конфигурация

Добавьте в `.env`:

```bash
# CEG Configuration
ENABLE_CEG=true
ENABLE_WATCHERS=true
ENABLE_PREDICTIONS=true

# Neo4j (уже есть)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

# Importance weights (опционально)
CEG_WEIGHT_NOVELTY=0.25
CEG_WEIGHT_BURST=0.20
CEG_WEIGHT_CREDIBILITY=0.25
CEG_WEIGHT_BREADTH=0.15
CEG_WEIGHT_PRICE_IMPACT=0.15
```

---

## 📈 Мониторинг и статистика

### Получить статистику CEG

```python
# Через API
GET /ceg/stats

# Через код
stats = ceg_service.get_stats()
# {
#   "news_processed": 150,
#   "events_created": 320,
#   "causal_links_created": 85,
#   "impacts_calculated": 45,
#   "importance_calculated": 320,
#   "watchers_triggered": 12,
#   "predictions_generated": 8,
#   "predictions_fulfilled": 3
# }
```

### Мониторинг watcher'ов

```python
watcher_stats = ceg_service.get_watcher_statistics()
# {
#   "total_active_watches": 25,
#   "triggered_l0": 180,
#   "triggered_l1": 45,
#   "triggered_l2": 12
# }
```

### Проверить предсказания

```python
await ceg_service.check_and_update_predictions()
# {
#   "fulfilled_count": 3,
#   "accuracy_stats": {
#     "overall_accuracy": 0.75
#   }
# }
```

---

## 🐛 Troubleshooting

### Проблема: Миграции не применяются

**Решение:** Используйте ручную миграцию через SQL:

```bash
# Подключитесь к PostgreSQL
psql -U newsuser -d newsdb

# Выполните SQL из add_ceg_tables.py вручную
\i migrations/versions/add_ceg_tables.py
```

### Проблема: Neo4j недоступен

**Решение:** Проверьте статус:

```bash
docker logs news-neo4j
docker restart news-neo4j
```

### Проблема: Ошибки в importance_calculator

**Решение:** Все SQL запросы заменены на SQLAlchemy ORM, но если возникают проблемы:

```python
# Проверьте, что импорты на месте:
from sqlalchemy import select, func as sql_func, distinct, cast
from sqlalchemy.dialects.postgresql import JSONB
from Parser.src.core.models import News, Event, Source
```

---

## 📚 Дополнительные ресурсы

- **Полная документация:** `Parser/CEG_README.md`
- **Архитектура:** `Parser/CEG_IMPLEMENTATION_SUMMARY.md`
- **Real-time pipeline:** `Parser/CEG_REALTIME_PIPELINE.md`
- **Демо скрипты:** `Parser/demo_*.py`

---

## ✨ Следующие шаги

1. ✅ Запустить тесты (`test_ceg_simple.py`)
2. ✅ Применить миграции
3. ⏳ Интегрировать с enricher service
4. ⏳ Настроить автоматическую обработку новостей
5. ⏳ Добавить мониторинг и алерты для L2 watcher'ов
6. ⏳ Оптимизировать performance для большого объема новостей

**CEG движок готов к использованию!** 🚀
