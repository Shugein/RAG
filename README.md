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
├── parser/               # Основная система агрегации новостей
│   ├── docker-compose.yml        # Docker конфигурация
│   ├── .env.example              # Пример переменных окружения
│   ├── requirements.txt          # Python зависимости
│   ├── alembic.ini               # Конфигурация миграций
│   ├── migrations/               # Миграции базы данных
│   │   └── versions/
│   ├── config/                   # Конфигурационные файлы       
│   ├── src/
│   │   ├── core/
│   ├── services/
│   │   ├── enricher/
│   │   ├── html_parser/
│   │   ├── events/
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── download/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── downloader_functions.py
│   │   │   │   └── check_collection.py
│   │   │   ├── system/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── vdb.py
│   │   │   │   ├── entity_recognition.py
│   │   │   │   ├── search.py
│   │   │   │   ├── engine.py
│   │   │   │   └── llm_final/
│   │   │   │       ├── __init__.py
│   │   │   │       ├── main.py
│   │   │   │       ├── sys_prompt.py
│   │   │   │       └── output.py
│   │   │   ├── vector_store.py
│   │   │   ├── embeddings.py
│   │   │   ├── retriever.py
│   │   │   ├── generator.py
│   │   │   └── rag_pipeline.py
│   │   ├── moex/
│   │   ├── ml/
│   │   ├── analytics/
│   │   ├── outbox/
│   │   ├── storage/
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
│   │   └── graph_models.py
│   ├── data/
│   │   └── learned_aliases.json
│   ├── models/
│   ├── sessions/
│   └── docker/
│       ├── Dockerfile.api
│       ├── Dockerfile.telegram
│       ├── Dockerfile.enricher
│       └── Dockerfile.outbox
```

### Core модули
- **config.py** - управление конфигурацией через Pydantic Settings
- **database.py** - SQLAlchemy engine и сессии
- **models.py** - ORM модели для всех таблиц

### Telegram Parser Service
- **client.py** - инициализация Telethon клиента
- **parser.py** - основная логика парсинга сообщений
- **antispam.py** - многоуровневая фильтрация рекламы

### HTML Parser Service
- **base_html_parser.py** - базовый класс для всех HTML парсеров
- **html_parser_service.py** - сервис управления парсерами
- **forbes_parser.py** - парсер Forbes Russia
- **interfax_parser.py** - парсер Interfax
- **moex_parser.py** - парсер Московской биржи
- **edisclosure_parser.py** - парсер eDisclosure
- **edisclosure_messages_parser.py** - парсер сообщений eDisclosure

### Enricher Service
- **ner_extractor.py** - извлечение сущностей через Natasha
- **moex_linker.py** - связывание компаний с тикерами через Algopack API
- **topic_classifier.py** - классификация по отраслям
- **company_aliases.py** - управление алиасами компаний
- **enrichment_service.py** - основной сервис обогащения
- **moex_auto_search.py** - автоматический поиск по MOEX
- **sector_mapper.py** - маппинг отраслей

### Events & CEG Engine
- **event_extractor.py** - извлечение событий из новостей
- **cmnln_engine.py** - движок CMNLN (Causal Mining of News & Links Networks)
- **causal_chains_engine.py** - построение причинных цепочек
- **ceg_realtime_service.py** - real-time обработка CEG
- **enhanced_evidence_engine.py** - поиск доказательств причинности
- **event_prediction.py** - предсказание событий
- **historical_backfill_service.py** - историческая обработка
- **importance_calculator.py** - расчет важности событий
- **watchers.py** - мониторинг событий

### RAG (Retrieval-Augmented Generation) System
- **download/downloader_functions.py** - загрузка и подготовка данных с NER
- **download/check_collection.py** - проверка коллекций Weaviate
- **system/vdb.py** - создание векторной БД и загрузка данных
- **system/entity_recognition.py** - извлечение финансовых сущностей (GPT-5-nano)
- **system/search.py** - гибридный поиск с реранкингом
- **system/engine.py** - RAG пайплайн (поиск + генерация)
- **system/llm_final/main.py** - основной модуль генерации статей
- **system/llm_final/sys_prompt.py** - System prompt для LLM
- **system/llm_final/output.py** - рендеринг в HTML/PDF
- **vector_store.py** - управление векторным хранилищем
- **embeddings.py** - создание и управление эмбеддингами
- **retriever.py** - поиск релевантных документов
- **generator.py** - генерация ответов на основе найденных документов
- **rag_pipeline.py** - основной RAG пайплайн

### RAG Core Components (в корне src/)
- **download/** - модули загрузки и приема данных
- **system/** - ядро RAG системы
- **system/LLM_final/** - генерация статей

### Market Data & Analytics
- **moex_prices.py** - получение данных с MOEX
- **market_data_service.py** - сервис рыночных данных
- **trading_signals.py** - торговые сигналы
- **impact_calculator.py** - расчет влияния на рынки
- **covariance_service.py** - анализ ковариации
- **analytics/dashboard.py** - аналитическая панель

### Machine Learning
- **news_clustering.py** - кластеризация новостей
- **sentiment_analyzer.py** - анализ тональности

### API Layer
- **main.py** - главный файл FastAPI приложения
- **historical.py** - исторические данные
- **schemas.py** - Pydantic схемы для API
- **websocket.py** - WebSocket соединения
- **endpoints/** - REST API endpoints:
  - **news.py** - управление новостями
  - **sources.py** - управление источниками
  - **health.py** - проверка здоровья системы
  - **jobs.py** - управление задачами
  - **ceg.py** - Causal Event Graph API
  - **importance.py** - API важности событий
  - **watchers.py** - API мониторинга
  - **images.py** - управление изображениями

### Infrastructure
- **outbox/relay.py** - чтение из outbox таблицы
- **outbox/publisher.py** - публикация в RabbitMQ
- **storage/news_repository.py** - CRUD операции с новостями
- **storage/image_service.py** - сохранение и дедупликация изображений
- **cache_service.py** - сервис кэширования
- **event_bus.py** - шина событий
- **news_trigger.py** - триггеры новостей
- **workers/impact_worker.py** - воркер расчета влияния
- **middleware/rate_limiter.py** - ограничение скорости запросов

### Graph Database
- **graph_models.py** - модели для Neo4j графа

### Utilities
- **logging.py** - настройка логирования
- **text_utils.py** - утилиты для работы с текстом

## Технологический стек

### Backend Framework
- **Python 3.11+** - основной язык программирования
- **FastAPI** - современный веб-фреймворк для API
- **Pydantic** - валидация данных и настройки
- **SQLAlchemy 2.0** - современный ORM
- **Alembic** - миграции базы данных

### Databases
- **PostgreSQL 15** - основная реляционная БД
- **Neo4j 5** - графовая БД для CEG
- **Redis 7** - кэш и очереди
- **RabbitMQ 3.12** - брокер сообщений

### Data Collection
- **Telethon** - клиент Telegram API
- **httpx** - асинхронный HTTP клиент
- **aio-pika** - асинхронный RabbitMQ клиент
- **BeautifulSoup4** - парсинг HTML

### NLP & AI
- **Natasha** - NER для русского языка
- **OpenAI GPT** - анализ текста и извлечение событий
- **Qwen3-4B** - локальная альтернатива GPT
- **FuzzyWuzzy** - нечеткое сравнение строк
- **Pymorphy3** - морфологический анализ

### Market Data
- **MOEX ISS API** - данные Московской биржи
- **Algopack API** - связывание компаний с тикерами

### Infrastructure
- **Docker & Docker Compose** - контейнеризация
- **Prometheus** - мониторинг метрик
- **Structlog** - структурированное логирование
- **Pillow** - обработка изображений
- **Tenacity** - retry механизмы

### Development Tools
- **pytest** - тестирование
- **Black** - форматирование кода
- **Flake8** - линтинг
- **MyPy** - проверка типов
##  Быстрый старт

### 1. Требования

- **Python**: 3.12
- **Docker**: 20.10+ с Docker Compose
- **GPU**: NVIDIA GPU с CUDA (опционально, для векторизации)
- **RAM**: минимум 32GB
- **API ключи**: OpenAI API (для извлечения сущностей и генерации статей)
- **20GB** свободного места

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

# Настройка Telegram
```powershell
.\setup_telegram.ps1
```

# Запуск системы
```powershell
.\start_dev.ps1
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

