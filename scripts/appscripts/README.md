# Utility Scripts

This directory contains utility scripts for database setup, testing, and maintenance.

## Neo4j Management

### Setup & Configuration
- **setup_neo4j.py** - Initialize Neo4j schema (constraints, indexes, initial data)
- **test_neo4j_connection.py** - Test Neo4j connectivity and authentication

### Backup & Restore
- **export_neo4j_dump.py** - Export Neo4j database to dump file
- **import_neo4j_dump.py** - Import Neo4j database from dump file

### Data Management
- **clear_neo4j_data.py** - Clear all data from Neo4j (WARNING: destructive)
- **cleanup_graph_duplicates.py** - Remove duplicate nodes and relationships
- **test_graph_consistency.py** - Verify graph data integrity

## Database Setup

- **init.sql** - PostgreSQL initialization SQL script
- **create_ceg_tables_sqlite.py** - Create CEG tables for SQLite (development)
- **load_sources.py** - Load news sources from config/sources.yml into database

## Testing Scripts

### NER & Classification
- **test_topic_classifier.py** - Test topic classification with examples
- **test_topic_classifier_simple.py** - Simple topic classifier test

### MOEX Integration
- **test_moex_auto_search.py** - Test MOEX company auto-search functionality

### Data Sources
- **verify_telegram_sources.py** - Verify Telegram sources configuration

## Maintenance & Fixes

- **fix_encoding.py** - Fix UTF-8 encoding issues in database

## Usage

Most scripts can be run directly from the project root:

```bash
# Setup Neo4j schema
python scripts/setup_neo4j.py

# Load sources
python scripts/load_sources.py

# Test MOEX search
python scripts/test_moex_auto_search.py

# Cleanup graph duplicates
python scripts/cleanup_graph_duplicates.py
```

Some scripts require environment variables to be set (DATABASE_URL, NEO4J_URI, etc.). Make sure your `.env` file is configured before running.

## Legacy Scripts

The following scripts in `Parser/scripts/` are legacy worker startup scripts (superseded by `workers/` directory):
- start_telegram_parser_ceg.py → workers/telegram_worker.py
- start_enricher.py → workers/enrichment_worker.py
- start_outbox_relay.py → workers/outbox_worker.py
- start_html_parser.py → workers/html_parser_worker.py (to be created)
- start_api.py → `python -m uvicorn api.main:app --reload`
