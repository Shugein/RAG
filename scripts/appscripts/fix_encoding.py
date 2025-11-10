#!/usr/bin/env python3
"""
Script to fix UTF-8 encoding issues in existing news data.

This script identifies and fixes corrupted text in the database that was stored
with incorrect encoding (mojibake).

Usage:
    python scripts/fix_encoding.py [--dry-run] [--limit N]
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List

# AddParser.src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from Parser.src.core.database import get_db_session, init_db
from Parser.src.core.models import News

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fix_mojibake(text: str) -> str:
    """
    Attempt to fix mojibake (corrupted UTF-8 encoding).
    
    Common pattern: Text was decoded as Latin-1 then encoded as UTF-8.
    We need to reverse this: decode as UTF-8, encode as Latin-1, decode as UTF-8.
    """
    if not text:
        return text
    
    try:
        # Try to detect and fix mojibake
        # Pattern: UTF-8 text incorrectly decoded as Latin-1
        fixed = text.encode('latin-1').decode('utf-8')
        logger.debug(f"Fixed mojibake: '{text[:50]}...' -> '{fixed[:50]}...'")
        return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        # If it fails, the text might already be correct or have different encoding issues
        logger.debug(f"Could not fix text: '{text[:50]}...'")
        return text


def is_likely_corrupted(text: str) -> bool:
    """
    Check if text is likely to be corrupted.
    
    Common indicators:
    - Contains sequences like Ð, Ñ, â, etc. (Cyrillic mojibake)
    - Has unusual character combinations
    """
    if not text:
        return False
    
    # Common mojibake patterns for Cyrillic
    mojibake_indicators = [
        'Ð', 'Ñ', 'â', 'Ð¡', 'ÐµÑ', 'Ñ‚', 'Ð½', 
        'Ð¾Ñ', 'ÐºÐ°Ñ', 'ÑÑ', 'Ð¸Ñ', 'ÐµÐ»'
    ]
    
    # Check for multiple indicators
    matches = sum(1 for indicator in mojibake_indicators if indicator in text)
    
    # If we have 2+ indicators, it's likely corrupted
    return matches >= 2


async def fix_news_encoding(
    session: AsyncSession,
    dry_run: bool = True,
    limit: int = None
) -> tuple[int, int]:
    """
    Fix encoding issues in news table.
    
    Returns:
        Tuple of (checked_count, fixed_count)
    """
    # Query all news or limited set
    stmt = select(News).order_by(News.detected_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    
    result = await session.execute(stmt)
    news_items = result.scalars().all()
    
    checked = 0
    fixed = 0
    
    logger.info(f"Checking {len(news_items)} news items for encoding issues...")
    
    for news in news_items:
        checked += 1
        needs_fix = False
        
        # Check and fix title
        if news.title and is_likely_corrupted(news.title):
            fixed_title = fix_mojibake(news.title)
            if fixed_title != news.title:
                logger.info(f"News {news.id} - Title corrupted")
                logger.info(f"  Before: {news.title[:100]}")
                logger.info(f"  After:  {fixed_title[:100]}")
                
                if not dry_run:
                    news.title = fixed_title
                needs_fix = True
        
        # Check and fix text_plain
        if news.text_plain and is_likely_corrupted(news.text_plain):
            fixed_text = fix_mojibake(news.text_plain)
            if fixed_text != news.text_plain:
                logger.info(f"News {news.id} - Text corrupted")
                logger.info(f"  Before: {news.text_plain[:100]}")
                logger.info(f"  After:  {fixed_text[:100]}")
                
                if not dry_run:
                    news.text_plain = fixed_text
                needs_fix = True
        
        # Check and fix summary
        if news.summary and is_likely_corrupted(news.summary):
            fixed_summary = fix_mojibake(news.summary)
            if fixed_summary != news.summary:
                logger.info(f"News {news.id} - Summary corrupted")
                
                if not dry_run:
                    news.summary = fixed_summary
                needs_fix = True
        
        if needs_fix:
            fixed += 1
            if not dry_run:
                await session.flush()
        
        # Log progress every 100 items
        if checked % 100 == 0:
            logger.info(f"Progress: {checked}/{len(news_items)} checked, {fixed} need fixing")
    
    if not dry_run:
        await session.commit()
        logger.info("Changes committed to database")
    else:
        logger.info("DRY RUN - No changes made to database")
    
    return checked, fixed


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Fix UTF-8 encoding issues in news database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be fixed without making changes'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of news items to check'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Apply fixes to database (opposite of --dry-run)'
    )
    
    args = parser.parse_args()
    
    # Default to dry-run unless --force is specified
    dry_run = not args.force if args.force else args.dry_run or True
    
    if not dry_run:
        confirm = input(
            "⚠️  This will modify data in the database. Continue? (yes/no): "
        )
        if confirm.lower() != 'yes':
            logger.info("Aborted by user")
            return
    
    logger.info("Starting encoding fix script...")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE - WILL MODIFY DATABASE'}")
    
    # Initialize database
    await init_db()
    
    # Fix encoding
    async with get_db_session() as session:
        checked, fixed = await fix_news_encoding(
            session,
            dry_run=dry_run,
            limit=args.limit
        )
    
    logger.info("=" * 60)
    logger.info(f"Summary:")
    logger.info(f"  Checked: {checked} news items")
    logger.info(f"  Found with encoding issues: {fixed}")
    logger.info(f"  Mode: {'DRY RUN (no changes made)' if dry_run else 'LIVE (changes saved)'}")
    logger.info("=" * 60)
    
    if dry_run and fixed > 0:
        logger.info("\n💡 To apply fixes, run with --force flag:")
        logger.info("   python scripts/fix_encoding.py --force")


if __name__ == "__main__":
    asyncio.run(main())

