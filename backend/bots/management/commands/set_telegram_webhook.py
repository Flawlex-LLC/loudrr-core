"""Register the Telegram bot webhook with Telegram.

Run once after deploying a new webhook URL or rotating the secret.
"""
import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand
from telegram import Bot


class Command(BaseCommand):
    help = "Register the Telegram bot webhook with Telegram"

    def add_arguments(self, parser):
        parser.add_argument(
            "--drop-pending",
            action="store_true",
            help="Drop any pending updates queued while webhook was unset",
        )

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stderr.write(self.style.ERROR("TELEGRAM_BOT_TOKEN is not set"))
            return
        if not settings.TELEGRAM_WEBHOOK_URL:
            self.stderr.write(self.style.ERROR("TELEGRAM_WEBHOOK_URL is not set"))
            return
        if not settings.TELEGRAM_WEBHOOK_SECRET:
            self.stderr.write(self.style.ERROR("TELEGRAM_WEBHOOK_SECRET is not set"))
            return

        asyncio.run(self._run(options["drop_pending"]))

    async def _run(self, drop_pending: bool):
        bot = Bot(settings.TELEGRAM_BOT_TOKEN)
        await bot.set_webhook(
            url=settings.TELEGRAM_WEBHOOK_URL,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
            drop_pending_updates=drop_pending,
        )
        info = await bot.get_webhook_info()
        self.stdout.write(self.style.SUCCESS(f"Webhook registered at {info.url}"))
        if info.pending_update_count:
            self.stdout.write(f"Pending updates: {info.pending_update_count}")
        if info.last_error_message:
            self.stdout.write(self.style.WARNING(f"Last error: {info.last_error_message}"))
