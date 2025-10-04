# RAG News Processing System

Система для приема, обработки и индексации финансовых новостей с автоматическим извлечением сущностей, гибридным поиском и генерацией статей через LLM.

## 🏗️ Архитектура

```
Tg_app_ui → HTTP Server → Queuery → Processing Pipeline → Weaviate Vector DB → Search → Article Generation
                (8081)                (NER + Chunking)        (8080)           (Hybrid)      (LLM)
```

## 📁 Структура проекта

```
RAG/
radar-ai/
├── src/
│   ├── download/                    # Модули загрузки и приема данных
│   │   ├── downloader_functions.py # Загрузка и подготовка данных (с NER)
│   │   └── check_collection.py     # Проверка коллекций Weaviate
│   │
│   ├── system/                      # Ядро системы
│   │   ├── vdb.py                  # Создание векторной БД и загрузка данных
│   │   ├── entity_recognition.py   # Извлечение финансовых сущностей (GPT-5-nano)
│   │   ├── search.py               # Гибридный поиск с реранкингом
│   │   ├── engine.py               # RAG пайплайн (поиск + генерация)
│   │   │
│   │   └── LLM_final/              # Генерация статей
│   │       ├── main.py             # Основной модуль генерации
│   │       ├── sys_prompt.py       # System prompt для LLM
│   │       └── output.py           # Рендеринг в HTML/PDF
│   │
├── paser/               # Основная система агрегации новостей
│   ├── docker-compose.yml        # Docker конфигурация
│   ├── .env.example              # Пример переменных окружения
│   ├── requirements.txt          # Python зависимости
│   ├── alembic.ini               # Конфигурация миграций
│   ├── migrations/               # Миграции базы данных
│   │   └── versions/
│   ├── config/                   # Конфигурационные файлы
│   │   ├── sources.yml           # Настройки источников
│   │   └── ad_rules.yml          # Правила фильтрации рекламы
│   ├── src/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── models.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── telegram_parser/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── parser.py
│   │   │   └── antispam.py
│   │   ├── enricher/
│   │   │   ├── __init__.py
│   │   │   ├── ner_extractor.py
│   │   │   ├── moex_linker.py
│   │   │   ├── topic_classifier.py
│   │   │   ├── company_aliases.py
│   │   │   ├── enrichment_service.py
│   │   │   ├── moex_auto_search.py
│   │   │   └── sector_mapper.py
│   │   ├── html_parser/
│   │   │   ├── __init__.py
│   │   │   ├── base_html_parser.py
│   │   │   ├── html_parser_service.py
│   │   │   ├── forbes_parser.py
│   │   │   ├── interfax_parser.py
│   │   │   ├── moex_parser.py
│   │   │   ├── edisclosure_parser.py
│   │   │   └── edisclosure_messages_parser.py
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── event_extractor.py
│   │   │   ├── cmnln_engine.py
│   │   │   ├── causal_chains_engine.py
│   │   │   ├── ceg_realtime_service.py
│   │   │   ├── enhanced_evidence_engine.py
│   │   │   ├── event_prediction.py
│   │   │   ├── historical_backfill_service.py
│   │   │   ├── importance_calculator.py
│   │   │   └── watchers.py
│   │   ├── moex/
│   │   │   ├── __init__.py
│   │   │   └── moex_prices.py
│   │   ├── ml/
│   │   │   ├── news_clustering.py
│   │   │   └── sentiment_analyzer.py
│   │   ├── analytics/
│   │   │   └── dashboard.py
│   │   ├── outbox/
│   │   │   ├── __init__.py
│   │   │   ├── relay.py
│   │   │   └── publisher.py
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── news_repository.py
│   │   │   └── image_service.py
│   │   ├── cache_service.py
│   │   ├── covariance_service.py
│   │   ├── event_bus.py
│   │   ├── impact_calculator.py
│   │   ├── market_data_service.py
│   │   ├── news_trigger.py
│   │   └── trading_signals.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── historical.py
│   │   ├── schemas.py
│   │   ├── websocket.py
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       ├── news.py
│   │       ├── sources.py
│   │       ├── health.py
│   │       ├── jobs.py
│   │       ├── ceg.py
│   │       ├── importance.py
│   │       ├── watchers.py
│   │       └── images.py
│   ├── middleware/
│   │   └── rate_limiter.py
│   ├── integrations/
│   │   └── trading_signals.py
│   ├── workers/
│   │   └── impact_worker.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logging.py
│   │   └── text_utils.py
│   └── graph_models.py
├── tests/
│   ├── fixtures/
│   └── test_*.py
└── scripts/
    ├── start_telegram_parser.py
    ├── start_enricher.py
    ├── start_outbox_relay.py
    └── start_api.py
```

