"""
Management command to create test users for load testing.

Usage:
    python manage.py create_load_test_users
    python manage.py create_load_test_users --count 200
    python manage.py create_load_test_users --delete  # Remove test users
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import User


class Command(BaseCommand):
    help = "Create test users for load testing (telegram_id 900000001+)"

    # Test user telegram_id range
    START_ID = 900000001
    DEFAULT_COUNT = 100

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=self.DEFAULT_COUNT,
            help=f"Number of test users to create (default: {self.DEFAULT_COUNT})",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete all load test users instead of creating",
        )
        parser.add_argument(
            "--credits",
            type=int,
            default=10000,
            help="Initial credits for each test user (default: 10000)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        delete = options["delete"]
        credits = options["credits"]

        if delete:
            self.delete_test_users()
        else:
            self.create_test_users(count, credits)

    def delete_test_users(self):
        """Delete all load test users."""
        deleted, _ = User.objects.filter(
            telegram_id__gte=self.START_ID,
            telegram_id__lt=self.START_ID + 1000000,
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} load test users")
        )

    @transaction.atomic
    def create_test_users(self, count: int, credits: int):
        """Create load test users."""
        created = 0
        skipped = 0

        for i in range(count):
            telegram_id = self.START_ID + i
            username = f"loadtest_user_{i + 1}"

            user, was_created = User.objects.get_or_create(
                telegram_id=telegram_id,
                defaults={
                    "telegram_username": username,
                    "display_name": f"Load Test User {i + 1}",
                    "x_username": f"loadtest_x_{i + 1}",
                    "credits": Decimal(credits),
                    "total_credits_earned": Decimal(credits),
                    "is_whitelisted": True,  # Allow all features
                    "loud_access": True,
                    "honesty_score": 50,
                },
            )

            if was_created:
                created += 1
            else:
                # Update existing test user credits
                user.credits = Decimal(credits)
                user.save(update_fields=["credits"])
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created} load test users, updated {skipped} existing"
            )
        )
        self.stdout.write(
            f"Telegram IDs: {self.START_ID} - {self.START_ID + count - 1}"
        )
        self.stdout.write(f"Credits per user: {credits}")
        self.stdout.write("")
        self.stdout.write("To use in Locust, set these headers:")
        self.stdout.write("  X-Load-Test-Auth: <your LOAD_TEST_SECRET>")
        self.stdout.write(f"  X-Load-Test-User: {self.START_ID}")
