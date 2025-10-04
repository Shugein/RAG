# Telegram Parser с CEG + AI - Руководство

## Обзор

Новый улучшенный Telegram Parser с интегрированной **AI extraction** и **CEG (Causal Event Graph)** построением в реальном времени.

## Новые возможности

✅ **AI Extraction**
- Использует OpenAI GPT-5 или локальный Qwen3-4B
- Автоматическое извлечение компаний, людей, метрик, рынков
- Возвращает данные в JSON формате

✅ **CEG Real-time**
- Автоматическое построение графа событий при парсинге
- Причинно-следственный анализ (CMNLN)
- Ретроспективный анализ связей
- Event Study для рыночного влияния

✅ **Статистика**
- Подробная статистика по событиям
- Количество причинных связей
- Рыночные воздействия
- Ретроспективные обновления

## Запуск

### Вариант 1: Новый скрипт с CEG (Рекомендуется)

```bash
python scripts/start_telegram_parser_ceg.py
```

### Вариант 2: Старый скрипт (без CEG)

```bash
python scripts/start_telegram_parser.py
```

## Интерактивная настройка

При запуске вас спросят:

### 1. Выбор AI модели

```
🧠 Выберите AI модель для анализа:
1. 🌐 OpenAI GPT (API) - точнее, но требует API ключ
2. 💻 Qwen3-4B (локально) - быстрее, работает офлайн

Введите номер (1 или 2, по умолчанию 1):
```

**OpenAI GPT (опция 1):**
- Требует API ключ в `.env`: `API_KEY_2` или `OPENAI_API_KEY`
- Более точное извлечение сущностей
- Работает через интернет

**Local Qwen3-4B (опция 2):**
- Работает полностью офлайн
- Требует GPU (CUDA) или будет медленнее на CPU
- Модель: `unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit`

### 2. Выбор режима работы

```
📋 Выберите режим работы:
1. 📚 Историческая загрузка - загрузить и проанализировать новости за период
2. 🔄 Мониторинг в реальном времени - следить за новыми новостями

Введите номер режима (1 или 2, по умолчанию 1):
```

**Историческая загрузка (опция 1):**
```
За сколько дней загружать новости? (по умолчанию 7):
```
- Загружает новости за указанный период
- Строит CEG граф с нуля
- Завершается после обработки
- Идеально для начальной загрузки данных

**Real-time мониторинг (опция 2):**
- Непрерывно следит за новыми сообщениями
- Обновляет CEG граф в реальном времени
- Работает как демон
- Идеально для продакшн использования

## Примеры запуска

### Пример 1: Историческая загрузка с OpenAI GPT

```bash
$ python scripts/start_telegram_parser_ceg.py

🧠 Выберите AI модель для анализа:
1. 🌐 OpenAI GPT (API) - точнее, но требует API ключ
2. 💻 Qwen3-4B (локально) - быстрее, работает офлайн

Введите номер (1 или 2, по умолчанию 1): 1
✅ OpenAI API ключ найден: sk-proj-...

📋 Выберите режим работы:
1. 📚 Историческая загрузка - загрузить и проанализировать новости за период
2. 🔄 Мониторинг в реальном времени - следить за новыми новостями

Введите номер режима (1 или 2, по умолчанию 1): 1

📚 РЕЖИМ: Историческая загрузка с AI анализом
------------------------------------------------------------
За сколько дней загружать новости? (по умолчанию 7): 30

✅ Конфигурация:
   - Период: последние 30 дней
   - AI модель: OpenAI GPT
   - CEG анализ: включен
   - Ретроспективный анализ: включен

⏳ Запуск парсера...
```

### Пример 2: Real-time мониторинг с локальным Qwen

```bash
$ python scripts/start_telegram_parser_ceg.py

🧠 Выберите AI модель для анализа:
1. 🌐 OpenAI GPT (API) - точнее, но требует API ключ
2. 💻 Qwen3-4B (локально) - быстрее, работает офлайн

Введите номер (1 или 2, по умолчанию 1): 2
✅ Будет использован локальный Qwen3-4B

📋 Выберите режим работы:
1. 📚 Историческая загрузка - загрузить и проанализировать новости за период
2. 🔄 Мониторинг в реальном времени - следить за новыми новостями

Введите номер режима (1 или 2, по умолчанию 1): 2

🔄 РЕЖИМ: Мониторинг в реальном времени
------------------------------------------------------------
✅ Парсер будет следить за новыми новостями и анализировать их в реальном времени
   - AI модель: Local Qwen3-4B
   - CEG граф: обновляется автоматически
   - Ретроспективный анализ: включен

⏳ Запуск парсера...
```

## Вывод логов

### Инициализация

