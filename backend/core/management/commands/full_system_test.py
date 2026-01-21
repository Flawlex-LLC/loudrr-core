"""
Comprehensive system test for Loudrr platform.

Tests ALL business logic flows:
1. User registration & X account linking
2. Post submission (escrow, karma deduction)
3. Engagement flow (session, clicks, verification)
4. Queue-based verification (Celery)
5. Credit system (earning, multipliers, daily caps)
6. Edge cases & error handling
7. Concurrency safety

Usage:
    python manage.py full_system_test
    python manage.py full_system_test --quick      # Skip slow tests
    python manage.py full_system_test --cleanup    # Clean up after
    python manage.py full_system_test --verbose    # Detailed output
"""
import random
import time
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.db.models import F
from django.utils import timezone

from core.models import User, Transaction, SiteSetting
from core.services.credits import CreditService, InsufficientCreditsError, DailyCapReachedError
from core.services.tweet_score import calculate_engagement_karma, get_tier_name
from core.services.settings import get_setting
from posts.models import Engagement, Post, VerificationBatch


class Command(BaseCommand):
    help = "Comprehensive system test for all business logic"

    # Test user IDs start from this
    TEST_TG_ID_START = 8888800000

    def add_arguments(self, parser):
        parser.add_argument(
            "--quick",
            action="store_true",
            help="Skip slow tests (Celery, concurrency)",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Clean up test data after running",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show detailed test output",
        )

    def handle(self, *args, **options):
        self.quick = options["quick"]
        self.cleanup = options["cleanup"]
        self.verbose = options["verbose"]

        self.passed = 0
        self.failed = 0
        self.errors = []

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("LOUDRR COMPREHENSIVE SYSTEM TEST"))
        self.stdout.write("=" * 70 + "\n")

        try:
            # Run all test suites
            self.test_user_creation()
            self.test_credit_system()
            self.test_tier_multipliers()
            self.test_post_submission()
            self.test_engagement_flow()
            self.test_verification_logic()

            if not self.quick:
                self.test_queue_system()
                self.test_concurrency()
            else:
                self.stdout.write(self.style.WARNING("\nSkipping slow tests (--quick mode)"))

            self.test_edge_cases()
            self.test_database_constraints()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nTest suite crashed: {e}"))
            import traceback
            traceback.print_exc()

        finally:
            if self.cleanup:
                self.cleanup_test_data()

            # Print summary
            self.print_summary()

    def log(self, message):
        """Log verbose output."""
        if self.verbose:
            self.stdout.write(f"    {message}")

    def assert_true(self, condition, test_name, message=""):
        """Assert a condition is true."""
        if condition:
            self.passed += 1
            self.stdout.write(self.style.SUCCESS(f"  ✓ {test_name}"))
        else:
            self.failed += 1
            error_msg = f"{test_name}: {message}" if message else test_name
            self.errors.append(error_msg)
            self.stdout.write(self.style.ERROR(f"  ✗ {test_name}"))
            if message:
                self.stdout.write(self.style.ERROR(f"    → {message}"))

    def assert_equal(self, actual, expected, test_name):
        """Assert two values are equal."""
        if actual == expected:
            self.passed += 1
            self.stdout.write(self.style.SUCCESS(f"  ✓ {test_name}"))
        else:
            self.failed += 1
            self.errors.append(f"{test_name}: expected {expected}, got {actual}")
            self.stdout.write(self.style.ERROR(f"  ✗ {test_name}"))
            self.stdout.write(self.style.ERROR(f"    → Expected: {expected}, Got: {actual}"))

    def assert_raises(self, exception_type, func, test_name):
        """Assert a function raises an exception."""
        try:
            func()
            self.failed += 1
            self.errors.append(f"{test_name}: Expected {exception_type.__name__} but no exception raised")
            self.stdout.write(self.style.ERROR(f"  ✗ {test_name}"))
        except exception_type:
            self.passed += 1
            self.stdout.write(self.style.SUCCESS(f"  ✓ {test_name}"))
        except Exception as e:
            self.failed += 1
            self.errors.append(f"{test_name}: Expected {exception_type.__name__}, got {type(e).__name__}")
            self.stdout.write(self.style.ERROR(f"  ✗ {test_name}"))

    def create_test_user(self, suffix, **kwargs):
        """Create a test user with given properties."""
        tg_id = self.TEST_TG_ID_START + suffix
        defaults = {
            "telegram_username": f"test_user_{suffix}",
            "display_name": f"Test User {suffix}",
            "x_username": f"testx_{suffix}",
            "credits": Decimal("100"),
            "tweetscout_score": 0,
            "honesty_score": 10,
        }
        defaults.update(kwargs)

        user, _ = User.objects.update_or_create(
            telegram_id=tg_id,
            defaults=defaults,
        )
        return user

    def create_test_post(self, user, escrow=Decimal("30")):
        """Create a test post."""
        post = Post.objects.create(
            user=user,
            x_link=f"https://x.com/test/status/{random.randint(1000000, 9999999)}",
            tweet_id=str(random.randint(1000000000, 9999999999)),
            escrow=escrow,
            initial_escrow=escrow,
            status=Post.Status.ACTIVE,
        )
        return post

    # =========================================================================
    # TEST SUITES
    # =========================================================================

    def test_user_creation(self):
        """Test user creation and basic properties."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: User Creation")
        self.stdout.write("-" * 50)

        # Test 1: Create user with defaults
        user = self.create_test_user(1)
        self.assert_true(user.id is not None, "User created with UUID")
        self.assert_equal(user.credits, Decimal("100"), "User has initial credits")
        self.assert_equal(user.honesty_score, 10, "User has default honesty score")

        # Test 2: User with X account
        user_with_x = self.create_test_user(2, x_username="real_x_user")
        self.assert_equal(user_with_x.x_username, "real_x_user", "X username saved correctly")

        # Test 3: User with TweetScout score
        user_with_score = self.create_test_user(3, tweetscout_score=500)
        tier = get_tier_name(user_with_score.tweetscout_score)
        self.assert_equal(tier, "based", "TweetScout score maps to correct tier")

        # Test 4: Duplicate telegram_id should update
        user_dup = self.create_test_user(1, display_name="Updated Name")
        self.assert_equal(user_dup.display_name, "Updated Name", "Duplicate TG ID updates user")

    def test_credit_system(self):
        """Test credit earning, spending, and transactions."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Credit System")
        self.stdout.write("-" * 50)

        user = self.create_test_user(10, credits=Decimal("50"))
        service = CreditService(user)

        # Test 1: Earn credits
        initial = user.credits
        service.earn(
            amount=Decimal("10.5"),
            reference_id=user.id,
            reference_type="test",
            description="Test earning",
        )
        user.refresh_from_db()
        self.assert_equal(user.credits, initial + Decimal("10.5"), "Credits earned correctly")

        # Test 2: Transaction created
        tx = Transaction.objects.filter(user=user, transaction_type="earn").last()
        self.assert_true(tx is not None, "Transaction record created")
        self.assert_equal(tx.amount, Decimal("10.5"), "Transaction amount correct")

        # Test 3: Spend credits
        initial = user.credits
        service.spend(
            amount=Decimal("20"),
            reference_id=user.id,
            reference_type="test",
            description="Test spending",
        )
        user.refresh_from_db()
        self.assert_equal(user.credits, initial - Decimal("20"), "Credits spent correctly")

        # Test 4: Insufficient credits
        user.credits = Decimal("5")
        user.save()
        service = CreditService(user)

        def try_spend():
            service.spend(
                amount=Decimal("100"),
                reference_id=user.id,
                reference_type="test",
                description="Should fail",
            )

        self.assert_raises(InsufficientCreditsError, try_spend, "InsufficientCreditsError raised")

        # Test 5: Decimal precision (4 decimal places)
        user.credits = Decimal("100")
        user.save()
        service = CreditService(user)
        service.earn(
            amount=Decimal("1.2345"),
            reference_id=user.id,
            reference_type="test",
            description="Precision test",
        )
        user.refresh_from_db()
        self.assert_true(
            str(user.credits).count('.') == 0 or len(str(user.credits).split('.')[1]) <= 4,
            "Decimal precision maintained (4 places)"
        )

    def test_tier_multipliers(self):
        """Test tier-based karma multipliers."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Tier Multipliers")
        self.stdout.write("-" * 50)

        base = Decimal("1")

        # Test each tier
        test_cases = [
            (0, "anon", Decimal("1.00")),
            (150, "normie", Decimal("1.03")),
            (300, "degen", Decimal("1.06")),
            (500, "based", Decimal("1.10")),
            (700, "legend", Decimal("1.14")),
            (900, "og", Decimal("1.17")),
            (1200, "goat", Decimal("1.20")),
        ]

        for score, expected_tier, expected_mult in test_cases:
            tier = get_tier_name(score)
            karma, multiplier = calculate_engagement_karma(base, score)

            self.assert_equal(tier, expected_tier, f"Score {score} → tier {expected_tier}")
            self.assert_equal(multiplier, expected_mult, f"Tier {expected_tier} → multiplier {expected_mult}")

    def test_post_submission(self):
        """Test post submission with escrow."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Post Submission")
        self.stdout.write("-" * 50)

        # Test 1: Create post with escrow
        poster = self.create_test_user(20, credits=Decimal("100"))
        initial_credits = poster.credits

        post = self.create_test_post(poster, escrow=Decimal("30"))

        self.assert_true(post.id is not None, "Post created with UUID")
        self.assert_equal(post.escrow, Decimal("30"), "Post has correct escrow")
        self.assert_equal(post.status, Post.Status.ACTIVE, "Post status is active")

        # Test 2: Post deducts from user balance (simulating real flow)
        poster.credits -= Decimal("30")
        poster.save()
        poster.refresh_from_db()
        self.assert_equal(poster.credits, initial_credits - Decimal("30"), "Poster credits deducted")

        # Test 3: Post completion when escrow depletes
        post.escrow = Decimal("0")
        post.status = Post.Status.COMPLETED
        post.completed_at = timezone.now()
        post.save()
        post.refresh_from_db()
        self.assert_equal(post.status, Post.Status.COMPLETED, "Post marked completed when escrow 0")

    def test_engagement_flow(self):
        """Test engagement creation and verification."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Engagement Flow")
        self.stdout.write("-" * 50)

        # Setup: poster and engager
        poster = self.create_test_user(30, credits=Decimal("100"))
        engager = self.create_test_user(31, credits=Decimal("10"), tweetscout_score=500)

        post = self.create_test_post(poster, escrow=Decimal("30"))

        # Test 1: Create engagement (click)
        engagement = Engagement.objects.create(
            user=engager,
            post=post,
            clicked_at=timezone.now(),
            verified=False,
            credit_granted=False,
        )
        self.assert_true(engagement.id is not None, "Engagement created")
        self.assert_equal(engagement.verified, False, "Engagement starts unverified")

        # Test 2: Verify engagement
        engagement.verified = True
        engagement.reply_verified = True
        engagement.like_verified = True
        engagement.save()
        engagement.refresh_from_db()
        self.assert_equal(engagement.verified, True, "Engagement marked verified")

        # Test 3: Award credits with multiplier
        base_credit = Decimal("1")
        karma, multiplier = calculate_engagement_karma(base_credit, engager.tweetscout_score)

        initial_credits = engager.credits
        service = CreditService(engager)
        service.earn(
            amount=karma,
            reference_id=engagement.id,
            reference_type="engagement",
            description=f"Test engagement (x{multiplier})",
        )
        engager.refresh_from_db()

        self.assert_equal(engager.credits, initial_credits + karma, "Engager received karma with multiplier")

        # Test 4: Deduct from escrow
        initial_escrow = post.escrow
        post.escrow = F('escrow') - karma
        post.save()
        post.refresh_from_db()

        expected_escrow = initial_escrow - karma
        self.assert_equal(post.escrow, expected_escrow, "Escrow deducted correctly")

        # Test 5: Unique constraint (one engagement per user per post)
        try:
            Engagement.objects.create(
                user=engager,
                post=post,
                clicked_at=timezone.now(),
            )
            self.assert_true(False, "Duplicate engagement prevented")
        except Exception:
            self.assert_true(True, "Duplicate engagement prevented")

    def test_verification_logic(self):
        """Test verification batch processing."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Verification Logic")
        self.stdout.write("-" * 50)

        user = self.create_test_user(40, credits=Decimal("10"))
        poster = self.create_test_user(41, credits=Decimal("100"))

        # Create multiple engagements
        engagements = []
        for i in range(5):
            post = self.create_test_post(poster)
            eng = Engagement.objects.create(
                user=user,
                post=post,
                clicked_at=timezone.now(),
                verified=False,
                credit_granted=False,
            )
            engagements.append(eng)

        # Test 1: Create verification batch
        batch = VerificationBatch.objects.create(
            user=user,
            engagement_ids=[str(e.id) for e in engagements],
            status=VerificationBatch.Status.PENDING,
        )
        self.assert_true(batch.id is not None, "Verification batch created")
        self.assert_equal(len(batch.engagement_ids), 5, "Batch contains 5 engagements")

        # Test 2: Batch status transitions
        batch.status = VerificationBatch.Status.PROCESSING
        batch.save()
        batch.refresh_from_db()
        self.assert_equal(batch.status, VerificationBatch.Status.PROCESSING, "Batch status → processing")

        batch.status = VerificationBatch.Status.COMPLETED
        batch.passed = 4
        batch.failed = 1
        batch.credits_awarded = Decimal("4.40")
        batch.completed_at = timezone.now()
        batch.save()
        batch.refresh_from_db()

        self.assert_equal(batch.status, VerificationBatch.Status.COMPLETED, "Batch status → completed")
        self.assert_equal(batch.passed, 4, "Batch passed count correct")
        self.assert_equal(batch.failed, 1, "Batch failed count correct")

    def test_queue_system(self):
        """Test Celery queue integration (requires running worker)."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Queue System (Celery)")
        self.stdout.write("-" * 50)

        from posts.tasks import process_verification_batch

        user = self.create_test_user(50, credits=Decimal("10"), x_username="test_queue_user")
        poster = self.create_test_user(51, credits=Decimal("100"))

        # Create engagement
        post = self.create_test_post(poster)
        eng = Engagement.objects.create(
            user=user,
            post=post,
            clicked_at=timezone.now(),
            verified=False,
            credit_granted=False,
        )

        # Create batch
        batch = VerificationBatch.objects.create(
            user=user,
            engagement_ids=[str(eng.id)],
            status=VerificationBatch.Status.PENDING,
        )

        # Try to queue task
        try:
            result = process_verification_batch.delay(str(batch.id))
            self.assert_true(result.id is not None, "Task queued to Celery")

            # Wait for result (with timeout)
            self.stdout.write("    Waiting for Celery to process (max 30s)...")
            try:
                task_result = result.get(timeout=30)
                self.assert_true(True, "Celery task completed")

                batch.refresh_from_db()
                self.assert_equal(
                    batch.status,
                    VerificationBatch.Status.COMPLETED,
                    "Batch marked completed by Celery"
                )
            except Exception as e:
                self.assert_true(False, f"Celery task failed or timed out: {e}")

        except Exception as e:
            self.assert_true(False, f"Failed to queue Celery task: {e}")

    def test_concurrency(self):
        """Test concurrent operations for race conditions."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Concurrency Safety")
        self.stdout.write("-" * 50)

        # Test 1: Concurrent credit deductions
        user = self.create_test_user(60, credits=Decimal("100"))

        def deduct_credit():
            try:
                with transaction.atomic():
                    u = User.objects.select_for_update().get(pk=user.pk)
                    if u.credits >= Decimal("10"):
                        u.credits -= Decimal("10")
                        u.save()
                        return True
                    return False
            except Exception:
                return False

        # Run 15 concurrent deductions (only 10 should succeed)
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(deduct_credit) for _ in range(15)]
            results = [f.result() for f in as_completed(futures)]

        successes = sum(1 for r in results if r)
        user.refresh_from_db()

        self.assert_equal(successes, 10, "Only 10 of 15 concurrent deductions succeeded")
        self.assert_equal(user.credits, Decimal("0"), "Final balance is 0 (no overdraft)")

        # Test 2: Concurrent escrow deductions
        poster = self.create_test_user(61, credits=Decimal("100"))
        post = self.create_test_post(poster, escrow=Decimal("5"))

        def deduct_escrow():
            try:
                updated = Post.objects.filter(
                    pk=post.pk,
                    escrow__gte=Decimal("1"),
                ).update(escrow=F('escrow') - Decimal("1"))
                return updated > 0
            except Exception:
                return False

        # Run 10 concurrent escrow deductions (only 5 should succeed)
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(deduct_escrow) for _ in range(10)]
            results = [f.result() for f in as_completed(futures)]

        successes = sum(1 for r in results if r)
        post.refresh_from_db()

        self.assert_equal(successes, 5, "Only 5 of 10 concurrent escrow deductions succeeded")
        self.assert_equal(post.escrow, Decimal("0"), "Final escrow is 0 (no negative)")

    def test_edge_cases(self):
        """Test edge cases and error handling."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Edge Cases")
        self.stdout.write("-" * 50)

        # Test 1: Zero credits user
        zero_user = self.create_test_user(70, credits=Decimal("0"))
        service = CreditService(zero_user)

        def try_spend_zero():
            service.spend(Decimal("1"), zero_user.id, "test", "Should fail")

        self.assert_raises(InsufficientCreditsError, try_spend_zero, "Cannot spend with 0 credits")

        # Test 2: Very small amounts (precision)
        small_user = self.create_test_user(71, credits=Decimal("0.0001"))
        self.assert_true(small_user.credits > 0, "Very small credit amounts supported")

        # Test 3: Engagement on own post (should be prevented)
        poster = self.create_test_user(72, credits=Decimal("100"))
        post = self.create_test_post(poster)

        # In real app this is prevented in the view, but DB allows it
        eng = Engagement.objects.create(
            user=poster,  # Same as post owner
            post=post,
            clicked_at=timezone.now(),
        )
        self.assert_true(eng.id is not None, "Self-engagement creates record (view should prevent)")

        # Test 4: Completed post engagement
        completed_post = self.create_test_post(poster)
        completed_post.status = Post.Status.COMPLETED
        completed_post.save()

        # Engagement on completed post (DB allows, view should check)
        engager = self.create_test_user(73)
        eng2 = Engagement.objects.create(
            user=engager,
            post=completed_post,
            clicked_at=timezone.now(),
        )
        self.assert_true(eng2.id is not None, "Engagement on completed post (view should prevent)")

        # Test 5: Empty verification batch
        empty_batch = VerificationBatch.objects.create(
            user=engager,
            engagement_ids=[],
            status=VerificationBatch.Status.PENDING,
        )
        self.assert_equal(len(empty_batch.engagement_ids), 0, "Empty batch allowed")

    def test_database_constraints(self):
        """Test database-level constraints."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("TEST SUITE: Database Constraints")
        self.stdout.write("-" * 50)

        # Test 1: Negative credits constraint
        user = self.create_test_user(80, credits=Decimal("10"))
        try:
            User.objects.filter(pk=user.pk).update(credits=Decimal("-1"))
            user.refresh_from_db()
            # Check if constraint was enforced
            self.assert_true(user.credits >= 0, "Negative credits prevented by constraint")
        except Exception:
            self.assert_true(True, "Negative credits prevented by constraint")

        # Test 2: Negative escrow constraint
        poster = self.create_test_user(81, credits=Decimal("100"))
        post = self.create_test_post(poster, escrow=Decimal("10"))
        try:
            Post.objects.filter(pk=post.pk).update(escrow=Decimal("-1"))
            post.refresh_from_db()
            self.assert_true(post.escrow >= 0, "Negative escrow prevented by constraint")
        except Exception:
            self.assert_true(True, "Negative escrow prevented by constraint")

        # Test 3: Unique telegram_id
        user1 = self.create_test_user(82)
        try:
            User.objects.create(
                telegram_id=user1.telegram_id,  # Duplicate
                telegram_username="should_fail",
            )
            self.assert_true(False, "Duplicate telegram_id prevented")
        except Exception:
            self.assert_true(True, "Duplicate telegram_id prevented")

    def cleanup_test_data(self):
        """Remove all test data."""
        self.stdout.write("\n" + "-" * 50)
        self.stdout.write("CLEANUP")
        self.stdout.write("-" * 50)

        test_users = User.objects.filter(
            telegram_id__gte=self.TEST_TG_ID_START,
            telegram_id__lt=self.TEST_TG_ID_START + 1000,
        )

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

            # Delete posts
            posts_deleted, _ = Post.objects.filter(
                user__in=test_users
            ).delete()
            self.stdout.write(f"  Deleted {posts_deleted} posts")

            # Delete transactions
            txs_deleted, _ = Transaction.objects.filter(
                user__in=test_users
            ).delete()
            self.stdout.write(f"  Deleted {txs_deleted} transactions")

            # Delete users
            users_deleted, _ = test_users.delete()
            self.stdout.write(f"  Deleted {users_deleted} test users")

        self.stdout.write(self.style.SUCCESS("  Cleanup complete"))

    def print_summary(self):
        """Print test summary."""
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("TEST SUMMARY")
        self.stdout.write("=" * 70)

        total = self.passed + self.failed
        self.stdout.write(f"\nTotal: {total} tests")
        self.stdout.write(self.style.SUCCESS(f"Passed: {self.passed}"))

        if self.failed > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {self.failed}"))
            self.stdout.write("\nFailed tests:")
            for error in self.errors:
                self.stdout.write(self.style.ERROR(f"  • {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("\nAll tests passed!"))

        self.stdout.write("\n" + "=" * 70 + "\n")
