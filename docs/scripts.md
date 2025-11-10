# Utility Scripts

This directory contains utility scripts for managing the News Aggregator system.

## Database Management

### fix_encoding.py

Fixes UTF-8 encoding issues (mojibake) in existing news data.

**Usage:**

```bash
# Dry run (shows what would be fixed without making changes)
python scripts/fix_encoding.py --dry-run

# Check only the 100 most recent news items
python scripts/fix_encoding.py --dry-run --limit 100

# Actually fix the data (requires confirmation)
python scripts/fix_encoding.py --force
```

**What it does:**
- Scans news titles, text, and summaries for corrupted encoding
- Detects common Cyrillic mojibake patterns
- Attempts to fix corrupted text by reversing the encoding error
- Provides detailed logging of changes

**When to use:**
- After discovering garbled Cyrillic text in your news
- After migrating from a system with incorrect encoding
- When you see characters like "Ð", "Ñ", "â" instead of Russian text

## Telegram Configuration

### verify_telegram_sources.py

Verifies that all configured Telegram channels are valid and accessible.

**Usage:**

```bash
python scripts/verify_telegram_sources.py
```

**What it does:**
- Connects to Telegram using your credentials
- Checks each enabled Telegram source in the database
- Verifies channel exists and is accessible
- Shows channel information (title, username, ID)
- Provides summary of valid/invalid sources

**When to use:**
- After adding new Telegram sources
- When experiencing errors fetching from Telegram
- To validate configuration after changes
- Before running a large backfill operation

**Example output:**
```
✅ interfax: Valid and accessible
   Channel: Интерфакс
   Username: @interfaxonline

❌ cbonds_news: Channel not found
   Configured as: @cbonds_news
   Error: No user has "@cbonds_news" as username

VERIFICATION SUMMARY:
Total sources: 4
✅ Valid: 3
❌ Invalid: 1
```

## Source Management

### load_sources.py

Loads source configurations from YAML into the database.

**Usage:**

```bash
python scripts/load_sources.py
```

**What it does:**
- Reads `config/sources.yml`
- Creates or updates source records in the database
- Preserves existing parser state

**When to use:**
- Initial setup
- After modifying `config/sources.yml`
- To add new sources or update existing ones

## Service Starters

### start_api.py
Starts the FastAPI web server.

### start_telegram_parser.py
Starts the Telegram message parser service.

### start_enricher.py
Starts the news enrichment service (NER, topic classification).

### start_outbox_relay.py
Starts the outbox event relay service.

## Troubleshooting

### Corrupted Text in News

**Symptoms:**
- News titles show garbled characters
- Cyrillic text appears as "Ð¤ÑÐ°Ð½ÑÑÐ·ÑÐºÐ¸Ð¹" instead of "Французский"

**Solution:**
1. Run encoding fix script:
   ```bash
   python scripts/fix_encoding.py --force
   ```
2. Restart your services to apply encoding configuration changes
3. New data should be stored correctly

### Telegram Channel Errors

**Symptoms:**
- "No user has X as username" errors
- Backfill jobs fail immediately
- Cannot fetch messages

**Solution:**
1. Verify channel configuration:
   ```bash
   python scripts/verify_telegram_sources.py
   ```
2. Check if channel exists and is public:
   - Open Telegram
   - Search for the channel username
   - Make sure you can access it
3. Update `config/sources.yml` if needed
4. Reload sources:
   ```bash
   python scripts/load_sources.py
   ```

### Database Connection Issues

**Symptoms:**
- "greenlet_spawn has not been called" errors
- Connection timeout errors

**Solution:**
1. Check PostgreSQL is running
2. Verify database URL in `.env` or environment
3. Check connection pool settings in `src/core/config.py`
4. Review database logs

## Best Practices

1. **Always test with --dry-run first** when using data modification scripts
2. **Backup your database** before running fix scripts
3. **Verify Telegram sources** before large backfill operations
4. **Monitor logs** when running services
5. **Use limit parameter** when testing scripts on large datasets

## Environment Setup

All scripts require:
- Python 3.10+
- Virtual environment activated
- Environment variables set (`.env` file)
- Database accessible
- For Telegram scripts: valid Telegram credentials

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Run script
python scripts/<script_name>.py
```

