# HTML Parsers Integration Guide

## Обзор

Данное руководство описывает интеграцию HTML парсеров Forbes и Interfax в существующую систему загрузки данных новостей. Парсеры интегрированы в общую архитектуру проекта и используют единую систему обогащения данных.

## Архитектура

### Компоненты системы

1. **BaseHTMLParser** - базовый класс для всех HTML парсеров
2. **ForbesParser** - парсер для Forbes.ru
3. **InterfaxParser** - парсер для Interfax.ru
4. **HTMLParserService** - сервис для управления парсерами
5. **Конфигурация источников** - настройки в `config/sources.yml`

### Структура файлов

```
src/services/html_parser/
├── __init__.py
├── base_html_parser.py      # Базовый класс
├── forbes_parser.py         # Парсер Forbes
├── interfax_parser.py       # Парсер Interfax
└── html_parser_service.py   # Сервис управления

scripts/
└── start_html_parser.py     # Скрипт запуска

config/
└── sources.yml              # Конфигурация источников
```

## Настройка

### 1. Обновление конфигурации источников

В файле `config/sources.yml` добавлены новые HTML источники:

```yaml
sources:
  - code: forbes
    name: Forbes.ru
    kind: html
    base_url: https://www.forbes.ru
    enabled: true
    trust_level: 9
    config:
      sections: ["biznes", "investicii"]
      max_articles_per_section: 25
      delay_between_requests: 2.0
      poll_interval: 3600

  - code: interfax
    name: Интерфакс (сайт)
    kind: html
    base_url: https://www.interfax.ru
    enabled: true
    trust_level: 10
    config:
      categories: ["business", "all"]
      days_back: 3
      max_pages_per_day: 5
      delay_between_requests: 0.4
      poll_interval: 1800
```

### 2. Загрузка источников в БД

```bash
python scripts/load_sources.py
```

## Использование

### Запуск всех HTML парсеров

```bash
# PowerShell
.\start_html_parser.ps1

# Python
python scripts/start_html_parser.py
```

### Запуск конкретного парсера

```bash
# PowerShell
.\start_html_parser.ps1 -Source forbes
.\start_html_parser.ps1 -Source interfax

# Python
python scripts/start_html_parser.py --source forbes
python scripts/start_html_parser.py --source interfax
```

### Настройка параметров

```bash
# Максимальное количество статей на источник
.\start_html_parser.ps1 -MaxArticles 100

# Использование локального AI вместо OpenAI API
.\start_html_parser.ps1 -LocalAI
```

## Особенности парсеров

### Forbes Parser

- **Разделы**: Бизнес, Инвестиции
- **Защита**: Использует ротацию User-Agent для обхода защиты
- **Задержки**: 2 секунды между запросами
- **Дедупликация**: По хешу контента

### Interfax Parser

- **Категории**: Business, All
- **Период**: Последние 3 дня
- **Пагинация**: До 5 страниц в день
- **Задержки**: 0.4 секунды между запросами

## Интеграция с системой

### Обогащение данных

Все парсеры автоматически интегрированы с системой обогащения:

1. **NER извлечение** - извлечение финансовых сущностей
2. **Классификация тем** - автоматическая категоризация
3. **Связывание с MOEX** - связывание с биржевыми инструментами
4. **Расчет влияния** - оценка влияния новостей на рынки

### Дедупликация

Система автоматически исключает дубликаты по:
- Хешу контента (SHA-256)
- URL статьи
- Внешнему ID источника

### Состояние парсера

Каждый источник имеет состояние парсера:
- Время последнего парсинга
- Количество ошибок
- Данные курсора для пагинации

## Мониторинг и логирование

### Логи

Логи сохраняются в:
- `logs/html_parser.log` - основной лог парсеров
- `logs/interfax_universal_collector.log` - лог Interfax (если используется старый парсер)

### Статистика

Парсеры предоставляют детальную статистику:
- Количество обработанных статей
- Количество сохраненных статей
- Количество дубликатов
- Количество ошибок

## Тестирование

### Запуск тестов

```bash
python test_html_parsers.py
```

Тесты проверяют:
1. Подключение к источникам
2. Получение списка статей
3. Парсинг отдельных статей
4. Работу сервиса парсеров

### Отладка

Для отладки можно запустить парсинг с ограниченным количеством статей:

```bash
python scripts/start_html_parser.py --source forbes --max-articles 5
```

## Расширение системы

### Добавление нового парсера

1. Создать класс, наследующий от `BaseHTMLParser`
2. Реализовать методы `get_article_urls()` и `parse_article()`
3. Зарегистрировать парсер в `HTMLParserService`
4. Добавить источник в `config/sources.yml`

### Пример нового парсера

```python
class NewSiteParser(BaseHTMLParser):
    async def get_article_urls(self, max_articles: int = 100) -> List[str]:
        # Логика получения URL статей
        pass
    
    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]:
        # Логика парсинга статьи
        pass
```

## Производительность

### Рекомендации

- **Forbes**: Не более 50 статей за раз (защита от блокировки)
- **Interfax**: До 100 статей за раз
- **Задержки**: Соблюдайте рекомендуемые задержки между запросами
- **Мониторинг**: Следите за логами на предмет ошибок блокировки

### Оптимизация

- Используйте `use_local_ai=True` для экономии на API вызовах
- Настройте `poll_interval` в зависимости от частоты обновления сайтов
- Регулируйте `max_articles` в зависимости от производительности

## Устранение неполадок

### Частые проблемы

1. **Блокировка IP**: Увеличьте задержки между запросами
2. **Ошибки парсинга**: Проверьте селекторы CSS на сайте
3. **Дубликаты**: Убедитесь в правильной работе дедупликации
4. **Ошибки БД**: Проверьте подключение к базе данных

### Логи для диагностики

```bash
# Просмотр логов
tail -f logs/html_parser.log

# Проверка состояния источников в БД
python -c "
import asyncio
from src.core.database import init_db, close_db, get_db_session
from src.core.models import Source
from sqlalchemy import select

async def check_sources():
    await init_db()
    async with get_db_session() as session:
        result = await session.execute(select(Source).where(Source.kind == 'html'))
        sources = result.scalars().all()
        for source in sources:
            print(f'{source.code}: {source.enabled}')
    await close_db()

asyncio.run(check_sources())
"
```

## Заключение

Интеграция HTML парсеров Forbes и Interfax успешно завершена. Парсеры полностью интегрированы в существующую архитектуру системы и готовы к использованию в продакшене.

Для начала работы:
1. Обновите источники: `python scripts/load_sources.py`
2. Запустите тесты: `python test_html_parsers.py`
3. Запустите парсеры: `.\start_html_parser.ps1`
