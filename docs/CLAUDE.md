# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**RADAR AI** - Unified financial news intelligence platform combining:

1. **News Aggregator** - Multi-source collection (Telegram, HTML) with anti-spam, NER, MOEX linking
2. **CEG Engine** - Causal Event Graph + CMNLN for market impact prediction
3. **RAG System** - Retrieval-Augmented Generation for article synthesis

**Purpose**: Ingest Russian financial news → Extract events → Build causal graphs → Predict market impacts → Generate articles

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RADAR AI Pipeline                         │
└─────────────────────────────────────────────────────────────────┘

1. INGESTION (services/aggregator/)
   Telegram + HTML → RabbitMQ: news.raw
              ↓
2. ENRICHMENT (services/aggregator/enrichment/)
   NER (Natasha) + MOEX Linking + Topics → PostgreSQL
              ↓
3. CEG ENGINE (services/ceg/)
   Event Extraction (GPT-5/Qwen) → Anchors/Evidence (BFS≤3)
   → CMNLN (causality scoring) → Importance (5 components)
   → Predictions + Watchers → Neo4j Graph
              ↓
4. RAG INDEXING (services/rag/indexing/)
   News + CEG metadata → Chunk + Vectorize → Weaviate
              ↓
5. RAG GENERATION (services/rag/search/ + generation/)
   Hybrid Search (Vector + BM25) → Reranking (BGE)
   → Hotness weighting → GPT-5 Article Generation
