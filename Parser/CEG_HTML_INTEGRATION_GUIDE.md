# CEG HTML Integration Guide

## Обзор

Данное руководство описывает интеграцию HTML парсеров Forbes и Interfax в CEG (Corporate Event Graph) систему. HTML источники теперь полностью интегрированы в единую систему обработки новостей с AI-based анализом и графовой базой данных.

## Архитектура интеграции

### Компоненты системы

```
CEG Parser Service
├── Telegram Sources (existing)
│   ├── Batch processing
│   ├── NER entity extraction
│   ├── CEG analysis
│   └── Neo4j graph creation
└── HTML Sources (NEW)
    ├── Forbes.ru parser
    ├── Interfax.ru parser
    ├── Same NER processing
    ├── Same CEG analysis
    └── Same Neo4j integration
```

### Единая обработка данных

1. **Telegram источники** - обрабатываются как раньше
2. **HTML источники** - новые Forbes и Interfax парсеры
3. **Общая NER система** - AI-based извлечение сущностей
4. **Общий CEG анализ** - анализ причинных связей
5. **Общая графовая БД** - Neo4j для всех источников

## Обновленный CEG скрипт

### Основной файл
- `scripts/start_telegram_parser_ceg.py` - обновлен для поддержки HTML источников

### Новые возможности

```python
class TelegramParserServiceCEG:
    """
    🚀 УЛУЧШЕННЫЙ Telegram Parser с BATCH обработкой и полным CEG анализом
    🌐 + ИНТЕГРАЦИЯ HTML ПАРСЕРОВ (Forbes, Interfax)
    """
```

### Ключевые изменения

1. **Двойная инициализация источников**:
   ```python
   # Telegram источники
   telegram_sources = await session.execute(
       select(Source).where(
           Source.kind == SourceKind.TELEGRAM,
           Source.enabled == True
       )
   )
   
   # HTML источники
   html_sources = await session.execute(
       select(Source).where(
           Source.kind == SourceKind.HTML,
           Source.enabled == True
       )
   )
   ```

2. **Параллельная обработка**:
   ```python
   # Telegram мониторинг
   for source in telegram_sources:
       task = asyncio.create_task(
           self._monitor_telegram_source_batch(source)
       )
   
   # HTML мониторинг
   for source in html_sources:
       task = asyncio.create_task(
           self._monitor_html_source_batch(source)
       )
   ```

3. **Единая NER обработка**:
   - HTML новости проходят через ту же NER систему
   - Извлечение финансовых сущностей
   - Классификация тем и событий

4. **Общий CEG анализ**:
   - Анализ важности событий
   - Поиск причинных связей
   - Генерация предсказаний

## Конфигурация источников

### Обновленный sources.yml

```yaml
sources:
  # Telegram sources (existing)
  - code: interfax
    name: Интерфакс
    kind: telegram
    # ... existing config

  # HTML sources (NEW)
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
      poll_interval: 3600  # 1 час

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
      poll_interval: 1800  # 30 минут
```

## Использование

### Запуск CEG парсера

```bash
# PowerShell - все источники
.\start_ceg_parser.ps1

# PowerShell - только Telegram
.\start_ceg_parser.ps1 -TelegramOnly

# PowerShell - только HTML
.\start_ceg_parser.ps1 -HTMLOnly

# Python напрямую
python scripts/start_telegram_parser_ceg.py
```

### Режимы работы

1. **Историческая загрузка**:
   - Загружает новости за указанный период
   - Обрабатывает и Telegram, и HTML источники
   - Выполняет полный CEG анализ

2. **Мониторинг в реальном времени**:
   - Следит за новыми новостями
   - Разные интервалы опроса для разных типов источников
   - Непрерывный CEG анализ

### Настройки batch обработки

- **Batch размер**: количество новостей в одном batch
- **Максимальные batch**: ограничение общего количества
- **Задержки**: между batch для избежания rate limiting
- **Retry логика**: повторные попытки при ошибках сети

## Обработка данных

### Единый pipeline

```
1. Сбор данных
   ├── Telegram: iter_messages()
   └── HTML: parse_article()

2. NER обработка
   ├── AI entity extraction
   ├── Financial entities
   └── Event classification

3. CEG анализ
   ├── Importance scoring
   ├── Causal link detection
   └── Prediction generation

4. Graph creation
   ├── Neo4j nodes
   ├── Relationships
   └── Properties

5. JSON output
   ├── Detailed responses
   ├── Metadata
   └── Analytics
```

