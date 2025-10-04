# src/services/telegram_parser/client.py

import asyncio
import logging
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from src.core.config import settings

logger = logging.getLogger(__name__)


class TelegramClientManager:
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.session_path = Path("sessions")
        self.session_path.mkdir(exist_ok=True)

    async def initialize(self) -> TelegramClient:
        """Initialize and return authenticated Telegram client"""
        session_file = self.session_path / f"{settings.TELETHON_SESSION_NAME}.session"

        self.client = TelegramClient(
            str(session_file),
            settings.TELETHON_API_ID,
            settings.TELETHON_API_HASH,
            system_version="4.16.30-vxCUSTOM"
        )

        await self.client.start(phone=settings.TELETHON_PHONE)
        logger.info("Telegram client initialized and authenticated")

        return self.client

    async def disconnect(self):
        """Gracefully disconnect the client"""
        if self.client:
            await self.client.disconnect()
            logger.info("Telegram client disconnected")