# Migration Guide - Новая архитектура RADAR AI

## 📋 Что изменилось

### Старая структура → Новая структура

```
СТАРОЕ:                              НОВОЕ:
├── src/                             ├── core/
│   └── system/                      │   ├── database/       (Parser/src/core/)
│       ├── vdb.py                   │   ├── graph/          (Parser/src/graph_models.py)
│       ├── search.py                │   ├── nlp/            (entity_recognition.py)
│       └── LLM_final/               │   └── messaging/      (event_bus.py)
│                                    │
├── Parser/                          ├── services/
│   ├── entity_recognition.py        │   ├── aggregator/     (Parser/src/services/)
│   └── src/                         │   │   ├── telegram/
│       ├── core/                    │   │   ├── html/
│       ├── services/                │   │   ├── enrichment/
│       │   ├── telegram_parser/     │   │   ├── clustering/
│       │   ├── enricher/            │   │   └── outbox/
│       │   ├── events/              │   │
│       │   ├── outbox/              │   ├── ceg/           (CEG Engine)
│       │   └── moex/                │   │   ├── events/
│       ├── api/                     │   │   ├── causal/
│       └── graph_models.py          │   │   ├── importance/
│                                    │   │   ├── watchers/
├── requirements.txt (root)          │   │   ├── predictions/
├── Parser/requirements.txt          │   │   └── market/
                                     │   │
                                     │   └── rag/           (RAG System)
                                     │       ├── indexing/
                                     │       ├── search/
                                     │       └── generation/
                                     │
                                     ├── workers/           (фоновые задачи)
                                     ├── api/               (REST API)
                                     └── requirements.txt   (объединенный)
```

## 🔧 Таблица миграции импортов

### Core modules

| Старый импорт | Новый импорт |
|--------------|--------------|
| `from Parser.src.core.models import News` | `from core.database.models import News` |
| `from Parser.src.core.config import settings` | `from core.database.config import settings` |
| `from Parser.src.core.database import get_session` | `from core.database.database import get_session` |
| `from Parser.src.graph_models import GraphService` | `from core.graph.service import GraphService` |
| `from Parser.src.services.event_bus import EventBus` | `from core.messaging.event_bus import EventBus` |
| `from entity_recognition import ExtractedEntities` | `from core.nlp.entity_recognition import ExtractedEntities` |

### Services - Aggregator

| Старый импорт | Новый импорт |
|--------------|--------------|
| `from Parser.src.services.telegram_parser.parser import TelegramParser` | `from services.aggregator.telegram.parser import TelegramParser` |
| `from Parser.src.services.enricher.ner_extractor import NERExtractor` | `from services.aggregator.enrichment.ner_extractor import NERExtractor` |
| `from Parser.src.services.enricher.moex_linker import MOEXLinker` | `from services.aggregator.enrichment.moex_linker import MOEXLinker` |
| `from Parser.src.services.outbox.relay import OutboxRelay` | `from services.aggregator.outbox.relay import OutboxRelay` |
| `from Parser.src.services.ml.news_clustering import NewsClusterer` | `from services.aggregator.clustering.news_clustering import NewsClusterer` |

### Services - CEG

| Старый импорт | Новый импорт |
|--------------|--------------|
| `from Parser.src.services.events.event_extractor import EventExtractor` | `from services.ceg.events.event_extractor import EventExtractor` |
| `from Parser.src.services.events.cmnln_engine import CMNLNEngine` | `from services.ceg.causal.cmnln_engine import CMNLNEngine` |
| `from Parser.src.services.events.causal_chains_engine import CausalChainsEngine` | `from services.ceg.causal.causal_chains_engine import CausalChainsEngine` |
| `from Parser.src.services.events.enhanced_evidence_engine import EvidenceEngine` | `from services.ceg.causal.enhanced_evidence_engine import EvidenceEngine` |
| `from Parser.src.services.events.importance_calculator import ImportanceScoreCalculator` | `from services.ceg.importance.calculator import ImportanceScoreCalculator` |
| `from Parser.src.services.impact_calculator import ImpactCalculator` | `from services.ceg.importance.impact import ImpactCalculator` |
| `from Parser.src.services.covariance_service import CovarianceService` | `from services.ceg.importance.covariance import CovarianceService` |
| `from Parser.src.services.events.watchers import WatcherService` | `from services.ceg.watchers.watchers import WatcherService` |
| `from Parser.src.services.events.event_prediction import EventPredictor` | `from services.ceg.predictions.event_prediction import EventPredictor` |
| `from Parser.src.services.moex.moex_prices import MOEXPriceService` | `from services.ceg.market.moex.moex_prices import MOEXPriceService` |
| `from Parser.src.services.market_data_service import MarketDataService` | `from services.ceg.market.market_data_service import MarketDataService` |