```
🚀 Initializing Telegram client...
🧠 Initializing AI Enrichment Service...
   ✓ Using OpenAI GPT for NER extraction
   ✓ CEG Real-time Service initialized
   ✓ Lookback window: 30 days
📡 Found 3 active Telegram sources
📚 Running in HISTORICAL LOADING mode (last 7 days)
   - Loading historical messages
   - Building CEG graph from scratch
   - Processing with AI extraction
```

### Обработка источника

```
📻 Starting monitor for Финансовые новости (fin_news)
📥 Starting backfill for fin_news (last 7 days)
   - AI extraction: OpenAI GPT
   - CEG analysis: Enabled

Processed 100 messages from fin_news
Extracted 2 events: [rate_hike, bank_stock_up]
Found 3 causal links
Calculated 2 market impacts (significant)
Retroactive analysis: 1 new link created
✨ Processed 1 new items from fin_news
   → Events: 2, Links: 3

✅ Backfill stats for fin_news:
   - Messages: 523
   - Saved news: 201
   - Ads filtered: 89
   - Duplicates: 233
   - Events created: 412
   - Causal links: 87
   - Market impacts: 64
   - Retroactive updates: 23
```

### Финальная статистика

```
======================================================================
📊 FINAL STATISTICS
======================================================================
Total messages processed: 1247
Saved news: 543
Ads filtered: 234
Duplicates: 470
Errors: 0
----------------------------------------------------------------------
CEG STATISTICS:
Events created: 1089
Causal links: 234
Market impacts: 156
Retroactive updates: 67
======================================================================
```

## Настройка источников

Источники настраиваются в базе данных в таблице `sources`:

```sql
INSERT INTO sources (
    id, code, name, kind, tg_chat_id, enabled, trust_level, config
) VALUES (
    uuid_generate_v4(),
    'rbc_news',
    'РБК Новости',
    'telegram',
    '@rbc_news',
    true,
    8,  -- Высокий уровень доверия
    '{"backfill_enabled": true, "fetch_limit": 1000}'::jsonb
);
```

## Конфигурация в .env

```bash
# OpenAI API
API_KEY_2=sk-proj-...
# или
OPENAI_API_KEY=sk-proj-...

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/newsdb

# Neo4j (для CEG)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Telegram
TELETHON_API_ID=12345678
TELETHON_API_HASH=abcdef...
TELETHON_SESSION_NAME=news_parser
TELETHON_PHONE=+79991234567

# Settings
ENABLE_ENRICHMENT=true
PARSER_POLL_INTERVAL=60  # Секунды между проверками (real-time режим)
```

## Архитектура обработки

```
Telegram Message
       ↓
   [AntiSpam Filter]
       ↓
    Save News
       ↓
[Enrichment Service] ← AI Extraction (GPT/Qwen)
       ↓
   ├── Extract Entities (companies, people, metrics)
   ├── Link to MOEX
   ├── Topic Classification
   │
   └──[CEG Real-time Service] ← NEW!
       ├── Event Extraction
       ├── Causal Link Detection (CMNLN)
       ├── Event Study Analysis
       └── Retroactive Analysis
```

## Troubleshooting

### API ключ не найден

```
⚠️  API ключ не найден, будет использован локальный Qwen3-4B
```

**Решение:** Добавьте в `.env`:
```bash
API_KEY_2=your_openai_api_key
```

### Neo4j не подключен

```
⚠ CEG Service not available (Neo4j not connected?)
```

**Решение:**
1. Запустите Neo4j: `docker-compose up -d neo4j`
2. Проверьте настройки в `.env`:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### Нет активных источников

```
No active Telegram sources found
```

**Решение:** Добавьте источники в БД:
```sql
UPDATE sources SET enabled = true WHERE kind = 'telegram';
```

### Qwen модель не загружается

```
Error loading model: Out of memory
```

**Решение:**
1. Используйте GPU: установите CUDA
2. Или используйте OpenAI API вместо локальной модели
3. Уменьшите batch_size в `entity_recognition_local.py`

## Сравнение с demo_ceg_pipeline.py

| Характеристика | demo_ceg_pipeline.py | start_telegram_parser_ceg.py |
|---------------|---------------------|------------------------------|
| **Запуск** | Вручную после парсинга | Автоматически при парсинге |
| **Режим** | Batch (все сразу) | Real-time (постепенно) |
| **CEG** | Строится после загрузки | Строится во время загрузки |
| **Ретроспектива** | Нет | Да, автоматически |
| **Использование** | Демо/тестирование | Продакшн |

## См. также

- [CEG_REALTIME_PIPELINE.md](CEG_REALTIME_PIPELINE.md) - Документация реактивного CEG
- [CEG_README.md](CEG_README.md) - Полная документация CEG
- [CLAUDE.md](CLAUDE.md) - Общая документация проекта
