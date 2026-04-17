"""Unregister the Telegram bot webhook with Telegram.

Useful when switching back to polling or rotating webhook URLs.
"""
import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand
from telegram import Bot


class Command(BaseCommand):
    help = "Unregister the Telegram bot webhook"

    def add_arguments(self, parser):
        parser.add_argument(
            "--drop-pending",
            action="store_true",
            help="Drop any pending updates queued at Telegram",
        )

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN is not set"))
            return
        asyncio.run(self._run(options["drop_pending"]))

    async def _run(self, drop_pending: bool):
        bot = Bot(settings.TELEGRAM_BOT_TOKEN)
        await bot.delete_webhook(drop_pending_updates=drop_pending)
        self.stdout.write(self.style.SUCCESS("Webhook deleted"))