# Database
DATABASE_URL=postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_TTL=3600

# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j

# RabbitMQ
RABBITMQ_URL=amqp://admin:admin123@localhost:5672/
RABBITMQ_EXCHANGE=news
RABBITMQ_PREFETCH_COUNT=10

# Telegram
TELETHON_API_ID=your_api_id
TELETHON_API_HASH=your_api_hash
TELETHON_SESSION_NAME=news_parser
TELETHON_PHONE=+7xxxxxxxxxx
TELEGRAM_BATCH_SIZE=100
TELEGRAM_BACKFILL_DAYS=365

# External APIs
ALGOPACK_API_KEY=your_algopack_key
ALGOPACK_BASE_URL=https://api.algopack.com/v1

# RAG & Vector Search
WEAVIATE_URL=http://localhost:8080
WEAVIATE_API_KEY=your_weaviate_key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
VECTOR_DIMENSION=1536
SIMILARITY_THRESHOLD=0.7
MAX_RETRIEVAL_DOCS=10

# Parsing Configuration
PARSER_WORKERS=4
PARSER_POLL_INTERVAL=60
PARSER_BACKOFF_FACTOR=2.0
PARSER_MAX_RETRIES=3

# Enrichment
ENRICHER_BATCH_SIZE=20
ENRICHER_WORKERS=2
NER_CONFIDENCE_THRESHOLD=0.7
COMPANY_MATCH_THRESHOLD=0.6

# Anti-spam
ANTISPAM_THRESHOLD=5.0
ANTISPAM_TRUSTED_THRESHOLD=8.0

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
API_CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]
API_PAGE_SIZE=50
API_MAX_PAGE_SIZE=200

# Images
IMAGE_MAX_SIZE_MB=15
IMAGE_THUMBNAIL_SIZE=(400, 400)
IMAGE_ALLOWED_TYPES=["image/jpeg", "image/png", "image/webp", "image/gif"]

# Monitoring
METRICS_PORT=9090
LOG_LEVEL=INFO
LOG_FORMAT=json

# Feature Flags
ENABLE_TELEGRAM=true
ENABLE_HTML_PARSER=true
ENABLE_ENRICHMENT=true
ENABLE_ANTISPAM=true
ENABLE_METRICS=true

# Development
DEBUG=false
TESTING=false
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
# docker-compose up -d postgres redis rabbitmq neo4j
```

```bash
alembic upgrade head
```

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

### 6. Запуск сервисов*
```bash
# В отдельных терминалах
python scripts/start_telegram_parser.py
python scripts/start_enricher.py
python scripts/start_outbox_relay.py
python scripts/start_api.py
```

### 7. Проверка данных

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

### 8. Основной RAG-pipeline

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

## Примеры использования

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
