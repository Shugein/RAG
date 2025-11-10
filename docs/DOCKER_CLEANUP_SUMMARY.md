# Docker Files Cleanup Summary

## Что было сделано

### 1. Объединение docker-compose файлов

**Было:**
- `docker-compose.yml` (корневой) - 262 строки с дублированием сервисов
- `Parser/docker/docker-compose.yml` - 174 строки с теми же сервисами

**Стало:**
- Единый `docker-compose.yml` с профилями - 273 строки
- Удален дублирующий `Parser/docker/docker-compose.yml`

### 2. Добавлены профили для выборочного запуска

- **rag** - RAG стек (Weaviate + трансформеры с GPU)
- **parser** - Parser сервисы (Telegram, Enricher, Outbox, API)
- **infrastructure** - Базовая инфраструктура (Postgres, RabbitMQ, Redis)
- **graph** - Neo4j графовая БД

### 3. Унификация переменных окружения

**Было:**
- `.env` (корневой)
- `Parser/.env` (удален как дубликат)

**Стало:**
- Единый `.env` в корне проекта
- Все сервисы используют `env_file: .env`

### 4. Удалены устаревшие файлы

- ❌ `Parser/docker/docker-compose.yml` (дубликат)
- ❌ `Parser/.env` (дубликат)
- ❌ `Parser/Dockerfile.local` (устаревший монолитный образ)

### 5. Оптимизированная структура Dockerfile'ов

Используется multi-stage build подход:

```
Parser/docker/
├── Dockerfile.base       # Базовый образ (Python + deps)
├── Dockerfile.telegram   # FROM base + CMD telegram
├── Dockerfile.enricher   # FROM base + CMD enricher
├── Dockerfile.outbox     # FROM base + CMD outbox
└── Dockerfile.api        # FROM base + EXPOSE + CMD api
```

Преимущества:
- Переиспользование слоев
- Быстрая сборка
- Консистентность окружения

## Текущая структура

```
RAG/
├── docker-compose.yml          # Единый файл с профилями
├── .env                        # Единый файл с переменными
├── Dockerfile                  # BERTA transformers (RAG)
├── DOCKER_GUIDE.md            # Документация по использованию
└── Parser/
    └── docker/
        ├── Dockerfile.base      # Базовый образ
        ├── Dockerfile.telegram  # Telegram parser
        ├── Dockerfile.enricher  # Enricher service
        ├── Dockerfile.outbox    # Outbox relay
        └── Dockerfile.api       # REST API
```

## Как использовать

### Запуск Parser стека
```bash
docker-compose --profile parser up -d
```

### Запуск RAG стека
```bash
docker-compose --profile rag up -d
```

### Запуск всего
```bash
docker-compose --profile rag --profile parser up -d
```

### Запуск только инфраструктуры (для разработки)
```bash
docker-compose --profile infrastructure up -d
```

## Преимущества новой структуры

1. **Нет дублирования** - единый источник правды
2. **Гибкость** - профили позволяют запускать только нужные компоненты
3. **Простота** - все в одном месте, легко понять и поддерживать
4. **Эффективность** - переиспользование базового образа
5. **Консистентность** - единый .env файл для всех сервисов

## Миграция для разработчиков

Если вы использовали старые команды:

### Старый способ ❌
```bash
cd Parser/docker
docker-compose up -d
```

### Новый способ ✅
```bash
# Из корневой директории
docker-compose --profile parser up -d
```

## Порты (изменения)

**PostgreSQL:**
- Было: `5433:5432` (корневой) и `5432:5432` (Parser)
- Стало: `5432:5432` (единый стандартный порт)

Все остальные порты остались без изменений.

## Дополнительная документация

- `DOCKER_GUIDE.md` - Полное руководство по использованию Docker
- `README.md` - Общая документация проекта
- `Parser/CLAUDE.md` - Архитектура и детали реализации

## Обратная совместимость

⚠️ **Внимание**: После этих изменений старые команды с `Parser/docker/docker-compose.yml` работать не будут.

Обновите свои скрипты и документацию на новые команды с профилями.