## 🚀 Быстрый старт

### 1. Требования

- **Python**: 3.12
- **Docker**: 20.10+ с Docker Compose
- **GPU**: NVIDIA GPU с CUDA (опционально, для векторизации)
- **RAM**: минимум 8GB
- **API ключи**: OpenAI API (для извлечения сущностей и генерации статей)

### 2. Установка

```bash
# Клонировать репозиторий
git clone <repository-url>
cd RAG

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

### 3. Настройка API ключей

Создайте файл `.env` в корне проекта:

```bash
# OpenAI API ключ (для GPT-5-nano в entity_recognition)
API_KEY_2=sk-your-openai-api-key

# OpenAI API ключ (для GPT-5 в генерации статей)
API_KEY=sk-your-openai-api-key

# Модель для генерации статей (опционально)
OPENAI_MODEL=gpt-5
```

### 4. Запуск Weaviate

```bash
# Запустить все сервисы (Weaviate + векторизатор + reranker)
docker compose up -d

# Проверить статус
docker ps

# Должно быть запущено:
# - weaviate (порт 8080)
# - text2vec-transformers (порт 8083) - векторизатор на GPU (дистилция FRIDA)
# - bge-reranker (порт 8082) - reranker
```

Подождите ~1-2 минуты пока все сервисы прогрузятся.

### 5. Загрузка данных в БД

```bash
# Создать коллекцию и загрузить тестовые данные
python src/system/vdb.py
```

**Что происходит:**
1. Загружаются новости
2. Для каждой новости извлекаются сущности (компании, персоны, рынки, метрики) через GPT-5-nano
3. Тексты чанкуются и лемматизируются
4. Данные индексируются в Weaviate с автоматической GPU-векторизацией

**Вывод:**
```
Инициализирован экстрактор сущностей: gpt-5-nano
Извлечение сущностей параллельно для документов
Подготовлено X чанков для загрузки в Weaviate
```

### 6. Проверка данных

```bash
# Проверить содержимое БД
python src/download/check_collection.py
```

**Вывод:**
- Статус сервера Weaviate
- Список всех коллекций
- Схема коллекции NewsChunks (все поля)
- Статистика (количество объектов, источники, временной диапазон)
- 2 примера объектов со всеми метаданными и сущностями

### 7. Основной RAG-pipeline

```bash
# Запустить RAG пайплайн
python src/system/engine.py
```

**Что происходит:**
1. **Гибридный поиск** по запросу 
   - Векторный поиск (семантический)
   - BM25 поиск (лексический/keyword)
   - Реранкинг с BAAI/bge-reranker-v2-m3
   - Учет hotness в финальном скоре
2. **Генерация статьи** через GPT-5
   - Social post (280 слов)
   - Article draft (500 слов)
   - Alert (краткое уведомление)
   - Хэштеги, ключевые моменты, идеи визуализации

**Вывод:**
```
=== HYBRID SEARCH WITH RERANKING ===
Found 10 results after hybrid search + reranking

After hotness adjustment:
 1. Rerank: 0.8500 + Hotness: 0.50 = Final: 0.7450 | Сбербанк показал рекордную прибыль

=== Final Documents (sorted by final score with hotness) ===
📄 Result #1
   Title: Сбербанк показал рекордную прибыль
   Type: 🔹 Full Parent Document
   Final Score: 0.7450 = 0.8500 × 0.70 + 0.50 × 0.30
   Компании: ПАО Сбербанк

=== GENERATED ARTICLE ===
Заголовок: Сбербанк: рекордная прибыль за 4К24, выше консенсуса на 5%
...
```

## 📊 Как работает система

### Пайплайн обработки данных

1. **Загрузка новостей** (`parser/test_news.json`)
   ```json
   {
     "text": "Полный текст новости...",
     "title": "Заголовок",
     "timestamp": 1704067200,
     "url": "https://...",
     "source": "РБК"
   }
   ```

2. **Извлечение сущностей** (`entity_recognition.py`)
   - Параллельная обработка через GPT-5-nano
   - Извлечение: компаний, тикеров, секторов, персон, должностей, рынков, финансовых метрик
   - Кэширование промптов (экономия до 50% на токенах)

3. **Подготовка данных** (`downloader_functions.py`)
   - Чанкинг текста (800 символов, overlap 200)
   - Лемматизация для BM25 (WordNet)
   - Формирование Document объектов с метаданными

4. **Индексация** (`vdb.py`)
   - Создание коллекции NewsChunks
   - Загрузка чанков с автоматической GPU-векторизацией
   - Хранение сущностей в метаданных

### Поисковый пайплайн

**Схема работы:**

```
Query: "Сбербанк прибыль"
         ↓
