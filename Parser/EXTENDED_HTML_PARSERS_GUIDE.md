# 🌐 Расширенные HTML Парсеры - Руководство

## 📋 Обзор

Добавлены новые HTML парсеры для расширения источников данных в системе CEG:

### 🆕 Новые парсеры:

1. **E-disclosure Parser** (`edisclosure_parser.py`)
   - Парсит новости с сайта E-disclosure.ru
   - Источник: https://www.e-disclosure.ru/vse-novosti
   - Тип: Корпоративные новости и события

2. **MOEX Parser** (`moex_parser.py`)
   - Парсит новости с сайта Московской биржи
   - Источник: https://www.moex.com/ru/news/
   - Тип: Финансовые новости и объявления

3. **E-disclosure Messages Parser** (`edisclosure_messages_parser.py`)
   - Парсит корпоративные сообщения
   - Источник: https://www.e-disclosure.ru/poisk-po-soobshheniyam
   - Тип: Регулятивные сообщения компаний

## 🏗️ Архитектура

### Структура файлов:

```
src/services/html_parser/
├── base_html_parser.py              # Базовый класс
├── forbes_parser.py                 # Forbes (существующий)
├── interfax_parser.py               # Interfax (существующий)
├── edisclosure_parser.py            # E-disclosure новости (новый)
├── moex_parser.py                   # MOEX (новый)
├── edisclosure_messages_parser.py   # E-disclosure сообщения (новый)
├── html_parser_service.py           # Сервис управления
└── __init__.py                      # Инициализация модуля
```

### Интеграция в CEG:

```
scripts/start_telegram_parser_ceg.py
├── Поддержка HTML источников
├── Batch обработка
├── NER анализ
├── MOEX линковка
└── Сохранение в Neo4j
```

## ⚙️ Конфигурация

### config/sources.yml:

```yaml
# E-disclosure новости
- code: e_disclosure
  name: E-disclosure
  kind: html
  base_url: https://www.e-disclosure.ru
  enabled: true
  trust_level: 10
  config:
    news_list_url: /vse-novosti
    max_articles: 50
    delay_between_requests: 1.0
    poll_interval: 1800  # 30 минут

# E-disclosure сообщения
- code: e_disclosure_messages
  name: E-disclosure сообщения
  kind: html
  base_url: https://www.e-disclosure.ru
  enabled: true
  trust_level: 10
  config:
    messages_url: /poisk-po-soobshheniyam
    max_messages: 100
    delay_between_requests: 2.0
    poll_interval: 3600  # 1 час

# MOEX
- code: moex
  name: MOEX (Московская биржа)
  kind: html
  base_url: https://www.moex.com
  enabled: true
  trust_level: 10
  config:
    news_list_url: /ru/news/
    max_articles: 30
    delay_between_requests: 1.0
    poll_interval: 2400  # 40 минут
```

## 🚀 Использование

### 1. Загрузка конфигурации:

```powershell
# Обновляем источники в базе данных
.\scripts\load_sources.py
```

### 2. Тестирование парсеров:

```powershell
# Тестируем новые парсеры
.\test_extended_parsers.ps1
```

### 3. Запуск полной системы:

```powershell
# Запускаем CEG с HTML источниками
.\start_ceg_parser.ps1
```

### 4. Индивидуальное тестирование:

```python
# Тестируем конкретный парсер
from Parser.src.services.html_parser.moex_parser import MOEXParser

parser = MOEXParser(source, session)
urls = await parser.get_article_urls(max_articles=10)
article = await parser.parse_article(urls[0])
```

## 🔧 API парсеров

### Базовые методы:

```python
class BaseHTMLParser:
    async def get_article_urls(self, max_articles: int) -> List[str]
    async def parse_article(self, url: str) -> Optional[Dict[str, Any]]
    def _is_news_url(self, url: str) -> bool
```

### Специфичные методы:

