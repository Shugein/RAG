#!/usr/bin/env python3
"""
Script to verify Telegram channel configurations.

This script checks that all configured Telegram channels are valid and accessible.

Usage:
    python scripts/verify_telegram_sources.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# AddParser.src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from telethon.errors import UsernameInvalidError, UsernameNotOccupiedError

from Parser.src.core.database import get_db_session, init_db
from Parser.src.core.models import Source
from Parser.src.services.telegram_parser.client import TelegramClientManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def verify_telegram_channel(client, source: Source) -> dict:
    """
    Verify a single Telegram channel.
    
    Returns:
        dict with verification results
    """
    result = {
        'source_code': source.code,
        'tg_chat_id': source.tg_chat_id,
        'valid': False,
        'accessible': False,
        'error': None,
        'channel_info': None
    }
    
    try:
        # Try to get the entity
        entity = await client.get_entity(source.tg_chat_id)
        result['valid'] = True
        result['accessible'] = True
        
        # Get channel info
        result['channel_info'] = {
            'title': getattr(entity, 'title', None),
            'username': getattr(entity, 'username', None),
            'id': entity.id,
            'participants_count': getattr(entity, 'participants_count', 'N/A'),
        }
        
        logger.info(f"✅ {source.code}: Valid and accessible")
        logger.info(f"   Channel: {result['channel_info']['title']}")
        logger.info(f"   Username: @{result['channel_info']['username']}")
        
    except (UsernameInvalidError, UsernameNotOccupiedError) as e:
        result['error'] = f"Channel not found: {e}"
        logger.error(f"❌ {source.code}: {result['error']}")
        logger.error(f"   Configured as: {source.tg_chat_id}")
        
    except ValueError as e:
        if "No user has" in str(e):
            result['error'] = f"Username not occupied: {e}"
            logger.error(f"❌ {source.code}: {result['error']}")
            logger.error(f"   Configured as: {source.tg_chat_id}")
        else:
            result['error'] = str(e)
            logger.error(f"❌ {source.code}: {result['error']}")
    
    except Exception as e:
        result['error'] = f"Unexpected error: {e}"
        logger.error(f"⚠️  {source.code}: {result['error']}")
    
    return result


async def main():
    """Main entry point"""
    logger.info("Starting Telegram sources verification...")
    logger.info("=" * 60)
    
    # Initialize database
    await init_db()
    
    # Initialize Telegram client
    client_manager = None
    try:
        client_manager = TelegramClientManager()
        client = await client_manager.initialize()
        logger.info("Telegram client initialized\n")
        
        # Get all Telegram sources
        async with get_db_session() as session:
            result = await session.execute(
                select(Source).where(
                    Source.kind == "telegram",
                    Source.enabled == True
                ).order_by(Source.code)
            )
            sources = result.scalars().all()
        
        if not sources:
            logger.warning("No enabled Telegram sources found in database")
            return
        
        logger.info(f"Found {len(sources)} enabled Telegram source(s)\n")
        
        # Verify each source
        results = []
        for source in sources:
            result = await verify_telegram_channel(client, source)
            results.append(result)
            print()  # Empty line between sources
        
        # Summary
        logger.info("=" * 60)
        logger.info("VERIFICATION SUMMARY:")
        logger.info("=" * 60)
        
        valid_count = sum(1 for r in results if r['valid'])
        invalid_count = len(results) - valid_count
        
        logger.info(f"Total sources: {len(results)}")
        logger.info(f"✅ Valid: {valid_count}")
        logger.info(f"❌ Invalid: {invalid_count}")
        
        if invalid_count > 0:
            logger.info("\n⚠️  INVALID SOURCES:")
            for r in results:
                if not r['valid']:
                    logger.info(f"  - {r['source_code']} ({r['tg_chat_id']})")
                    logger.info(f"    Error: {r['error']}")
            
            logger.info("\n💡 NEXT STEPS:")
            logger.info("  1. Verify the channel names are correct")
            logger.info("  2. Check if channels are public and accessible")
            logger.info("  3. Update config/sources.yml with correct usernames")
            logger.info("  4. Reload sources: python scripts/load_sources.py")
        else:
            logger.info("\n✅ All sources are valid and accessible!")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error during verification: {e}", exc_info=True)
        raise
    
    finally:
        if client_manager:
            await client_manager.disconnect()
            logger.info("\nTelegram client disconnected")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nVerification cancelled by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

