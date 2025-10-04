# Исправление дубликатов в графовой базе данных

## Проблема
В графовой базе данных Neo4j создавались дубликаты узлов компаний и секторов из-за неправильной логики создания ID и отсутствия констрейнтов уникальности.

## Исправления

### 1. Детерминированные ID для узлов

**Файл:** `src/services/enricher/enrichment_service.py`

- **Компании:** Используется формат `moex:{ticker}` вместо случайного UUID
- **Темы:** Используется формат `topic:{normalized_name}` вместо случайного UUID
- **Секторы:** Используется формат `sector:{sector_key}`

```python
# Было:
company_id = str(uuid4())

# Стало:
company_id = f"moex:{company_data['secid']}"
```

### 2. Улучшенная логика MERGE в GraphService

**Файл:** `src/graph_models.py`

- Добавлены операции `ON CREATE SET` и `ON MATCH SET` для правильного upsert
- Обновление полей `created_at` и `updated_at` в зависимости от операции

```cypher
MERGE (c:Company {id: $company_id})
ON CREATE SET 
    c.name = $name,
    c.ticker = $ticker,
    c.is_traded = $is_traded,
    c.created_at = datetime(),
    c.country_code = 'RU'
ON MATCH SET 
    c.name = $name,
    c.ticker = $ticker,
    c.is_traded = $is_traded,
    c.updated_at = datetime()
```

### 3. Констрейнты уникальности

**Файл:** `src/graph_models.py`

Добавлены констрейнты для всех типов узлов:
- `news_id` - уникальность новостей
- `company_id` - уникальность компаний
- `sector_id` - уникальность секторов
- `topic_id` - уникальность тем
- `entity_id` - уникальность сущностей
- `market_id` - уникальность рынков
- `country_code` - уникальность стран
- `regulator_id` - уникальность регуляторов
- `instrument_id` - уникальность инструментов

### 4. Связывание с секторами и рынками

**Файл:** `src/services/enricher/enrichment_service.py`

- Автоматическое создание связи компаний с рынком MOEX
- Автоматическое определение и связывание с секторами на основе тикера
- Использование `MOEXSectorMapper` для маппинга тикеров на секторы

### 5. Новые методы в GraphService

Добавлены методы для работы с секторами и рынками:
- `create_sector_node()` - создание узла сектора
- `link_company_to_sector()` - связывание компании с сектором
- `create_market_node()` - создание узла рынка
- `link_company_to_market()` - связывание компании с рынком

## Инструменты для проверки и очистки

### 1. Проверка целостности графа

**Файл:** `scripts/test_graph_consistency.py`

```bash
python scripts/test_graph_consistency.py
```

Проверяет:
- Дубликаты узлов
- Изолированные узлы
- Качество данных
- Статистику по узлам и связям

### 2. Очистка дубликатов

**Файл:** `scripts/cleanup_graph_duplicates.py`

```bash
# Сухой прогон (только подсчет дубликатов)
python scripts/cleanup_graph_duplicates.py

# Фактическая очистка
python scripts/cleanup_graph_duplicates.py --execute

# Очистка только компаний
python scripts/cleanup_graph_duplicates.py --execute --companies
```

## Графовая схема после исправлений

```
Market {id, name, country_code, source}
  └── [:HAS_COMPANY] → Company {id, name, ticker, isin, country_code, sector}
      ├── [:IN_SECTOR] → Sector {id, name, taxonomy}
      └── [:HAS_INSTRUMENT] → Instrument {id, symbol, type, exchange, currency}

News {id, url, title, text, published_at, source}
  ├── [:ABOUT] → Company
  ├── [:AFFECTS] → Company {weight, window, dt, method}
  ├── [:HAS_TOPIC] → Topic {id, name, confidence}
  └── [:MENTIONS] → Entity {id, text, type, confidence}
```

## Преимущества исправлений

1. **Устранение дубликатов** - каждая компания, сектор и тема имеют уникальный ID
2. **Консистентность данных** - правильная логика upsert предотвращает потерю данных
3. **Производительность** - индексы и констрейнты ускоряют запросы
4. **Целостность** - констрейнты гарантируют уникальность узлов
5. **Мониторинг** - инструменты для проверки и очистки дубликатов

## Использование

После применения исправлений:

1. Запустите проверку целостности:
   ```bash
   python scripts/test_graph_consistency.py
   ```

2. Если найдены дубликаты, очистите их:
   ```bash
   python scripts/cleanup_graph_duplicates.py --execute
   ```

3. Убедитесь, что новые данные создаются без дубликатов

## Примечания

- Все изменения обратно совместимы
- Существующие данные можно очистить с помощью скриптов
- Новые данные автоматически используют правильную логику
- Констрейнты создаются автоматически при инициализации GraphService