### Services - RAG

| Старый импорт | Новый импорт |
|--------------|--------------|
| `from src.system.vdb import create_collection` | `from services.rag.indexing.indexer import create_collection` |
| `from src.download.downloader_functions import chunk_text` | `from services.rag.indexing.chunker import chunk_text` |
| `from src.system.search import hybrid_search` | `from services.rag.search.search import hybrid_search` |
| `from src.system.engine import RAGPipeline` | `from services.rag.search.engine import RAGPipeline` |
| `from src.system.LLM_final.main import generate_article` | `from services.rag.generation.LLM_final.main import generate_article` |

### API

| Старый импорт | Новый импорт |
|--------------|--------------|
| `from Parser.src.api.main import app` | `from api.main import app` |
| `from Parser.src.api.endpoints.news import router` | `from api.endpoints.news import router` |

## 🚀 Как использовать

### 1. Автоматическое обновление импортов

```bash
python update_imports.py
```

Скрипт автоматически обновит импорты во всех файлах в `services/`, `workers/`, `api/`.

### 2. Ручное обновление

Если автоматический скрипт пропустил файл:

1. Откройте файл
2. Найдите импорты с `Parser.src` или `src.`
3. Замените согласно таблице выше
4. Сохраните

### 3. Проверка

```bash
# Найти оставшиеся старые импорты
grep -r "from Parser.src" services/ workers/ api/
grep -r "from src\." services/ workers/ api/
```

## 📦 Requirements

Объединенный `requirements.txt` содержит:

```ini
# === Core Dependencies ===
python-dotenv
pydantic
pydantic-settings

# === Database ===
sqlalchemy
asyncpg
alembic

# === Graph Database ===
neo4j

# === Messaging ===
aio-pika
redis

# === Telegram ===
telethon
cryptg

# === Web Framework ===
fastapi
uvicorn[standard]
httpx

# === NLP & NER ===
natasha
pymorphy3

# === RAG & ML ===
weaviate-client
llama-index
openai
sentence-transformers
torch

# === Development ===
pytest
pytest-asyncio
```

## 🏃 Запуск системы

### Старый способ:
```bash
cd Parser
python scripts/start_telegram_parser.py
python scripts/start_enricher.py
python scripts/start_api.py
```

### Новый способ:
```bash
# Из корня проекта
python workers/telegram_worker.py
python workers/enrichment_worker.py
python workers/outbox_worker.py
python -m uvicorn api.main:app --reload
```

Или через Docker:
```bash
docker compose up
```

## ⚠️ Важные замечания

1. **НЕ удаляйте** старые `src/` и `Parser/src/` до тестирования!
2. **Обновите импорты** во всех файлах перед запуском
3. **Проверьте** что все тесты проходят
4. **Обновите** `.env` файл (путей больше не нужно)

## 🧪 Тестирование

После миграции импортов:

```bash
# Проверить импорты
python -c "from core.database.models import News; print('OK')"
python -c "from services.ceg.events.event_extractor import EventExtractor; print('OK')"
python -c "from services.rag.search.engine import RAGPipeline; print('OK')"

# Запустить тесты
pytest tests/
```

## 📝 Чеклист миграции

- [ ] Обновить импорты (run `update_imports.py`)
- [ ] Обновить requirements (`pip install -r requirements.txt`)
- [ ] Обновить миграции БД (если нужно)
- [ ] Протестировать Parser pipeline
- [ ] Протестировать CEG pipeline
- [ ] Протестировать RAG pipeline
- [ ] Обновить документацию
- [ ] Удалить старые src/, Parser/src/ (ПОСЛЕ тестирования!)