```

## Technology Stack

**Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Alembic
**Databases**: PostgreSQL 15, Neo4j 5, Redis 7, Weaviate 1.33
**Message Queue**: RabbitMQ 3.12
**NLP/AI**: Natasha, OpenAI GPT-5, Qwen3-4B, sentence-transformers, llama-index
**Telegram**: Telethon, cryptg
**Market Data**: MOEX ISS API, Algopack API
**Infrastructure**: Docker + Compose

## Code Organization

```
RAG/
├── core/                           # Shared modules
│   ├── database/                   # PostgreSQL ORM
│   │   ├── models.py              # News, Events, Entities, Sources
│   │   ├── database.py            # Session management
│   │   └── config.py              # Pydantic settings
│   ├── graph/                     # Neo4j service
│   │   └── service.py             # GraphService, EventNode, CAUSES/PRECEDES
│   ├── nlp/                       # NLP utilities
│   │   └── entity_recognition.py  # GPT-5-nano entity extraction
│   └── messaging/                 # Event bus
│       └── event_bus.py           # RabbitMQ abstraction
│
├── services/                       # Business logic
│   ├── aggregator/                # News collection + enrichment
│   │   ├── telegram/              # Telethon parser + anti-spam
│   │   ├── html/                  # Site parsers (Forbes, Interfax, MOEX)
│   │   ├── enrichment/            # NER + MOEX linking + topics
│   │   ├── clustering/            # News clustering
│   │   └── outbox/                # Transactional outbox → RabbitMQ
│   │
│   ├── ceg/                       # Causal Event Graph engine
│   │   ├── events/                # Event extraction from news
│   │   │   └── event_extractor.py # GPT-5/Qwen event extraction
│   │   ├── causal/                # Causality analysis
│   │   │   ├── cmnln_engine.py    # CMNLN scoring
│   │   │   ├── causal_chains_engine.py  # Build cause-effect chains
│   │   │   └── enhanced_evidence_engine.py  # Evidence discovery (BFS≤3)
│   │   ├── importance/            # Event importance scoring
│   │   │   ├── calculator.py      # W1*Novelty + W2*Burst + W3*Credibility + ...
│   │   │   ├── impact.py          # Price impact (AR/CAR, vol_spike)
│   │   │   └── covariance.py      # Correlation analysis
│   │   ├── watchers/              # Market watchers (L0/L1/L2)
│   │   │   └── watchers.py        # Monitor market reactions
│   │   ├── predictions/           # Event predictions
│   │   │   └── event_prediction.py # Future event generation
│   │   └── market/                # Market data services
│   │       ├── moex/              # MOEX ISS API
│   │       └── market_data_service.py
│   │
│   └── rag/                       # Retrieval-Augmented Generation
│       ├── indexing/              # Weaviate indexing
│       │   ├── indexer.py         # Index news + CEG metadata
│       │   └── chunker.py         # Text chunking + lemmatization
│       ├── search/                # Hybrid search
│       │   ├── search.py          # Vector + BM25 + Reranking
│       │   └── engine.py          # RAG pipeline orchestration
│       └── generation/            # Article generation
│           └── LLM_final/         # GPT-5 generation + prompts
│
├── workers/                        # Background tasks
│   ├── telegram_worker.py         # Telegram polling
│   ├── enrichment_worker.py       # NER + enrichment
│   ├── outbox_worker.py           # Event publishing
│   └── html_parser_worker.py      # HTML parser worker
│
├── api/                            # REST API
│   ├── main.py                    # FastAPI app
│   └── endpoints/                 # API routes
│       ├── news.py                # News endpoints
│       ├── ceg.py                 # CEG/events endpoints
│       ├── importance.py          # Importance scores
│       └── watchers.py            # Watchers management
│
├── scripts/                        # Utility scripts
│   ├── setup_neo4j.py             # Neo4j schema setup
│   ├── load_sources.py            # Load news sources
│   ├── cleanup_graph_duplicates.py # Remove duplicates
│   ├── test_*.py                  # Testing scripts
│   ├── init.sql                   # PostgreSQL initialization
│   └── README.md                  # Scripts documentation
│
├── docs/                           # Project documentation
│   ├── README.md                  # Documentation index
│   ├── CEG_*.md                   # CEG engine guides
│   ├── *_SUMMARY.md               # Implementation summaries
│   ├── *_GUIDE.md                 # Integration guides
│   └── CLAUDE_OLD.md              # Legacy documentation
│
├── migrations/                     # Alembic migrations
├── docker-compose.yml             # Multi-service orchestration
├── requirements.txt               # All dependencies
├── MIGRATION_GUIDE.md             # Refactoring guide
└── CLAUDE.md                      # This file
```

## Environment Setup

Create `.env` file in project root:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb

# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j

# Redis
REDIS_URL=redis://localhost:6379/0

# RabbitMQ
RABBITMQ_URL=amqp://admin:admin123@localhost:5672/

# Telegram (get from my.telegram.org)
TELETHON_API_ID=your_api_id
TELETHON_API_HASH=your_api_hash
TELETHON_SESSION_NAME=news_parser
TELETHON_PHONE=+7xxxxxxxxxx

# Algopack API (MOEX data)
ALGOPACK_API_KEY=your_api_key
ALGOPACK_BASE_URL=https://api.algopack.com/v1

# OpenAI (for entity extraction and generation)
API_KEY=sk-your-openai-api-key
API_KEY_2=sk-your-openai-api-key-2
OPENAI_MODEL=gpt-5
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Weaviate (RAG)
WEAVIATE_URL=http://localhost:8083

# Feature Flags
ENABLE_TELEGRAM=true
ENABLE_HTML_PARSER=true
ENABLE_ENRICHMENT=true
ENABLE_CEG=true
ENABLE_WATCHERS=true
ENABLE_PREDICTIONS=true

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Running the System

### Docker Compose (Recommended)

```bash
# Start all infrastructure
docker compose up -d

# Services started:
# - PostgreSQL (5432)
# - Neo4j (7474 browser, 7687 bolt)
# - RabbitMQ (5672, 15672 management)
# - Redis (6379)
# - Weaviate (8083)
# - Text2vec-transformers (8081, GPU)
# - BGE-reranker (8082, GPU)
```

### Database Setup

```bash
# Run PostgreSQL migrations
alembic upgrade head

# Setup Neo4j schema
python scripts/setup_neo4j.py

# Load news sources from config
python scripts/load_sources.py
```

### Start Workers

```bash
# In separate terminals (or use supervisor/systemd)
python workers/telegram_worker.py        # Telegram parsing
python workers/enrichment_worker.py      # NER + enrichment
python workers/outbox_worker.py          # Event publishing
```

### Start API

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Access:
- API Docs: http://localhost:8000/docs
- RabbitMQ UI: http://localhost:15672 (admin/admin123)
- Neo4j Browser: http://localhost:7474 (neo4j/password123)

## Common Commands

### Database

```bash
# PostgreSQL migrations
alembic upgrade head                        # Apply migrations
alembic revision --autogenerate -m "desc"   # Create new migration

