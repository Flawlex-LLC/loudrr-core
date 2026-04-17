"""Lazy singleton for the Telegram bot Application.

In webhook mode the Django process receives updates via HTTP and feeds them
into this shared Application. The Application is initialized once per worker.
"""
import asyncio
import logging

from .bot import create_bot

logger = logging.getLogger(__name__)

_bot_app = None
_bot_app_lock = asyncio.Lock()


async def get_bot_app():
    """Return the initialized bot Application (singleton per worker)."""
    global _bot_app
    if _bot_app is not None:
        return _bot_app

    async with _bot_app_lock:
        if _bot_app is None:
            logger.info("Initializing Telegram bot Application for webhook mode")
            app = create_bot()
            await app.initialize()
            _bot_app = app
    return _bot_app
