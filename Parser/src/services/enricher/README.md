# MOEX Company Linker с автоматическим обучением

Модули для автоматического поиска и связывания компаний с инструментами Московской биржи.

## Компоненты

### 1. `company_aliases.py` - Централизованное управление алиасами

Единая точка хранения всех алиасов компаний (ручных и автоматически выученных).

**Основные возможности:**
- Хранение вручную проверенных алиасов
- Автоматическое обучение новых алиасов
- Персистентное хранение в JSON файле
- Синглтон для использования во всех модулях

**Использование:**
```python
from src.services.enricher.company_aliases import get_alias_manager

# Получить менеджер
alias_manager = get_alias_manager()

# Получить тикер по алиасу
ticker = alias_manager.get_ticker("сбербанк")  # "SBER"

# Добавить новый алиас
alias_manager.add_learned_alias("сбер банк", "SBER")

# Получить все алиасы для тикера
aliases = alias_manager.get_aliases_for_ticker("SBER")
# ["сбер", "сбербанк", "sberbank", ...]
```

### 2. `moex_auto_search.py` - Автоматический поиск через MOEX ISS API

Автоматический поиск инструментов на Московской бирже используя **бесплатное ISS API**.

**Основные возможности:**
- Поиск по названию компании
- Автоматическое извлечение ISIN кодов
- Поиск лучшего совпадения с учетом приоритетов
- Автоматическое обучение и сохранение алиасов
- Кеширование результатов

**API MOEX ISS:**
- Документация: https://iss.moex.com/iss/reference/
- Поиск: `https://iss.moex.com/iss/securities.json?q=<query>`
- Детали: `https://iss.moex.com/iss/securities/<ticker>.json`

**Использование:**
```python
from src.services.enricher.moex_auto_search import MOEXAutoSearch

# Инициализация
searcher = MOEXAutoSearch()
await searcher.initialize()

# Прямой поиск
results = await searcher.search_by_query("Сбербанк", limit=5)
for result in results:
    print(f"{result.secid} - {result.shortname} (ISIN: {result.isin})")

# Поиск лучшего совпадения
match = await searcher.find_best_match("Газпром нефть")
if match:
    print(f"Ticker: {match.secid}, ISIN: {match.isin}")

# Автообучение из NER сущности
entity_name = "ПАО Лукойл"
learned = await searcher.auto_learn_from_ner(entity_name, save_alias=True)
# Автоматически: находит LKOH, извлекает ISIN, сохраняет алиас

await searcher.close()
```

**Возвращаемые данные:**
```python
@dataclass
class MOEXSecurityInfo:
    secid: str              # Тикер (например, "SBER")
    shortname: str          # Короткое название
    name: str               # Полное название
    isin: Optional[str]     # ISIN код (RU0009029540)
    regnumber: Optional[str]
    is_traded: bool         # Торгуется ли сейчас
    market: Optional[str]   # shares, bonds, etc
    engine: Optional[str]
    type: Optional[str]
    primary_boardid: Optional[str]  # TQBR, TQTF, etc
```

### 3. `moex_linker.py` - Интегрированный линкер (обновлен)

Обновленная версия использует общие алиасы и автоматический поиск.

**Изменения:**
- ✅ Убрано дублирование `KNOWN_ALIASES`
- ✅ Использует `CompanyAliasManager`
- ✅ Автоматический поиск через MOEX ISS API
- ✅ Автообучение при обнаружении новых компаний

**Использование:**
```python
from src.services.enricher.moex_linker import MOEXLinker

# Инициализация (с автообучением)
linker = MOEXLinker(enable_auto_learning=True)
await linker.initialize()

# Поиск компаний в тексте
text = "Сбербанк отчитался о рекордной прибыли"
companies = await linker.link_companies(text)

# Поиск по NER сущностям
entities = [{"type": "ORG", "text": "Норильский никель"}]
companies = await linker.link_companies(text, entities)

await linker.close()
```

### 4. `topic_classifier.py` - Классификатор тем (обновлен)

Также обновлен для использования общих алиасов.

## Workflow автоматического обучения

```
1. NER извлекает сущность "ПАО Лукойл"
   ↓
2. Проверка в известных алиасах → не найдено
   ↓
3. Автопоиск через MOEX ISS API
   ├─ Запрос: GET /iss/securities.json?q=ПАО Лукойл
   ├─ Находит: LKOH (Лукойл)
   └─ ISIN: RU0009024277
   ↓
4. Сохранение алиаса
   ├─ "пао лукойл" → "LKOH"
   └─ Запись в data/learned_aliases.json
   ↓
5. Возврат результата с ISIN кодом
```

## Хранение данных

### `data/learned_aliases.json`
Автоматически выученные алиасы:
```json
{
  "пао лукойл": "LKOH",
  "газпром нефть": "SIBN",
  "группа пик": "PIKK"
}
```

Файл обновляется автоматически при обнаружении новых компаний.

## Преимущества

### Было:
- ❌ Дублирование кода в двух модулях
- ❌ Ручное добавление алиасов
- ❌ Нужно знать все ISIN коды заранее
- ❌ Синхронизация изменений в двух местах

