# Структура проекта News Aggregator

```
news-aggregator/
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── alembic.ini
├── migrations/
│   └── versions/
├── config/
│   ├── sources.yml
│   └── ad_rules.yml
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── telegram_parser/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── parser.py
│   │   │   ├── antispam.py
│   │   │   └── handlers.py
│   │   ├── enricher/
│   │   │   ├── __init__.py
│   │   │   ├── ner_extractor.py
│   │   │   ├── moex_linker.py
│   │   │   └── topic_classifier.py
│   │   ├── outbox/
│   │   │   ├── __init__.py
│   │   │   ├── relay.py
│   │   │   └── publisher.py
│   │   └── storage/
│   │       ├── __init__.py
│   │       ├── news_repository.py
│   │       └── image_service.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── endpoints/
│   │   │   ├── news.py
│   │   │   ├── sources.py
│   │   │   └── health.py
│   │   └── dependencies.py
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       ├── metrics.py
│       └── text_utils.py
├── tests/
│   ├── fixtures/
│   └── test_*.py
└── scripts/
    ├── start_telegram_parser.py
    ├── start_enricher.py
    ├── start_outbox_relay.py
    └── start_api.py
```

## Компоненты и их назначение

### Core модули
- **config.py** - управление конфигурацией через Pydantic Settings
- **database.py** - SQLAlchemy engine и сессии
- **models.py** - ORM модели для всех таблиц
- **schemas.py** - Pydantic модели для валидации

### Telegram Parser Service
- **client.py** - инициализация Telethon клиента
- **parser.py** - основная логика парсинга сообщений
- **antispam.py** - многоуровневая фильтрация рекламы
- **handlers.py** - обработчики событий новых сообщений

### Enricher Service
- **ner_extractor.py** - извлечение сущностей через Natasha
- **moex_linker.py** - связывание компаний с тикерами через Algopack API
- **topic_classifier.py** - классификация по отраслям

### Outbox Service
- **relay.py** - чтение из outbox таблицы
- **publisher.py** - публикация в RabbitMQ

### Storage
- **news_repository.py** - CRUD операции с новостями
- **image_service.py** - сохранение и дедупликация изображений

## Технологический стек

- **Python 3.11+**
- **Telethon** - для Telegram API
- **FastAPI** - REST API
- **SQLAlchemy 2.0** - ORM
- **Alembic** - миграции БД
- **Pydantic** - валидация данных
- **aio-pika** - async RabbitMQ клиент
- **Natasha** - NER для русского языка
- **httpx** - HTTP клиент для Algopack API
- **Pillow** - обработка изображений
- **prometheus-client** - метрики
- **structlog** - структурированное логирование

## Переменные окружения (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/newsdb

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Telegram
TELETHON_API_ID=your_api_id
TELETHON_API_HASH=your_api_hash
TELETHON_SESSION_NAME=news_parser
TELETHON_PHONE=+7xxxxxxxxxx

# Algopack API
ALGOPACK_API_KEY=your_api_key
ALGOPACK_BASE_URL=https://api.algopack.com/v1

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Metrics
# METRICS_PORT=9090  # Удален вместе с Prometheus
```