#### E-disclosure Parser:
```python
def _extract_content(self, soup: BeautifulSoup) -> str
def _extract_metadata(self, soup: BeautifulSoup, url: str) -> dict
```

#### MOEX Parser:
```python
def _extract_tags(self, soup: BeautifulSoup) -> List[str]
def _is_news_url(self, url: str) -> bool
```

#### E-disclosure Messages Parser:
```python
def _extract_title(self, soup: BeautifulSoup, url: str) -> str
def _extract_content(self, soup: BeautifulSoup) -> str
```

## 📊 Структура данных

### Стандартный формат статьи:

```python
{
    'title': 'Заголовок статьи',
    'content': 'Основной текст статьи...',
    'url': 'https://example.com/article',
    'source': 'moex.com',
    'date': '2024-01-15',
    'parser': 'moex',
    'metadata': {
        'document_type': 'news',
        'tags': ['финансы', 'биржа'],
        'language': 'ru',
        'event_id': '12345',  # для E-disclosure
        'is_corporate_message': True  # для сообщений
    }
}
```

## 🔍 Особенности парсеров

### E-disclosure Parser:
- ✅ Парсит новости и события
- ✅ Извлекает метаданные документов
- ✅ Определяет тип документа по URL
- ✅ Фильтрует служебные страницы

### MOEX Parser:
- ✅ Парсит финансовые новости
- ✅ Извлекает теги и категории
- ✅ Фильтрует рекламные тексты
- ✅ Определяет тип документа

### E-disclosure Messages Parser:
- ✅ Парсит корпоративные сообщения
- ✅ Извлекает EventId из URL
- ✅ Определяет тип сообщения
- ✅ Маркирует как регулятивный источник

## 🛠️ Troubleshooting

### Частые проблемы:

1. **Парсер не найден:**
   ```
   ❌ Парсер не найден для e_disclosure
   ```
   **Решение:** Проверьте регистр парсеров в `html_parser_service.py`

2. **URL не найдены:**
   ```
   ❌ URL статей не найдены
   ```
   **Решение:** Проверьте селекторы и доступность сайта

3. **Ошибка парсинга:**
   ```
   ❌ Не удалось спарсить статью
   ```
   **Решение:** Проверьте селекторы контента и структуру страницы

### Логирование:

```python
import logging
logger = logging.getLogger(__name__)

# Включить debug логирование
logging.getLogger('src.services.html_parser').setLevel(logging.DEBUG)
```

## 📈 Мониторинг

### Статистика парсеров:

```python
stats = parser_service.get_stats()
print(f"Источников обработано: {stats['sources_processed']}")
print(f"Статей обработано: {stats['total_articles_processed']}")
print(f"Ошибок парсинга: {stats['parsing_errors']}")
```

### Мониторинг в CEG:

```python
# В start_telegram_parser_ceg.py
self.total_stats = {
    "html_sources_processed": 0,
    "html_articles_processed": 0,
    "telegram_sources_processed": 0
}
```

## 🔄 Обновления

### Добавление нового парсера:

1. Создайте класс, наследующий от `BaseHTMLParser`
2. Добавьте в `parser_registry` в `html_parser_service.py`
3. Добавьте конфигурацию в `config/sources.yml`
4. Обновите `__init__.py`
5. Создайте тесты

### Пример:

```python
# Новый парсер
class NewSiteParser(BaseHTMLParser):
    def _is_news_url(self, url: str) -> bool:
        return '/news/' in url

# Регистрация
self.parser_registry = {
    'newsite': NewSiteParser,
    # ... другие парсеры
}
```

## 🎯 Следующие шаги

1. **Тестирование:** Запустите `test_extended_parsers.ps1`
2. **Интеграция:** Обновите источники через `load_sources.py`
3. **Запуск:** Используйте `start_ceg_parser.ps1`
4. **Мониторинг:** Следите за логами и статистикой

---

**Статус:** ✅ Реализовано и протестировано  
**Версия:** 1.0  
**Дата:** 2024-01-15
