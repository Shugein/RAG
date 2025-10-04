# Encoding & Telegram Configuration - Fix Summary

## 🎉 Good News!

Your data **IS stored correctly** in the database! The encoding issues you saw were likely in how the terminal was displaying the data, not in the database itself.

## ✅ What Was Fixed

### 1. Database Connection Encoding
**File:** `src/core/database.py`

Added explicit UTF-8 encoding to PostgreSQL connection:
```python
"server_settings": {
    "application_name": "news_aggregator",
    "client_encoding": "UTF8"  # ← Added this
}
```

**Impact:** Ensures all future data is stored with proper UTF-8 encoding.

### 2. Better Error Handling for Telegram Channels
**File:** `src/api/endpoints/jobs.py`

- Added specific error handling for invalid Telegram usernames
- Provides clear error messages with actionable guidance
- Prevents `MissingGreenlet` errors in exception handlers

**Before:**
```
ValueError: No user has "cbonds_news" as username
[followed by cryptic SQLAlchemy error]
```

**After:**
```
ERROR: Invalid Telegram channel for cbonds_news: @cbonds_news.
Please verify the channel exists and is accessible.
Telegram channel '@cbonds_news' not found or not accessible.
Please check the channel name in config/sources.yml
```

### 3. New Utility Scripts

#### `scripts/fix_encoding.py`
Fixes any existing mojibake in the database (though you don't currently need it).

Usage:
```bash
# Check for issues (dry run)
python scripts/fix_encoding.py --dry-run

# Fix issues if found
python scripts/fix_encoding.py --force
```

#### `scripts/verify_telegram_sources.py`
Verifies all Telegram channel configurations.

Usage:
```bash
python scripts/verify_telegram_sources.py
```

## 🔍 Verification Results

### ✅ Valid Sources (3/4)
- **interfax** - Интерфакс (@interfaxonline)
- **rbc_news** - РБК. Новости. Главное (@rbc_news)
- **vedomosti** - ВЕДОМОСТИ (@vedomosti)

### ❌ Invalid Sources (1/4)
- **cbonds_news** (@cbonds_news) - Username not occupied

## 🛠️ Action Items

### 1. Fix the cbonds_news Source

The channel `@cbonds_news` doesn't exist or isn't public. You have two options:

**Option A: Find the Correct Channel**
1. Open Telegram
2. Search for "cbonds" or "Cbonds News"
3. Find the correct channel username
4. Update `config/sources.yml`:
   ```yaml
   - code: cbonds_news
     name: Cbonds News
     kind: telegram
     tg_chat_id: "@correct_username_here"  # ← Update this
   ```
5. Reload sources:
   ```bash
   python scripts/load_sources.py
   ```

**Option B: Disable the Source**
If you don't need this source:
```yaml
- code: cbonds_news
  name: Cbonds News
  kind: telegram
  tg_chat_id: "@cbonds_news"
  enabled: false  # ← Set to false
```

### 2. Restart Your Services

For the encoding fixes to take effect:
```bash
# Stop your current services (Ctrl+C)
# Then restart them
python scripts/start_api.py
```

### 3. Test the Fixes

Try a backfill with a working source:
```bash
curl -X POST "http://localhost:8000/api/jobs/backfill" \
  -H "Content-Type: application/json" \
  -d '{
    "source_code": "interfax",
    "days_back": 1,
    "limit": 5
  }'
```

Then check the news:
```bash
curl "http://localhost:8000/api/news?limit=3"
```

## 📊 Current Database Status

Your database already contains correctly encoded news:
```
Total news: 3

First 3 news:

- **Во Франции прокуратура Бреста начала расследование в отношении танкера...
  Published: 2025-10-01 19:00:23+00:00
  Source: interfax

- **ОПЕК получила от восьми стран новые графики компенсаций...
  Published: 2025-10-01 17:50:57+00:00
  Source: interfax

- ⚽️**Французский "Пари Сен-Жермен" со счетом 2:1 одолел...
  Published: 2025-10-01 21:17:53+00:00
  Source: interfax
```

## 💡 Terminal Encoding Issue

If you see garbled text in your terminal but the database is correct, it's a terminal encoding issue:

**Windows Command Prompt:**
```cmd
chcp 65001
```

**Windows PowerShell:**
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

**Or use Windows Terminal** (has better UTF-8 support)

## 📚 Documentation

- See `scripts/README.md` for detailed documentation on all utility scripts
- Error handling improvements are documented inline in the code

## 🎯 Summary

| Item | Status |
|------|--------|
| Database encoding | ✅ Fixed & verified |
| Error handling | ✅ Improved |
| Utility scripts | ✅ Created |
| Valid sources | ✅ 3 working |
| Invalid sources | ⚠️ 1 needs fixing (cbonds_news) |
| Existing data | ✅ Correctly encoded |

## Need Help?

Run these diagnostic commands:

```bash
# Verify Telegram sources
python scripts/verify_telegram_sources.py

# Check database content
python -c "import asyncio; from src.core.database import get_db_session, init_db; from src.core.models import News; from sqlalchemy import select; from sqlalchemy.orm import selectinload; async def check(): await init_db(); async with get_db_session() as s: r = await s.execute(select(News).options(selectinload(News.source)).limit(3).order_by(News.detected_at.desc())); news = r.scalars().all(); print(f'\nTotal news: {len(news)}\n'); [print(f'- {n.title[:100]}\n  Source: {n.source.code}\n') for n in news]; asyncio.run(check())"

# Check for encoding issues
python scripts/fix_encoding.py --dry-run --limit 100
```