### Формат данных

HTML новости преобразуются в тот же формат, что и Telegram:

```python
news_batch.append({
    "id": str(news.id),
    "text": news.text_plain or news.title or "",
    "title": news.title,
    "date": news.published_at,
    "source_id": source.id,
    "source_name": source.name,
    "external_id": news.external_id,
    "url": news.url,
    "ad_score": 0.0,  # HTML источники считаем не рекламой
    "ad_reasons": []
})
```

## Статистика и мониторинг

### Расширенная статистика

```python
self.total_stats = {
    # Existing stats
    "total_messages": 0,
    "saved_news": 0,
    "entities_extracted": 0,
    "graph_nodes_created": 0,
    
    # New HTML stats
    "html_sources_processed": 0,
    "html_articles_processed": 0,
    "telegram_sources_processed": 0
}
```

### Логирование

```
📡 Found 7 active Telegram sources
🌐 Found 2 active HTML sources
📊 Total sources: 9

🌐 Starting BATCH monitor for HTML source Forbes.ru (forbes)
📊 Collected 15 HTML news items for batch processing
✅ HTML batch processing completed for forbes
   - News processed: 15
   - Entities extracted: 45
   - Graph nodes created: 23
   - CEG links created: 67
```

## Производительность

### Оптимизации

1. **Параллельная обработка**: Telegram и HTML источники обрабатываются параллельно
2. **Разные интервалы**: HTML источники опрашиваются реже (30-60 минут vs 5 минут)
3. **Batch размеры**: HTML источники используют меньшие batch (25 vs 50)
4. **Retry логика**: Обработка сетевых ошибок и временных недоступностей

### Рекомендации

- **Forbes**: 25 статей за раз, интервал 1 час
- **Interfax**: 50 статей за раз, интервал 30 минут
- **Telegram**: 50 сообщений за раз, интервал 5 минут

## Устранение неполадок

### Частые проблемы

1. **HTML парсер не находит статьи**:
   - Проверьте доступность сайта
   - Увеличьте задержки между запросами
   - Проверьте селекторы CSS

2. **Блокировка IP**:
   - Используйте ротацию User-Agent
   - Увеличьте интервалы опроса
   - Настройте прокси (если нужно)

3. **Ошибки NER обработки**:
   - Проверьте API ключи
   - Уменьшите batch размер
   - Используйте локальный AI

### Логи для диагностики

```bash
# Основные логи
tail -f logs/html_parser.log
tail -f logs/telegram_parser.log

# CEG логи
tail -f logs/ceg_realtime.log

# Проверка источников в БД
python -c "
import asyncio
from src.core.database import init_db, close_db, get_db_session
from src.core.models import Source
from sqlalchemy import select

async def check_sources():
    await init_db()
    async with get_db_session() as session:
        result = await session.execute(select(Source))
        sources = result.scalars().all()
        for source in sources:
            status = '✓' if source.enabled else '✗'
            print(f'{status} {source.code}: {source.name} ({source.kind})')
    await close_db()

asyncio.run(check_sources())
"
```

## Расширение системы

### Добавление новых HTML парсеров

1. Создайте новый парсер, наследующий от `BaseHTMLParser`
2. Добавьте в `HTMLParserService.parser_registry`
3. Добавьте источник в `config/sources.yml`
4. Перезапустите CEG парсер

### Интеграция с другими источниками

Система легко расширяется для поддержки:
- RSS лент
- API новостных сервисов
- Социальных сетей
- Других веб-сайтов

## Заключение

Интеграция HTML парсеров в CEG систему успешно завершена. Теперь система поддерживает:

✅ **Единую обработку** Telegram и HTML источников  
✅ **AI-based NER** для всех типов новостей  
✅ **CEG анализ** с причинными связями  
✅ **Графовую БД** Neo4j для всех данных  
✅ **Batch обработку** с оптимизацией  
✅ **Real-time мониторинг** с разными интервалами  
✅ **Детальную статистику** и логирование  

Для начала работы:
1. Обновите источники: `python scripts/load_sources.py`
2. Запустите CEG парсер: `.\start_ceg_parser.ps1`
3. Мониторьте логи и статистику

Система готова к продакшену и может обрабатывать новости из множества источников в едином CEG pipeline!
