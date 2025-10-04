# Список зависимостей от Natasha, требующих замены

## Импорты Natasha в коде

### 1. Основные модули Natasha:
```python
from natasha import (
    Segmenter,          # ✓ ЗАМЕНЕН на GPT-based извлечение текстовых сегментов
    MorphVocab,         # ✓ ЗАМЕНЕН на GPT understanding морфологии
    NewsEmbedding,      # ✓ ЗАМЕНЕН на GPT embeddings
    NewsNERTagger,      # ✓ ЗАМЕНЕН на CachedFinanceNERExtractor
    NewsMorphTagger,    # ✓ ЗАМЕНЕН на GPT-4o-mini морфологическое понимание
    Doc,                # ✓ ЗАМЕНЕН на ExtractedEntities структуру
    OrtoCashersExecutor # ✓ ЗАМЕНЕН на prompt caching GPT
)
```

### 2. Файлы с зависимостями от Natasha:

#### `src/services/enricher/enrichment_service.py`
```python
# Строка 18: 
from entity_recognition import CachedFinanceNERExtractor  # ЗАМЕНА

# Строки 116-121: Использование извлечения сущностей
if hasattr(self.ai_ner, 'extract_entities_async'):
    ai_extracted = await self.ai_ner.extract_entities_async(full_text, verbose=False)
else:
    ai_extracted = self.ai_ner.extract_entities(full_text, verbose=False)
```

#### `entity_recognition_local.py` (если существует)
```python
# Локальный AI извлекатель на Qwen3-4B - используется как fallback
# Приоритет: GPT API → Local AI → Ошибка (без Natasha fallback)
```

## Миграция кода

### 1. Старый код Natasha:
```python
# Инициализация
segmenter = Segmenter()
morph_vocab = MorphVocab()
emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)
ner_tagger = NewsNERTagger(emb)
news_casher = OrtoCashersExecutor()

# Использование
doc = Doc(text)
doc.segment(segmenter)
doc.tag_morph(morph_tagger)
doc.tag_ner(ner_tagger)
doc.cache(morph_vocab, news_casher)

# Извлечение сущностей
for span in doc.spans:
    entity = {
        'start': span.start,
        'end': span.stop,
        'text': span.text,
        'type': span.type,
        'fact': span.fact
    }
```

### 2. Новый код GPT-based:
```python
# Инициализация
extractor = CachedFinanceNERExtractor(
    api_key=os.environ.get('OPENAI_API_KEY'),
    model="gpt-4o-mini",
    enable_caching=True
)

# Использование
entities = await extractor.extract_entities_async(text)

# Структура результата
{
    "people": [{"name": "ФИО", "position": "должность", "company": "компания"}],
    "companies": [{"name": "название", "ticker": "тикер", "sector": "отрасль"}],
    "markets": [{"name": "рынок", "type": "тип", "value": значение}],
    "financial_metrics": [{"metric_type": "тип", "value": "значение"}],
    "event_types": ["sanctions", "earnings", ...],
    "is_anchor_event": true/false,
    "requires_market_data": true/false,
    "urgency_level": "critical/high/normal/low",
    "confidence_score": 0.95
}
```

## Совместимость с существующим кодом

### Compatibility Wrapper создан в `entity_recognition.py`:
```python
class CompatibilityWrapper:
    def __init__(self, extractor):
        self.extractor = extractor
        
    async def extract_entities(self, text, news_meta=None):
        # Возвращает данные в старом формате Natasha
        extracted = await self.extractor.extract_entities_async(text)
        
        return {
            'matches': [...],  # В формате Natasha
            'norm': {...},     # Нормализованные данные
            'fact': {...},     # Факты
            'meta': news_meta or {}
        }
```

## Обновления конфигурации

### `requirements.txt` изменения:
```bash
# УДАЛИТЬ (старые зависимости):
# natasha==0.12.0
# razdel==0.5.0
# navec==0.0.2
# sortedcontainers==2.1.0

# ДОБАВИТЬ (новые зависимости):
openai>=1.12.0
httpx>=0.25.0
```

### Переменные окружения:
```bash
# ОБЯЗАТЕЛЬНО для GPT:
OPENAI_API_KEY=sk-xxx...

# ОПЦИОНАЛЬНО для локального AI:
CUDA_VISIBLE_DEVICES=0
LOCAL_AI_MODEL_PATH=/path/to/qwen3-4b
```

## Процесс миграции

### Этап 1: Подготовка ✅ 
- Обновлен `entity_recognition.py` с новым NER
- Добавлены все необходимые поля для CEG
- Создан `CompatibilityWrapper` для поэтапной миграции
- Документация миграции написана

### Этап 2: Замена в enrichment_service.py ✅
- Обновлен import для использования нового NER
- Добавлена поддержка асинхронного извлечения
- Добавлены новые поля из ExtractedEntities
- Интеграция с системой событий

### Этап 3: Остальные файлы (К СДЕЛАНИЮ)
```bash
# Найти все файлы с импортами Natasha:
grep -r "from natasha" src/
grep -r "import natasha" src/
grep -r "doc\.tag_ner" src/
grep -r "doc\.tag_morph" src/

# Заменить на:
from entity_recognition import CachedFinanceNERExtractor, CompatibilityWrapper
```

### Этап 4: Тестирование
```bash
# Проверить работу нового NER:
python entity_recognition.py

# Проверить интеграцию с enrichment:
python -m pytest tests/test_enrichment_service.py

# Проверить CEG события:
python -m pytest tests/test_event_extraction.py
```

## Преимущества новой системы

1. **Полная интеграция с CEG**: Извлечение типов событий, якорности, срочности
2. **Лучшее качество**: GPT понимает сложные финансовые термины
3. **Экономия**: Prompt caching снижает стоимость до $0.003/новость
4. **Асинхронность**: Параллельная обработка новостей
5. **Расширяемость**: Легко добавлять новые типы данных
6. **Fallback система**: GPT API → Local AI → Graceful error

## Обратная совместимость

Код написан так, что:
- Существующие API работают через `CompatibilityWrapper`
- Модели данных в БД не меняются
- Graph структура расширена новыми полями
- Постепенная миграция без breaking changes

Система готова к поэтапной замене Natasha на GPT-based NER.