# Neo4j management
python scripts/setup_neo4j.py              # Create constraints/indexes
python scripts/clear_neo4j_data.py         # Clear all graph data
python scripts/cleanup_graph_duplicates.py # Remove duplicates
```

### Testing

```bash
# CEG system
python Parser/test_ceg_simple.py           # Basic CEG tests
python Parser/demo_ceg_pipeline.py         # Full CEG pipeline

# NER & Linking
python scripts/test_moex_auto_search.py
python scripts/test_topic_classifier.py

# Graph
python scripts/test_neo4j_connection.py
python scripts/test_graph_consistency.py
```

### RAG System

```bash
# Check Weaviate collection
python src/download/check_collection.py

# Create/populate vector DB
python services/rag/indexing/indexer.py

# Run hybrid search + generation
python services/rag/search/engine.py
```

## API Endpoints

**News API** (port 8000):
- `GET /news` - List news (filters: source, date_from/to, q, ticker, topic)
- `GET /news/{id}` - Single news with full enrichment
- `GET /sources` - List news sources
- `GET /images/{id}/bytes` - Get image data
- `GET /health` - System health check

**CEG API**:
- `GET /ceg/events` - List events with filters
- `GET /ceg/events/{id}` - Event details
- `GET /ceg/events/{id}/causal-context` - Causal predecessors/successors
- `GET /ceg/events/{id}/causal-chains` - Full cause-effect chains
- `GET /ceg/events/{id}/similar` - Similar events
- `GET /ceg/anchor-events` - Canonical event prototypes
- `GET /ceg/stats` - CEG statistics

**Watchers API**:
- `GET /watchers` - Active watchers
- `POST /watchers` - Create watcher
- `DELETE /watchers/{id}` - Remove watcher

## Key Implementation Details

### CEG Pipeline (from TZ)

**1. Event Extraction** (`services/ceg/events/event_extractor.py`):
- GPT-5 API or Qwen3-4B-Instruct (fallback)
- Dual-pass: quick local NER + GPT verification
- Output: events[type, attrs, ts, targets]

**2. Anchors & Evidence** (`services/ceg/causal/`):
- Find top-k anchor events by embedding similarity
- BFS≤3 between anchor sets
- Select ≤3 Evidence Events
- Build CLG (Causal Link Graph)

**3. CMNLN Scoring** (`services/ceg/causal/cmnln_engine.py`):
- Domain priors (cause→effect rules with confidence)
- Text markers ("из-за", "привело к", "вследствие")
- Conditional probabilities with antecedent awareness
- Output: p_chain, conf_total = W1*conf_prior + W2*conf_text + W3*conf_market

**4. Importance Calculation** (`services/ceg/importance/calculator.py`):
```
Importance = W1*Novelty + W2*Burst + W3*Credibility + W4*Breadth + W5*PriceImpact
```
- Novelty: semantic novelty (embedding distance)
- Burst: Hawkes process + Kleinberg burst detection
- Credibility: source quality (whitelist/graylist/blacklist)
- Breadth: n_tickers, n_sectors, n_countries
- PriceImpact: AR/CAR from event study

**5. Watchers** (`services/ceg/watchers/watchers.py`):
- L0: no watcher (prediction only)
- L1: short windows (15m/60m) for top targets
- L2: full windows (15m/60m/1d/5d) + correlates (depth≤2)
- Triggers: |ΔP| ≥ 1-1.5% and |z| ≥ 2

**6. Neo4j Graph** (`core/graph/service.py`):
- Nodes: News, Event, AnchorEvent, Company, Instrument, Sector
- Edges: PRECEDES, CAUSES (kind, sign, expected_lag, conf_*), AFFECTS, ALIGNS_TO, EVIDENCE_OF

### RAG Pipeline

**1. Indexing** (`services/rag/indexing/`):
- Load news from PostgreSQL
- Extract entities via GPT-5-nano (`core/nlp/entity_recognition.py`)
- Chunk text (800 chars, 200 overlap)
- Lemmatize for BM25
- **Enrich with CEG metadata** (importance, causal_chains, predicted_events)
- Index in Weaviate with GPU vectorization

**2. Search** (`services/rag/search/search.py`):
- Hybrid: `alpha × vector_score + (1-alpha) × bm25_score`
- Reranking: BGE-reranker-v2-m3
- Hotness adjustment: `final = 0.7 × rerank + 0.3 × hotness` (CEG importance!)

**3. Generation** (`services/rag/generation/LLM_final/`):
- GPT-5 structured output
- Formats: social_post (280w), article_draft (500w), alert
- Outputs: headline, key_points, hashtags, visual ideas

### Anti-Spam System

Multi-level scoring (`services/aggregator/telegram/antispam.py`):
- Rule-based weights from `config/ad_rules.yml`
- Hashtags (#реклама, #promo): 2.0-3.0
- Keywords (казино, ставки): 1.5-5.0
- URLs (UTM params, shorteners): 1.5-2.0
- Trusted sources: higher threshold (8.0 vs 5.0)

## Development Practices

**Async everywhere**: All SQLAlchemy, HTTP, I/O use async/await
**Dual-write pattern**: Updates go to both PostgreSQL and Neo4j
**Event sourcing**: Domain events via transactional outbox
**Structured logging**: Use structlog with context
**Migrations**: Always use Alembic for schema changes

**Import conventions** (after refactoring):
```python
# Core modules
from core.database.models import News, Event
from core.graph.service import GraphService
from core.nlp.entity_recognition import ExtractedEntities
from core.messaging.event_bus import EventBus

