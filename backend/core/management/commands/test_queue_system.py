"""
Load test command for queue-based verification system.

Creates fake TG users, simulates engagement flow, and verifies
the queue system works correctly.

Usage:
    python manage.py test_queue_system --users=5 --cleanup
"""
import random
import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import User
from posts.models import Engagement, Post, VerificationBatch


class Command(BaseCommand):
    help = "Load test the queue-based verification system"

    # Test user telegram IDs start from this number
    TEST_TG_ID_START = 9999900000

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=5,
            help="Number of test users to create (default: 5)",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Clean up test users and their data after test",
        )
        parser.add_argument(
            "--cleanup-only",
            action="store_true",
            help="Only clean up existing test data, don't run test",
        )
        parser.add_argument(
            "--wait",
            type=int,
            default=30,
            help="Seconds to wait for Celery to process batches (default: 30)",
        )

    def handle(self, *args, **options):
        num_users = options["users"]
        cleanup = options["cleanup"]
        cleanup_only = options["cleanup_only"]
        wait_time = options["wait"]

        if cleanup_only:
            self.cleanup_test_data()
            return

        self.stdout.write(self.style.NOTICE(f"\n{'='*60}"))
        self.stdout.write(self.style.NOTICE("Queue System Load Test"))
        self.stdout.write(self.style.NOTICE(f"{'='*60}\n"))

        # Check if we have enough posts
        active_posts = Post.objects.filter(status=Post.Status.ACTIVE).count()
        if active_posts < 10:
            self.stdout.write(self.style.ERROR(
                f"Need at least 10 active posts, found {active_posts}. "
                "Run seed_posts first."
            ))
            return

        self.stdout.write(f"Found {active_posts} active posts")
        self.stdout.write(f"Creating {num_users} test users...\n")

        # Track created resources for cleanup
        created_users = []
        created_engagements = []
        created_batches = []

        try:
            # Step 1: Create test users
            for i in range(num_users):
                tg_id = self.TEST_TG_ID_START + i + 1
                user, created = User.objects.get_or_create(
                    telegram_id=tg_id,
                    defaults={
                        "telegram_username": f"test_user_{i+1}",
                        "display_name": f"Test User {i+1}",
                        "x_username": f"testuser{i+1}",
                        "credits": Decimal("100"),
                        "honesty_score": 50,
                    }
                )
                created_users.append(user)
                status = "created" if created else "exists"
                self.stdout.write(f"  [{status}] User {user.display_name} (TG: {tg_id})")

            self.stdout.write(self.style.SUCCESS(f"\n{len(created_users)} test users ready"))

            # Step 2: Simulate engagement flow for each user
            self.stdout.write(f"\nSimulating engagements...")

            # Get active posts (exclude posts owned by test users)
            posts = list(Post.objects.filter(
                status=Post.Status.ACTIVE,
                escrow__gt=0,
            ).exclude(
                user__in=created_users
            ).order_by('?')[:20])  # Random 20 posts

            if len(posts) < 10:
                self.stdout.write(self.style.ERROR(
                    f"Need at least 10 posts not owned by test users, found {len(posts)}"
                ))
                return

            for user in created_users:
                # Each user engages with 10 random posts
                user_posts = random.sample(posts, min(10, len(posts)))
                self.stdout.write(f"\n  User {user.display_name}:")

                for post in user_posts:
                    # Create engagement (simulating click)
                    eng, created = Engagement.objects.get_or_create(
                        user=user,
                        post=post,
                        defaults={
                            "clicked_at": timezone.now(),
                            "verified": False,
                            "credit_granted": False,
                        }
                    )
                    if created:
                        created_engagements.append(eng)
                    self.stdout.write(f"    - Engaged post {str(post.id)[:8]}...")

            self.stdout.write(self.style.SUCCESS(
                f"\n{len(created_engagements)} engagements created"
            ))

            # Step 3: Queue claims for each user
            self.stdout.write(f"\nQueuing verification batches...")

            from posts.tasks import process_verification_batch

            for user in created_users:
                # Get user's pending engagements
                pending = list(Engagement.objects.filter(
                    user=user,
                    verified=False,
                    credit_granted=False,
                ).values_list('id', flat=True))

                if not pending:
                    self.stdout.write(f"  User {user.display_name}: No pending engagements")
                    continue

                # Create batch (simulating queue-claim API)
                batch = VerificationBatch.objects.create(
                    user=user,
                    engagement_ids=[str(eid) for eid in pending],
                    status=VerificationBatch.Status.PENDING,
                )
                created_batches.append(batch)

                # Queue the task
                try:
                    process_verification_batch.delay(str(batch.id))
                    self.stdout.write(
                        f"  User {user.display_name}: Queued batch {str(batch.id)[:8]} "
                        f"({len(pending)} engagements)"
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"  User {user.display_name}: Failed to queue - {e}"
                    ))
                    # Mark batch as failed
                    batch.status = VerificationBatch.Status.FAILED
                    batch.message = str(e)
                    batch.save()

            self.stdout.write(self.style.SUCCESS(
                f"\n{len(created_batches)} batches queued"
            ))

            # Step 4: Wait for Celery to process
            self.stdout.write(f"\nWaiting {wait_time}s for Celery to process...")

            for i in range(wait_time):
                time.sleep(1)
                # Check progress every 5 seconds
                if (i + 1) % 5 == 0:
                    completed = VerificationBatch.objects.filter(
                        id__in=[b.id for b in created_batches],
                        status=VerificationBatch.Status.COMPLETED,
                    ).count()
                    processing = VerificationBatch.objects.filter(
                        id__in=[b.id for b in created_batches],
                        status=VerificationBatch.Status.PROCESSING,
                    ).count()
                    pending = VerificationBatch.objects.filter(
                        id__in=[b.id for b in created_batches],
                        status=VerificationBatch.Status.PENDING,
                    ).count()
                    self.stdout.write(
                        f"  [{i+1}s] Completed: {completed}, "
                        f"Processing: {processing}, Pending: {pending}"
                    )

                    # All done?
                    if completed == len(created_batches):
                        self.stdout.write(self.style.SUCCESS("  All batches completed!"))
                        break

            # Step 5: Report results
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write("RESULTS")
            self.stdout.write(f"{'='*60}\n")

            for batch in created_batches:
                batch.refresh_from_db()
                user = batch.user

                if batch.status == VerificationBatch.Status.COMPLETED:
                    self.stdout.write(self.style.SUCCESS(
                        f"  {user.display_name}: COMPLETED - "
                        f"Passed: {batch.passed}, Failed: {batch.failed}, "
                        f"Credits: {batch.credits_awarded}"
                    ))
                elif batch.status == VerificationBatch.Status.PROCESSING:
                    self.stdout.write(self.style.WARNING(
                        f"  {user.display_name}: STILL PROCESSING"
                    ))
                elif batch.status == VerificationBatch.Status.PENDING:
                    self.stdout.write(self.style.WARNING(
                        f"  {user.display_name}: STILL PENDING (Celery may not be running)"
                    ))
                elif batch.status == VerificationBatch.Status.FAILED:
                    self.stdout.write(self.style.ERROR(
                        f"  {user.display_name}: FAILED - {batch.message}"
                    ))

            # Summary
            completed_count = sum(
                1 for b in created_batches
                if b.status == VerificationBatch.Status.COMPLETED
            )
            self.stdout.write(f"\nSummary: {completed_count}/{len(created_batches)} batches completed")

            if completed_count == len(created_batches):
                self.stdout.write(self.style.SUCCESS("\nQueue system is working correctly!"))
            elif completed_count > 0:
                self.stdout.write(self.style.WARNING(
                    "\nPartial success - some batches processed"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    "\nNo batches completed - check if Celery worker is running"
                ))

        finally:
            # Cleanup if requested
            if cleanup:
                self.stdout.write(f"\n{'='*60}")
                self.stdout.write("CLEANUP")
                self.stdout.write(f"{'='*60}\n")
                self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove all test users and their associated data."""
        # Find test users
        test_users = User.objects.filter(
            telegram_id__gte=self.TEST_TG_ID_START,
            telegram_id__lt=self.TEST_TG_ID_START + 1000,
        )

        count = test_users.count()
        if count == 0:
            self.stdout.write("No test users found to clean up")
            return

        self.stdout.write(f"Found {count} test users to clean up")

        with transaction.atomic():
            # Delete batches
            batches_deleted, _ = VerificationBatch.objects.filter(
                user__in=test_users
            ).delete()
            self.stdout.write(f"  Deleted {batches_deleted} verification batches")

            # Delete engagements
            engagements_deleted, _ = Engagement.objects.filter(
                user__in=test_users
            ).delete()
            self.stdout.write(f"  Deleted {engagements_deleted} engagements")

            # Delete users
            users_deleted, _ = test_users.delete()
            self.stdout.write(f"  Deleted {users_deleted} test users")

        self.stdout.write(self.style.SUCCESS("Cleanup complete"))
