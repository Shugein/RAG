# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Financial News Aggregator** system that collects, enriches, and publishes Russian financial news with entity extraction, company linking, and topic classification. The system parses Telegram channels, filters spam/ads, extracts entities (companies, metrics, dates), links companies to MOEX tickers, and publishes enriched news via RabbitMQ.

## High-Level Architecture

The system follows a **multi-service microservices architecture** with transactional outbox pattern for reliable event publishing:

1. **Telegram_Parser Service** ([src/services/telegram_parser/](src/services/telegram_parser/))
   - Connects to Telegram via Telethon
   - Parses messages from configured channels in [config/sources.yml](config/sources.yml)
   - Applies multi-level anti-spam filtering using rules from [config/ad_rules.yml](config/ad_rules.yml)
   - Stores raw news in PostgreSQL
   - Deduplicates by content hash

2. **Enricher Service** ([src/services/enricher/](src/services/enricher/))
   - Reads new/unenriched news from database
   - Extracts entities via Natasha NLP (Russian language):
     - Organizations, persons, locations
     - Dates, money amounts, percentages
     - Financial metrics (amounts with units, reporting periods)
   - Links companies to MOEX securities via Algopack API
   - Classifies topics (macro, oil_gas, metals, banks, etc.)
   - Updates news records with enrichment data

3. **Outbox Relay Service** ([src/services/outbox/](src/services/outbox/))
   - Implements transactional outbox pattern
   - Polls `outbox` table for pending events
   - Publishes events to RabbitMQ exchange
   - Handles retries with exponential backoff
   - Ensures at-least-once delivery guarantees

4. **REST API** ([src/api/main.py](src/api/main.py))
   - FastAPI application
   - Provides news search and filtering endpoints
   - Supports full-text search, date range, ticker, topic filters
   - Returns enriched data (entities, companies, topics)
   - Serves image bytes from database

## Technology Stack

- **Python 3.11+**
- **Telethon** - Telegram MTProto API client
- **SQLAlchemy 2.0** - Async ORM with PostgreSQL
- **Alembic** - Database migrations
- **FastAPI** - REST API framework
- **PostgreSQL** - Primary data store with JSONB and full-text search
- **Neo4j** - Graph database for relationships (companies, news, instruments, markets)
- **RabbitMQ** - Message broker for event publishing
- **Natasha** - Russian NLP library for NER extraction
- **Algopack API** - MOEX securities data provider
- **Pillow** - Image processing and deduplication

## Database Schema

Key tables defined in [src/core/models.py](src/core/models.py):

- **sources** - News sources (Telegram channels, HTML sites) with trust_level for spam filtering
- **news** - News articles with content hash deduplication, full-text search support
- **images** - Deduplicated images (SHA-256) stored as BYTEA with thumbnails
- **entities** - Extracted entities (ORG, PERSON, DATE, MONEY, PCT, AMOUNT, PERIOD, UNIT, LOC)
- **linked_companies** - Companies linked to MOEX securities (secid, isin, board)
- **topics** - News topic classifications (macro, oil_gas, metals, banks, retail, etc.)
- **sector_constituents** - MOEX sector/index constituents for company matching
- **company_aliases** - Company name aliases for faster linking
- **outbox** - Transactional outbox for event publishing with retry logic
- **parser_states** - Parser state tracking (last message ID, backfill status, error counts)

Relationships: News has many entities, linked_companies, topics, and images. All use UUID primary keys. Many-to-many relationship between news and images via `news_images` association table.

**Graph Schema** (Neo4j) defined in [src/graph_models.py](src/graph_models.py):
- **Market** - Stock markets (MOEX, NYSE, NASDAQ)
- **Instrument** - Securities (equity, bond, future, option, token) with secid, isin, board
- **Company** - Issuers with full_name, short_name, inn
- **Sector** - Industry sectors
- **News** - News nodes with type (one_company, market, regulatory) and subtype (earnings, guidance, m&a, etc.)
- **Relationships**: Company-[:ISSUES]->Instrument, Instrument-[:TRADED_ON]->Market, Company-[:IN_SECTOR]->Sector, News-[:MENTIONS]->Company/Instrument, News-[:IMPACTS]->Instrument (with price_impact, volume_impact, sentiment)