┌─────────────────────────┐
│  HYBRID SEARCH          │
├─────────────────────────┤
│ • Vector (alpha × s)    │ ← Семантический поиск по original_text
│ • BM25 ((1-alpha) × s)  │ ← Keyword поиск по text_for_bm25
│ • Fusion (RELATIVE)     │ ← Объединение скоров
└─────────────────────────┘
         ↓
┌─────────────────────────┐
│  RERANKING              │
├─────────────────────────┤
│ bge-reranker-v2-m3      │ ← Переранжирование по original_text
└─────────────────────────┘
         ↓
┌─────────────────────────┐
│  HOTNESS ADJUSTMENT     │
├─────────────────────────┤
│ final = rerank×0.7      │
│       + hotness×0.3     │
└─────────────────────────┘
         ↓
┌─────────────────────────┐
│  PARENT DOC RETRIEVAL   │
├─────────────────────────┤
│ Deduplication           │ ← Убираем дубли parent_doc_id
└─────────────────────────┘
         ↓
    Top N results
```

**Параметры поиска:**

- `alpha` (0.0-1.0) - баланс векторный/BM25
  - 0.0 = только BM25 (лексический)
  - 0.5 = гибридный (по умолчанию)
  - 1.0 = только векторный
- `hotness_weight` (0.0-1.0) - вес актуальности
  - 0.0 = только релевантность
  - 0.3 = баланс (по умолчанию)
  - 1.0 = только актуальность

### Генерация статей

**Схема работы:**

```
Search Results (с сущностями)
         ↓
┌──────────────────────────┐
│  EXTRACT ENTITIES        │
├──────────────────────────┤
│ • companies → Instruments│
│ • tickers, sectors       │
│ • sources → SourceItems  │
│ • hotness → hot_score    │
└──────────────────────────┘
         ↓
┌──────────────────────────┐
│  BUILD REQUEST           │
├──────────────────────────┤
│ DraftRequest(            │
│   news_type="earnings",  │
│   tone="explanatory",    │
│   instruments=[...],     │
│   sources=[...],         │
│   body_text=full_text    │
│ )                        │
└──────────────────────────┘
         ↓
┌──────────────────────────┐
│  GPT-5 GENERATION        │
├──────────────────────────┤
│ Structured output:       │
│ • headline, dek          │
│ • variants (social,      │
│   article, alert)        │
│ • key_points, hashtags   │
│ • visual ideas           │
│ • disclaimer             │
└──────────────────────────┘
         ↓
    DraftResponse
```

## 🔧 Конфигурация

### Порты

- **8080** - Weaviate (векторная БД)
- **8082** - BGE Reranker
- **8083** - Text2Vec Transformers (векторизатор)


### Схема БД (Weaviate Collection)

**Коллекция:** `NewsChunks`

**Текстовые поля:**
- `original_text` (TEXT) - оригинальный текст чанка, **векторизуется**
- `text_for_bm25` (TEXT) - лемматизированный текст для BM25, **skip_vectorization=True**
- `parent_doc_text` (TEXT) - полный текст родительского документа

**Метаданные:**
- `chunk_index` (INT) - индекс чанка
- `parent_doc_id` (TEXT) - ID родительского документа
- `title`, `url`, `source` (TEXT) - метаданные новости
- `timestamp` (INT) - Unix timestamp
- `publication_date` (TEXT) - дата публикации YYYY-MM-DD
- `hotness` (NUMBER) - оценка актуальности 0.0-1.0

**Извлеченные сущности:**
- `entities_json` (TEXT) - полный JSON с сущностями
- `companies` (TEXT_ARRAY) - названия компаний
- `company_tickers` (TEXT_ARRAY) - тикеры
- `company_sectors` (TEXT_ARRAY) - секторы
- `people` (TEXT_ARRAY) - имена персон
- `people_positions` (TEXT_ARRAY) - должности
- `markets` (TEXT_ARRAY) - рынки/биржи/индексы
- `market_types` (TEXT_ARRAY) - типы рынков
- `financial_metric_types` (TEXT_ARRAY) - типы метрик
- `financial_metric_values` (TEXT_ARRAY) - значения метрик

## 🎯 Примеры использования

### Пример 1: Поиск с разными alpha

```python
from src.system.engine import RAGPipeline