# Services
from services.aggregator.telegram.parser import TelegramParser
from services.ceg.events.event_extractor import EventExtractor
from services.ceg.importance.calculator import ImportanceScoreCalculator
from services.rag.search.engine import RAGPipeline
```

## Migration Notes

**⚠️ Recent Refactoring**: Project structure was reorganized on 2025-11-09.

- Old `Parser/src/` → `services/aggregator/` + `services/ceg/`
- Old `src/system/` → `services/rag/`
- Shared code → `core/`
- Scripts → `workers/`

**See `MIGRATION_GUIDE.md` for detailed migration instructions.**

If you see old imports like `from Parser.src.core.models`, they should be updated to `from core.database.models`. Run `python update_imports.py` to auto-fix.

## Important Files

**Configuration**:
- `core/database/config.py` - Pydantic settings
- `config/sources.yml` - News sources
- `config/ad_rules.yml` - Anti-spam rules

**Key Models**:
- `core/database/models.py` - News, Events, Entities, Sources (PostgreSQL)
- `core/graph/service.py` - EventNode, CAUSES, PRECEDES (Neo4j)

**Main Pipelines**:
- `services/aggregator/telegram/parser.py` - Telegram ingestion
- `services/ceg/events/event_extractor.py` - Event extraction
- `services/ceg/causal/cmnln_engine.py` - Causality scoring
- `services/rag/search/engine.py` - RAG pipeline

## Troubleshooting

**Import errors**: Run `python update_imports.py` to fix old imports
**Port conflicts**: Check with `netstat -ano | findstr :8000` (Windows)
**Encoding issues**: Run `python scripts/fix_encoding.py`
**Graph duplicates**: Run `python scripts/cleanup_graph_duplicates.py`
**Weaviate not starting**: Check GPU driver, increase healthcheck `start_period`

## Documentation

Detailed documentation is available in the `docs/` directory:
- **Quick Start Guides**: CEG setup, PowerShell setup
- **Architecture**: Implementation notes, project structure
- **CEG Engine**: Implementation summaries, integration guides
- **Parsers**: Telegram, HTML parser guides
- **Maintenance**: Migration guides, fix summaries

See `docs/README.md` for a complete index.

## Utility Scripts

All utility scripts are in the `scripts/` directory:
- **Neo4j**: setup, backup/restore, cleanup
- **Database**: initialization, source loading
- **Testing**: topic classifier, MOEX search, graph consistency
- **Maintenance**: encoding fixes

See `scripts/README.md` for detailed usage.
