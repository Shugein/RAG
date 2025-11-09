# Docker Compose Guide

## Структура проекта

Проект использует единый `docker-compose.yml` с профилями для выборочного запуска различных компонентов системы.

## Доступные профили

### 1. **rag** - RAG Stack (Weaviate + трансформеры)
Включает:
- `text2vec-transformers` - BERTA embeddings (требует GPU)
- `reranker-transformers` - BGE reranker (требует GPU)
- `weaviate` - векторная база данных

### 2. **parser** - News Parser Stack
Включает:
- `telegram-parser` - парсер Telegram каналов
- `enricher` - обогащение новостей (NER, компании, темы)
- `outbox-relay` - публикация событий в RabbitMQ
- `api` - REST API для доступа к данным
- Зависимости: `postgres`, `rabbitmq`, `redis`, `neo4j`

### 3. **infrastructure** - Базовая инфраструктура
Включает:
- `postgres` - PostgreSQL база данных
- `rabbitmq` - брокер сообщений
- `redis` - кэш и очереди

### 4. **graph** - Graph Database
Включает:
- `neo4j` - графовая база данных для причинно-следственных связей

## Команды запуска

### Запуск только RAG стека
```bash
docker-compose --profile rag up -d
```

### Запуск только Parser стека
```bash
docker-compose --profile parser up -d
```

### Запуск только инфраструктуры
```bash
docker-compose --profile infrastructure up -d
```

### Запуск всего вместе
```bash
docker-compose --profile rag --profile parser up -d
```

### Запуск Parser + Graph (без RAG)
```bash
docker-compose --profile parser --profile graph up -d
```

## Остановка сервисов

### Остановить все сервисы
```bash
docker-compose down
```

### Остановить с удалением volumes (данные будут потеряны!)
```bash
docker-compose down -v
```

## Просмотр логов

### Все сервисы
```bash
docker-compose logs -f
```

### Конкретный сервис
```bash
docker-compose logs -f telegram-parser
docker-compose logs -f api
docker-compose logs -f weaviate
```

## Доступ к сервисам

### Parser Stack
- **API**: http://localhost:8000
  - Docs: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432
  - DB: newsdb
  - User: newsuser
  - Pass: newspass
- **RabbitMQ Management**: http://localhost:15672
  - User: admin
  - Pass: admin123
- **Redis**: localhost:6379
- **Neo4j Browser**: http://localhost:7474
  - User: neo4j
  - Pass: password123

### RAG Stack
- **Weaviate**: http://localhost:8083
- **Text2Vec Transformers**: http://localhost:8081
- **Reranker**: http://localhost:8082

## Требования

### Для RAG стека
- NVIDIA GPU с поддержкой CUDA
- NVIDIA Container Toolkit
- Минимум 8GB VRAM

### Для Parser стека
- 4GB RAM минимум
- 10GB свободного места на диске для данных

## Переменные окружения

Все переменные окружения хранятся в корневом файле `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb

# RabbitMQ
RABBITMQ_URL=amqp://admin:admin123@localhost:5672/

# Redis
REDIS_URL=redis://localhost:6379/0

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j

# Telegram API (получить на my.telegram.org)
TELETHON_API_ID=your_api_id
TELETHON_API_HASH=your_api_hash
TELETHON_PHONE=+7xxxxxxxxxx

# Algopack API (для MOEX данных)
ALGOPACK_API_KEY=your_api_key
ALGOPACK_BASE_URL=https://api.algopack.com/v1

# OpenRouter API (для NER extraction)
API_KEY_2=sk-or-v1-...
```

## Структура Docker файлов

```
RAG/
├── docker-compose.yml          # Единый файл с профилями
├── Dockerfile                  # BERTA transformers
├── .env                        # Переменные окружения
└── Parser/
    └── docker/
        ├── Dockerfile.telegram  # Telegram parser
        ├── Dockerfile.enricher  # Enricher service
        ├── Dockerfile.outbox    # Outbox relay
        └── Dockerfile.api       # REST API
```

## Troubleshooting

### Проверка статуса
```bash
docker-compose ps
```

### Проверка здоровья сервисов
```bash
docker-compose ps | grep healthy
```

### Перезапуск конкретного сервиса
```bash
docker-compose restart telegram-parser
```

### Пересборка после изменений кода
```bash
docker-compose --profile parser build
docker-compose --profile parser up -d
```

### Очистка всего (осторожно!)
```bash
docker-compose down -v
docker system prune -a --volumes
```

## Миграции базы данных

Миграции запускаются автоматически при старте сервисов. Для ручного запуска:

```bash
docker-compose exec api alembic upgrade head
```

## Разработка

### Локальный запуск (без Docker)
```bash
# Запустить только инфраструктуру в Docker
docker-compose --profile infrastructure up -d

# Запустить приложения локально
cd Parser
python scripts/start_telegram_parser.py
python scripts/start_enricher.py
python scripts/start_api.py
```

### Отладка
```bash
# Войти в контейнер
docker-compose exec telegram-parser bash

# Проверить переменные окружения
docker-compose exec telegram-parser env | grep DATABASE_URL
```

## Best Practices

1. **Разработка**: используйте `--profile infrastructure` для запуска только БД, остальное локально
2. **Тестирование**: используйте `--profile parser` для полного стека Parser
3. **Продакшн**: рекомендуется разделить на отдельные docker-compose файлы или использовать оркестратор (Kubernetes)
4. **Бэкапы**: регулярно делайте бэкапы volumes (особенно `postgres_data` и `neo4j_data`)

## Мониторинг

### Использование ресурсов
```bash
docker stats
```

### Размер volumes
```bash
docker system df -v
```

### Сетевая активность
```bash
docker network inspect rag-network
```