rag = RAGPipeline()
rag.connect()

# Только семантический поиск (alpha=1.0)
results = rag.search("новости о финансовом кризисе", alpha=1.0)

# Только keyword поиск (alpha=0.0)
results = rag.search("Сбербанк прибыль", alpha=0.0)

# Гибридный поиск (alpha=0.5)
results = rag.search("инвестиции в технологии", alpha=0.5)
```

### Пример 2: Генерация разных форматов статей

```python
# Earnings новость
result = rag.query(
    user_query="Сбербанк отчитался за квартал",
    news_type="earnings",
    tone="explanatory",
    desired_outputs=["social_post", "article_draft", "alert"]
)

# Макро-новость
result = rag.query(
    user_query="ЦБ повысил ключевую ставку",
    news_type="macro",
    tone="urgent",
    desired_outputs=["alert", "social_post"]
)

# Индустриальный тренд
result = rag.query(
    user_query="Развитие финтех-сектора",
    news_type="industry_trend",
    tone="explanatory",
    desired_outputs=["article_draft", "digest"]
)
```

### Пример 3: Сохранение статьи в PDF

```python
from src.system.LLM_final.output import save_article_pdf

# Генерируем статью
result = rag.query(user_query="...")
draft = result['draft']

# Сохраняем в PDF
pdf_path = save_article_pdf(
    draft.model_dump(by_alias=True),
    "article_output.pdf"
)
print(f"PDF сохранён: {pdf_path}")
```

## 📡 API для интеграции

### Python API

```python
from src.system.engine import RAGPipeline

# Инициализация
rag = RAGPipeline(collection_name="NewsChunks")
rag.connect()

# Поиск
results = rag.search(
    query="Яндекс технологии",
    limit=10,
    rerank_limit=3,
    alpha=0.5,
    hotness_weight=0.3
)

# Генерация статьи
article = rag.query(
    user_query="Новости о Яндексе",
    news_type="tech_fintech",
    tone="explanatory"
)

# Результат
print(article['draft'].headline)
print(article['draft'].variants['article_draft'])
```

## 🐛 Troubleshooting

### Weaviate не запускается

```bash
# Проверить логи
docker logs weaviate

# Перезапустить
docker compose down
docker compose up -d
```

### Ошибка GPU

Если нет GPU, измените в `docker-compose.yml`:

```yaml
text2vec-transformers:
  environment:
    ENABLE_CUDA: "0"  # Отключить CUDA
```

И удалите секцию `deploy.resources`.

### Нет результатов поиска

```bash
# Проверьте количество объектов в БД
python src/download/check_collection.py
```

Если коллекция пустая:
```bash
# Загрузите данные
python src/system/vdb.py
```

## 📈 Производительность

### Скорость обработки

- **Извлечение сущностей:** ~2-3 секунды (параллельно через API OpenAI)
- **Индексация:** ~0.02 секунды для batch 32
- **Поиск:** ~0.5-1 секунда
- **Генерация статьи:** ~15 секунд

### Оптимизация

**Для больших объемов:**
1. Увеличить batch size в `vdb.py`
2. Использовать GPU для векторизатора (реализовано)
3. Кэширование промптов (уже реализовано в `entity_recognition.py`)

**Для точности:**
1. Настроить `alpha` для вашего use case
2. Увеличить `limit` для большего покрытия
3. Настроить `hotness_weight` для приоритета актуальности

## 🔍 Мониторинг

### Проверка здоровья системы

```bash
# Weaviate
curl http://localhost:8080/v1/meta

# Векторизатор
curl http://localhost:8083/.well-known/ready

# Reranker
curl http://localhost:8082/.well-known/ready
```

### Логи

```bash
# Docker логи
docker logs weaviate
docker logs text2vec-transformers
docker logs bge-reranker

# Python логи
# Добавлены в engine.py через logging module
```

## 🛠️ Разработка

### Использоване Bert like моделей для определения важности новости


### Настройка модуля памяти

### Подборка горячих новостей

Функционал почти реализован, нужно повысить качество метрики hotness