### Стало:
- ✅ Единый источник алиасов
- ✅ Автоматическое обучение
- ✅ ISIN коды извлекаются автоматически
- ✅ Система учится на новых данных
- ✅ Использует бесплатное MOEX ISS API

## Конфигурация

### Включение/выключение автообучения

```python
# С автообучением (по умолчанию)
linker = MOEXLinker(enable_auto_learning=True)

# Без автообучения (только известные алиасы)
linker = MOEXLinker(enable_auto_learning=False)
```

### Настройка кеширования

```python
# С кешем (рекомендуется)
searcher = MOEXAutoSearch(use_cache=True)

# Без кеша
searcher = MOEXAutoSearch(use_cache=False)
```

### Настройка порогов

В `moex_auto_search.py`:
```python
# Минимальный score для автосохранения
auto_match = await searcher.auto_learn_from_ner(
    entity_name,
    min_confidence_score=50.0,  # Увеличьте для большей точности
    save_alias=True
)
```

## Примеры использования

### Пример 1: Обработка новости с автообучением

```python
from src.services.enricher.ner_extractor import NERExtractor
from src.services.enricher.moex_linker import MOEXLinker

# Инициализация
ner = NERExtractor(use_ml_ner=True)
linker = MOEXLinker(enable_auto_learning=True)
await linker.initialize()

# Текст новости
text = """
ПАО "Полюс" увеличило добычу золота на 15% в третьем квартале.
Компания Норникель планирует выплатить дивиденды.
"""

# Извлечение сущностей
entities = ner.extract_entities(text)
org_entities = [e for e in entities if e.type == "ORG"]

# Автоматическое связывание + обучение
for entity in org_entities:
    match = await linker.link_organization(entity.text)
    if match:
        print(f"{entity.text} → {match.ticker} (ISIN: {match.isin})")
        print(f"  Метод: {match.match_method}")
        # Если match_method == "auto_learned", алиас сохранен автоматически!

await linker.close()
```

### Пример 2: Пакетный импорт компаний

```python
from src.services.enricher.moex_auto_search import MOEXAutoSearch

searcher = MOEXAutoSearch()
await searcher.initialize()

# Список компаний для импорта
companies = [
    "Татнефть",
    "Северсталь", 
    "Детский мир",
    "HeadHunter"
]

for company_name in companies:
    result = await searcher.auto_learn_from_ner(company_name, save_alias=True)
    if result:
        print(f"✓ {company_name}: {result.secid} (ISIN: {result.isin})")
    else:
        print(f"✗ {company_name}: не найдено")

# Все алиасы автоматически сохранены!
await searcher.close()
```

### Пример 3: Просмотр выученных алиасов

```python
from src.services.enricher.company_aliases import get_alias_manager

manager = get_alias_manager()

# Все алиасы
all_aliases = manager.get_all_aliases()
print(f"Всего алиасов: {len(all_aliases)}")

# Только выученные
learned = manager.learned_aliases
print(f"Выученных: {len(learned)}")

# Алиасы для конкретного тикера
sber_aliases = manager.get_aliases_for_ticker("SBER")
print(f"SBER алиасы: {sber_aliases}")
```

## Производительность

- **Поиск в кеше:** < 1 мс
- **Поиск через MOEX ISS API:** 100-300 мс
- **Автообучение (первый раз):** 150-350 мс
- **Повторный поиск:** < 1 мс (кеш)

## Лимиты и ограничения

- MOEX ISS API - бесплатный, без ограничений по запросам
- Рекомендуется включить кеширование для production
- Выученные алиасы сохраняются локально

## Troubleshooting

### Проблема: Неправильно определена компания

**Решение:** Вручную добавьте корректный алиас
```python
from src.services.enricher.company_aliases import get_alias_manager

manager = get_alias_manager()
manager.add_learned_alias("некорректный алиас", "ПРАВИЛЬНЫЙ_ТИКЕР")
```

### Проблема: Много ложных срабатываний

**Решение:** Увеличьте порог confidence
```python
# В moex_linker.py, line ~453
confidence=0.85  # Увеличьте до 0.90+
```

### Проблема: Не находит компанию

**Решение:** Проверьте поиск напрямую через MOEX ISS
```bash
curl "https://iss.moex.com/iss/securities.json?q=название_компании"
```

## Миграция старого кода

### До:
```python
# moex_linker.py и topic_classifier.py
KNOWN_ALIASES = {
    "сбер": "SBER",
    ...
}
```

### После:
```python
# Импортируем общий менеджер
from src.services.enricher.company_aliases import get_alias_manager

self.alias_manager = get_alias_manager()
ticker = self.alias_manager.get_ticker("сбер")
```

## TODO / Будущие улучшения

- [ ] Поддержка облигаций, фьючерсов
- [ ] Интеграция с Neo4j для хранения алиасов
- [ ] Веб-интерфейс для управления алиасами
- [ ] Экспорт/импорт алиасов
- [ ] Метрики качества автообучения
- [ ] A/B тестирование разных алгоритмов поиска

## Контакты и поддержка

Вопросы и предложения: см. IMPLEMENTATION_NOTES.md

