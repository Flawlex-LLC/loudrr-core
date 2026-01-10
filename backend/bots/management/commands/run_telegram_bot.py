"""
Django management command to run the Telegram bot.

Usage: python manage.py run_telegram_bot
"""
import asyncio
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from bots.telegram.bot import create_bot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the ECHO Telegram bot"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting ECHO Telegram bot..."))

        if not settings.TELEGRAM_BOT_TOKEN:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not configured"))
            return

        try:
            asyncio.run(self.run_bot())
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("Bot stopped"))

    async def run_bot(self):
        """Run the bot using asyncio."""
        application = create_bot()
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)

        self.stdout.write(self.style.SUCCESS("Bot is running. Press Ctrl+C to stop."))

        # Keep running until interrupted
        try:
            await asyncio.Event().wait()
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