## Anti-Spam System

Multi-level spam detection in [src/services/telegram_parser/antispam.py](src/services/telegram_parser/antispam.py):

- **Rule-based scoring** with configurable weights from [config/ad_rules.yml](config/ad_rules.yml)
- **Hashtag detection** (#реклама, #promo, #ad, etc.) - weight 2.0-3.0
- **Keyword matching** (казино, ставки, промокод, скидка, etc.) - weight 1.5-5.0
- **URL analysis** (UTM parameters, shorteners, suspicious TLDs) - weight 1.5-2.0
- **Structural checks** (many URLs, forwarded messages, short text with links) - weight 1.5-3.0
- **Trust levels** - Higher threshold for trusted sources (trust_level 8+)
- **Whitelisted domains** - Official sources bypass ad detection (cbr.ru, moex.com, rbc.ru, etc.)

Score >= threshold → message filtered as ad. Default threshold: 5.0, trusted sources: 8.0.

## Entity Extraction & Linking

**NER Extraction** (Natasha-based):
- Organizations → normalized name → linked to MOEX securities
- Dates, periods (1П2025, Q3 2024, 9М2025)
- Money amounts with currency
- Percentages with basis (YoY, QoQ, MoM)
- Amounts with units (тонн, баррелей, млн руб)

**Company Linking** (Algopack API):
1. Normalize org name (remove legal forms, quotes, common words)
2. Check local alias cache/database
3. Search via Algopack API with fuzzy matching
4. Boost scored for traded securities and primary boards
5. Save aliases for future matches
6. Check trading status for linked companies

**Topic Classification** (keyword-based):
- Multiple topics per news (max 3 returned)
- Topics: macro, budget, oil_gas, metals, banks, retail, telecom, energy, transport, realestate, agriculture, dividends, ipo, bonds
- Company-specific topics boosted by entity matches

## Environment Setup

Required environment variables (create `.env` file in project root):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb

# Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
NEO4J_DATABASE=neo4j

# RabbitMQ
RABBITMQ_URL=amqp://admin:admin123@localhost:5672/

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram (get from my.telegram.org)
TELETHON_API_ID=your_api_id
TELETHON_API_HASH=your_api_hash
TELETHON_SESSION_NAME=news_parser
TELETHON_PHONE=+7xxxxxxxxxx

# Algopack API
ALGOPACK_API_KEY=your_api_key
ALGOPACK_BASE_URL=https://api.algopack.com/v1

# Logging & Metrics
LOG_LEVEL=INFO
LOG_FORMAT=json
# METRICS_PORT=9090  # Удален вместе с Prometheus

# Development
DEBUG=false
```

See [src/core/config.py](src/core/config.py) for complete settings structure with Pydantic validation.

## Running Services

### Windows/PowerShell (Primary Development Environment)

**Quick Start:**
```powershell
# 1. Setup (first time only)
.\setup.ps1

# 2. Configure Telegram credentials
.\setup_telegram.ps1

# 3. Start development environment
.\start_dev.ps1
```

**Start Development Mode** (recommended):
```powershell
.\start_dev.ps1
```
Starts infrastructure (PostgreSQL, RabbitMQ, Redis, Neo4j) in Docker and application services locally in separate windows for easy debugging.

**Start Full Docker Mode:**
```powershell
.\start_full.ps1
```
All services in Docker containers.

**Stop Services:**
```powershell
.\stop_dev.ps1      # Stop development mode
.\stop_full.ps1     # Stop full Docker mode
```

**Utilities:**
```powershell
.\check_health.ps1              # Check system health
.\view_logs.ps1                 # View all logs
.\view_logs.ps1 -Service api    # View specific service logs
.\reset_project.ps1             # Full project reset (careful!)
```

**Neo4j Management:**
```powershell
.\start_neo4j.ps1   # Start Neo4j container
.\stop_neo4j.ps1    # Stop Neo4j container
.\view_neo4j_data.ps1  # Query Neo4j data
```

### Linux/macOS (Bash)

**Start infrastructure and services:**
```bash
./setup.sh          # First time setup
./start_dev.sh      # Start development mode
```

### Docker Setup (Cross-Platform)

Start all infrastructure services:
```bash
docker-compose -f docker/docker-compose.yml up -d postgres rabbitmq redis neo4j
```

Start individual application services:
```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Or start individual services
docker-compose -f docker/docker-compose.yml up -d telegram-parser
docker-compose -f docker/docker-compose.yml up -d enricher
docker-compose -f docker/docker-compose.yml up -d outbox-relay
docker-compose -f docker/docker-compose.yml up -d api

# View logs
docker-compose -f docker/docker-compose.yml logs -f telegram-parser
```

### Manual Setup (Development)

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Database migrations:**
```bash
# Run PostgreSQL migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Setup Neo4j schema
python scripts/setup_neo4j.py
```

**Load initial data:**
```bash
python scripts/load_sources.py  # Load news sources from config/sources.yml
```

**Start services manually:**
```bash
# Telegram_Parser
python scripts/start_telegram_parser.py

# Enricher Service
python scripts/start_enricher.py

# Outbox Relay
python scripts/start_outbox_relay.py

# REST API
python scripts/start_api.py
# Or with uvicorn:
uvicornParser.src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Access Services

- **API**: http://localhost:8000 (docs at http://localhost:8000/docs)
- **RabbitMQ Management**: http://localhost:15672 (admin/admin123)
- **Neo4j Browser**: http://localhost:7474 (neo4j/password123)

## API Endpoints

Endpoints defined in [src/api/endpoints/](src/api/endpoints/):

**News** ([news.py](src/api/endpoints/news.py)):
- `GET /news` - List news with filters (source, date_from, date_to, q, ticker, topic, include_enrichment, limit, offset)
- `GET /news/{news_id}` - Get single news item with full enrichment

**Images** ([images.py](src/api/endpoints/images.py)):
- `GET /images/{image_id}` - Get image metadata
- `GET /images/{image_id}/bytes` - Get image binary data

**Sources** ([sources.py](src/api/endpoints/sources.py)):
- `GET /sources` - List configured sources
- `GET /sources/{source_id}` - Get single source

**Jobs** ([jobs.py](src/api/endpoints/jobs.py)) (if implemented):
- Manual trigger endpoints for parsing/enrichment jobs

**Health** ([health.py](src/api/endpoints/health.py)):
- `GET /health` - Health check with service status

**Metrics**:
- `GET /metrics` - Prometheus metrics (mounted at root level)

## Key Implementation Details

**Deduplication Strategy:**
- Content-based: SHA-256 of title+text stored in `hash_content`
- Image-based: SHA-256 of image bytes, single storage for duplicates
- External ID: Composite unique constraint on (source_id, external_id)

**Transactional Outbox Pattern:**
- Events created in same transaction as news records
- Relay polls with `SELECT ... FOR UPDATE SKIP LOCKED` for concurrency
- Exponential backoff for failed events (max 3 retries)
- Events include full news data + enrichment in JSON payload

**Parser State Management:**
- Tracks last processed message ID per source
- Supports backfill mode (historical data up to 1 year)
- Tracks errors and retry counts
- Marks backfill completion

**Image Storage:**
- Images stored as BYTEA in PostgreSQL (not ideal for production, consider S3)
- SHA-256 deduplication before storage
- Thumbnails generated for large images
- Many-to-many relationship (news can share images)

**Graph Database Usage:**
- Dual-write pattern: PostgreSQL for transactional data, Neo4j for relationships
- Graph queries enable: company impact analysis, sector correlation, news clustering
- Market impact tracking with price/volume/sentiment scores
- Company-instrument-market hierarchy for multi-level analysis

## Project Structure

```
src/
├── core/               # Core domain models and configuration
│   ├── models.py       # SQLAlchemy ORM models
│   ├── config.py       # Pydantic settings
│   └── database.py     # Database engine and session management
├── services/           # Business logic services
│   ├── telegram_parser/  # Telegram message parsing
│   │   ├── client.py     # Telethon client setup
│   │   ├── parser.py     # Message parsing logic
│   │   └── antispam.py   # Ad detection and filtering
│   ├── enricher/         # News enrichment
│   │   ├── ner_extractor.py      # Natasha NER extraction
│   │   ├── moex_linker.py        # Company-to-MOEX linking
│   │   └── topic_classifier.py   # Topic classification
│   ├── outbox/           # Outbox pattern implementation
│   │   ├── relay.py      # Outbox polling and relay
│   │   └── publisher.py  # RabbitMQ publishing
│   └── storage/          # Data access layer
│       ├── news_repository.py  # News CRUD operations
│       └── image_service.py    # Image storage and deduplication
├── api/                # REST API
│   ├── main.py         # FastAPI app setup
│   └── endpoints/      # API route handlers
└── utils/              # Utilities (logging, metrics, text processing)

config/
├── sources.yml         # News sources configuration
└── ad_rules.yml        # Anti-spam rules configuration

migrations/             # Alembic database migrations
└── versions/           # Migration version files

docker/                 # Docker configuration
├── docker-compose.yml  # Multi-service orchestration
└── Dockerfile.*        # Service-specific Dockerfiles

scripts/                # Service startup scripts
└── start_outbox_relay.py
```

## Testing & Utilities

**Test Scripts** (in [scripts/](scripts/)):
```bash
# Test MOEX company auto-search
python scripts/test_moex_auto_search.py

# Test topic classifier
python scripts/test_topic_classifier.py
python scripts/test_topic_classifier_simple.py

# Test Neo4j connection
python scripts/test_neo4j_connection.py

# Test graph consistency
python scripts/test_graph_consistency.py

# Verify Telegram sources configuration
python scripts/verify_telegram_sources.py
```

**Utility Scripts:**
```bash
# Fix encoding issues in database
python scripts/fix_encoding.py

# Cleanup graph duplicates
python scripts/cleanup_graph_duplicates.py
```

## Development Practices

When implementing new features:
- **Async patterns**: Always use async/await (SQLAlchemy 2.0 async, aio-pika, httpx)
- **Event sourcing**: Add outbox events for domain events requiring external notification
- **Dual-write**: When modifying company/news data, update both PostgreSQL and Neo4j
- **Logging**: Use structlog for structured logging with context
- **Metrics**: Add Prometheus metrics for monitoring
- **Database**: Use Alembic for schema changes; models auto-validate with Pydantic
- **Graph schema**: Update Neo4j constraints/indexes via [scripts/setup_neo4j.py](scripts/setup_neo4j.py)
- **Testing**: Tests not yet implemented (tests/ directory exists but empty)
- **Code quality**: Project has black, flake8, mypy in requirements.txt for linting

## Common Issues & Solutions

**PowerShell Execution Policy:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Port Conflicts:**
```powershell
# Check port usage
netstat -ano | findstr :8000
netstat -ano | findstr :5432
netstat -ano | findstr :7687

# Kill process by PID
taskkill /PID <PID> /F
```

**Database Issues:**
```powershell
# Check PostgreSQL logs
docker logs news-postgres

# Restart PostgreSQL
docker restart news-postgres

# Check Neo4j logs
docker logs news-neo4j
```

**Encoding Issues:**
- Run `python scripts/fix_encoding.py` to fix UTF-8 encoding in database
- Ensure all files are saved with UTF-8 encoding (not Windows-1251)

**Graph Duplicates:**
- Run `python scripts/cleanup_graph_duplicates.py` to remove duplicate nodes
- Run `python scripts/test_graph_consistency.py` to verify graph integrity