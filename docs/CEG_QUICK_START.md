# CEG Quick Start (SQLite + Neo4j)

## ⚡ Быстрый старт

### 1. Создать CEG таблицы в SQLite

```bash
cd Parser
python scripts/create_ceg_tables_sqlite.py
```

**Результат:**
```
✅ CEG таблицы успешно созданы в newsdb.sqlite
  ✓ events
  ✓ event_importance
  ✓ triggered_watches
  ✓ event_predictions
```

### 2. Проверить работу (без БД)

```bash
python test_ceg_simple.py
```

**Результат:**
```
✅ ВСЕ БАЗОВЫЕ ТЕСТЫ ПРОЙДЕНЫ
```

### 3. Запустить Neo4j

```bash
docker compose up -d neo4j
```

Проверить: http://localhost:7474 (neo4j / password123)

### 4. Запустить полный тест (если есть новости в БД)

```bash
python demo_ceg_pipeline.py
```

---

## 🗄️ База данных

- **SQLite** (`newsdb.sqlite`) - основные данные (новости, события, важность)
- **Neo4j** (bolt://localhost:7687) - граф причинно-следственных связей

**Преимущества:**
- ✅ Не нужен PostgreSQL
- ✅ Быстрый старт
- ✅ Подходит для разработки
- ✅ Легко бэкапить (просто скопировать .sqlite файл)

**Ограничения SQLite:**
- ⚠️ JSONB запросы работают через LIKE (менее эффективно)
- ⚠️ Нет конкурентных записей (одна транзакция за раз)
- ⚠️ Для продакшена рекомендуется PostgreSQL

---

## 🔧 Конфигурация

`.env` файл:
```bash
# SQLite (локальная разработка)
DATABASE_URL=sqlite+aiosqlite:///newsdb.sqlite

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123

# CEG настройки
ENABLE_CEG=true
ENABLE_WATCHERS=true
ENABLE_PREDICTIONS=true
```

---

## 🧪 Проверка таблиц

```bash
# Через sqlite3
sqlite3 newsdb.sqlite "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%event%';"

# Или через Python
python -c "import sqlite3; conn = sqlite3.connect('newsdb.sqlite'); print('\n'.join([t[0] for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%event%'\").fetchall()]))"
```

**Ожидаемый вывод:**
```
events
event_importance
event_predictions
triggered_watches
```

---

## 📊 Использование

### Через API

```python
import asyncio
from Parser.src.services.events.ceg_realtime_service import CEGRealtimeService
from Parser.src.core.database import get_db_session
from Parser.src.graph_models import GraphService
from Parser.src.core.config import settings

async def process_news():
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

        # Обработать новость
        news = ...  # Загрузить из БД
        ai_extracted = ...  # AI extraction

        result = await ceg.process_news(news, ai_extracted)

        print(f"События: {len(result['events'])}")
        print(f"Причинные связи: {len(result['causal_links'])}")
        print(f"Влияния на рынки: {len(result['impacts'])}")

    await graph.close()

asyncio.run(process_news())
```

### REST API

```bash
# Запустить API
python scripts/start_api.py

# Получить события
curl http://localhost:8000/ceg/events

# Получить причинный контекст события
curl http://localhost:8000/ceg/events/{event_id}/causal-context

# Получить причинные цепочки
curl http://localhost:8000/ceg/events/{event_id}/causal-chains?max_depth=3
```

---

## 🚀 Интеграция с пайплайном

### Вариант 1: В enricher

Добавить в `src/services/enricher/enrichment_service.py`:

```python
from Parser.src.services.events.ceg_realtime_service import CEGRealtimeService

# После обогащения новости
if settings.ENABLE_CEG:
    result = await ceg_service.process_news(news, ai_extracted)
```

### Вариант 2: Отдельный воркер

```python
# scripts/ceg_worker.py
# Обрабатывает необработанные новости в фоне
```

---

## 📈 Мониторинг

```python
# Получить статистику
stats = await ceg_service.get_stats()
# {
#   "news_processed": 150,
#   "events_created": 320,
#   "causal_links_created": 85,
#   ...
# }

# Проверить watcher'ы
watcher_stats = await ceg_service.get_watcher_statistics()

# Проверить предсказания
await ceg_service.check_and_update_predictions()
```

---

## 🐛 Troubleshooting

### Ошибка: `sqlite3.OperationalError: no such table: events`

**Решение:**
```bash
python scripts/create_ceg_tables_sqlite.py
```

### Ошибка: `Neo4j connection refused`

**Решение:**
```bash
docker compose up -d neo4j
docker logs news-neo4j  # Проверить логи
```

### Ошибка: `ImportError` в importance_calculator

**Решение:** Убедитесь, что удалены импорты PostgreSQL:
```python
# Удалить:
from sqlalchemy.dialects.postgresql import JSONB

# Использовать:
Event.attrs.like(f'%{ticker}%')  # Для SQLite
```

---

## 📚 Дополнительная документация

- **Полное руководство:** `CEG_SETUP.md`
- **Архитектура:** `CEG_IMPLEMENTATION_SUMMARY.md`
- **Компоненты:** `CEG_README.md`
- **Real-time pipeline:** `CEG_REALTIME_PIPELINE.md`

---

## ✨ Что дальше?

1. ✅ CEG таблицы созданы
2. ✅ Тесты пройдены
3. ⏳ Запустить Neo4j
4. ⏳ Обработать первые новости
5. ⏳ Интегрировать с enricher
6. ⏳ Настроить watcher'ы для алертов

**CEG движок готов к работе!** 🚀
