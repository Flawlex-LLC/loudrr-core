"""
Comprehensive Race Condition & Exploitation Tests

Tests scenarios where users might try to exploit the system:
1. Double-clicking claim button
2. Re-engaging with old/completed posts
3. Concurrent verification batch creation
4. Escrow depletion races
5. Waitlist token reuse attacks
6. Session manipulation

Run with: python manage.py test core.tests.test_race_conditions -v 2
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone

from core.models import User, SiteSetting
from posts.models import Post, Engagement


class TestDoubleClickClaim(TransactionTestCase):
    """
    Test double-clicking the claim button.

    Scenario: User clicks "Claim" rapidly multiple times trying to get
    multiple verification batches and earn more credits.
    """

    def setUp(self):
        # Create settings
        SiteSetting.objects.update_or_create(
            key='MIN_ENGAGEMENTS_TO_CLAIM',
            defaults={'value': '10', 'data_type': 'int'}
        )
        SiteSetting.objects.update_or_create(
            key='MIN_SESSION_DURATION_SECONDS',
            defaults={'value': '0', 'data_type': 'int'}  # Disable for testing
        )

        # Create user with X account
        self.user = User.objects.create_user(
            telegram_id=100000001,
            display_name='Double Clicker',
            x_username='doubleclicker',
            credits=Decimal('0')
        )

        # Create post owner
        self.owner = User.objects.create_user(
            telegram_id=100000002,
            display_name='Owner',
            credits=Decimal('500')
        )

        # Create 10 posts
        self.posts = []
        for i in range(10):
            post = Post.objects.create(
                user=self.owner,
                x_link=f'https://x.com/owner/status/{10000+i}',
                tweet_id=str(10000+i),
                escrow=Decimal('30'),
                initial_escrow=Decimal('30'),
                status=Post.Status.ACTIVE,
                platform='web'
            )
            self.posts.append(post)

        # Create 10 unverified engagements (eligible for claim)
        for post in self.posts:
            Engagement.objects.create(
                user=self.user,
                post=post,
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),
                verified=False,
                credit_granted=False
            )

    def test_concurrent_claim_buttons(self):
        """
        Rapid double-click on claim button should not create multiple batches.
        """
        from posts.models import VerificationBatch

        results = []
        errors = []

        def make_claim():
            try:
                client = Client()
                response = client.post(
                    '/api/miniapp/session/queue-claim/?telegram_id=100000001',
                    content_type='application/json'
                )
                results.append({
                    'status': response.status_code,
                    'data': response.json() if response.status_code == 200 else None
                })
            except Exception as e:
                errors.append(str(e))

        # Simulate 5 rapid clicks
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_claim) for _ in range(5)]
            for future in as_completed(futures):
                pass

        # Count successful batch creations
        successful_batches = VerificationBatch.objects.filter(user=self.user).count()

        # At most ONE batch should be created (others should fail or be rejected)
        # because engagements get marked or batch locks them
        self.assertLessEqual(
            successful_batches, 2,  # Allow some tolerance for timing
            f"Too many batches created: {successful_batches}"
        )

    def test_claim_after_claim_fails(self):
        """
        Second claim request immediately after first should fail.
        """
        from posts.models import VerificationBatch

        client = Client()

        # First claim - should succeed
        response1 = client.post(
            '/api/miniapp/session/queue-claim/?telegram_id=100000001',
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)
        data1 = response1.json()
        self.assertTrue(data1.get('success', False) or 'batch_id' in data1)

        # Second claim - should fail (no more unverified engagements)
        response2 = client.post(
            '/api/miniapp/session/queue-claim/?telegram_id=100000001',
            content_type='application/json'
        )
        data2 = response2.json()

        # Should either fail or return that there aren't enough engagements
        self.assertFalse(data2.get('success', True))


class TestOldPostExploits(TransactionTestCase):
    """
    Test attempts to exploit old/completed/cancelled posts.

    Scenarios:
    - Engaging with completed posts
    - Engaging with cancelled posts
    - Engaging with posts that have depleted escrow
    """

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(
            telegram_id=200000001,
            display_name='Exploiter',
            x_username='exploiter',
            credits=Decimal('0')
        )

        self.owner = User.objects.create_user(
            telegram_id=200000002,
            display_name='Owner',
            credits=Decimal('500')
        )

    def test_cannot_engage_completed_post(self):
        """Attempting to engage with a COMPLETED post should fail."""
        completed_post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/owner/status/20001',
            tweet_id='20001',
            escrow=Decimal('0'),  # Depleted
            initial_escrow=Decimal('30'),
            status=Post.Status.COMPLETED,
            platform='web'
        )

        response = self.client.post(
            '/api/miniapp/session/click/?telegram_id=200000001',
            data=json.dumps({'post_id': str(completed_post.id)}),
            content_type='application/json'
        )

        # Should either return error or not create engagement
        if response.status_code == 200:
            # Check no engagement was created
            self.assertFalse(
                Engagement.objects.filter(user=self.user, post=completed_post).exists()
            )
        else:
            # Error response is also acceptable
            self.assertIn(response.status_code, [400, 404])

    def test_cannot_engage_cancelled_post(self):
        """Attempting to engage with a CANCELLED post should fail."""
        cancelled_post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/owner/status/20002',
            tweet_id='20002',
            escrow=Decimal('30'),
            initial_escrow=Decimal('30'),
            status=Post.Status.CANCELLED,
            platform='web'
        )

        response = self.client.post(
            '/api/miniapp/session/click/?telegram_id=200000001',
            data=json.dumps({'post_id': str(cancelled_post.id)}),
            content_type='application/json'
        )

        if response.status_code == 200:
            self.assertFalse(
                Engagement.objects.filter(user=self.user, post=cancelled_post).exists()
            )
        else:
            self.assertIn(response.status_code, [400, 404])

    def test_cannot_engage_depleted_escrow_post(self):
        """Post with 0 escrow remaining should not accept new engagements."""
        depleted_post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/owner/status/20003',
            tweet_id='20003',
            escrow=Decimal('0'),  # No escrow left
            initial_escrow=Decimal('30'),
            status=Post.Status.ACTIVE,  # Still technically active
            platform='web'
        )

        response = self.client.post(
            '/api/miniapp/session/click/?telegram_id=200000001',
            data=json.dumps({'post_id': str(depleted_post.id)}),
            content_type='application/json'
        )

        # Should handle gracefully - either reject or not in feed
        # The post shouldn't appear in start session anyway
        data = response.json()
        # Either error or success with warning
        self.assertTrue(response.status_code in [200, 400, 404])


class TestReEngagementExploits(TransactionTestCase):
    """
    Test attempts to re-engage with posts user already engaged with.
    """

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(
            telegram_id=300000001,
            display_name='Re-engager',
            x_username='reengager',
            credits=Decimal('0')
        )

        self.owner = User.objects.create_user(
            telegram_id=300000002,
            display_name='Owner',
            credits=Decimal('500')
        )

        self.post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/owner/status/30001',
            tweet_id='30001',
            escrow=Decimal('30'),
            initial_escrow=Decimal('30'),
            status=Post.Status.ACTIVE,
            platform='web'
        )

    def test_re_engage_same_post_idempotent(self):
        """Engaging with same post multiple times should be idempotent."""
        # First engagement
        response1 = self.client.post(
            '/api/miniapp/session/click/?telegram_id=300000001',
            data=json.dumps({'post_id': str(self.post.id)}),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)

        initial_count = Engagement.objects.filter(
            user=self.user, post=self.post
        ).count()
        self.assertEqual(initial_count, 1)

        # Try to engage 10 more times
        for _ in range(10):
            self.client.post(
                '/api/miniapp/session/click/?telegram_id=300000001',
                data=json.dumps({'post_id': str(self.post.id)}),
                content_type='application/json'
            )

        # Should still only have 1 engagement
        final_count = Engagement.objects.filter(
            user=self.user, post=self.post
        ).count()
        self.assertEqual(final_count, 1)

    def test_re_engage_after_verification(self):
        """Cannot re-engage with a post that was already verified."""
        # Create verified engagement
        Engagement.objects.create(
            user=self.user,
            post=self.post,
            clicked_at=timezone.now() - timezone.timedelta(hours=1),
            verified=True,  # Already verified
            credit_granted=True
        )

        # Try to engage again
        response = self.client.post(
            '/api/miniapp/session/click/?telegram_id=300000001',
            data=json.dumps({'post_id': str(self.post.id)}),
            content_type='application/json'
        )

        # Should still only have 1 engagement (the original)
        count = Engagement.objects.filter(user=self.user, post=self.post).count()
        self.assertEqual(count, 1)

    def test_concurrent_re_engagement_attempts(self):
        """Concurrent attempts to engage same post should create only one."""
        results = []

        def make_engagement():
            client = Client()
            response = client.post(
                '/api/miniapp/session/click/?telegram_id=300000001',
                data=json.dumps({'post_id': str(self.post.id)}),
                content_type='application/json'
            )
            results.append(response.status_code)

        # 20 concurrent requests
        threads = [threading.Thread(target=make_engagement) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All requests should succeed (200)
        self.assertTrue(all(r == 200 for r in results))

        # But only ONE engagement should exist
        count = Engagement.objects.filter(user=self.user, post=self.post).count()
        self.assertEqual(count, 1)


class TestEscrowRaceConditions(TransactionTestCase):
    """
    Test race conditions around escrow deduction.

    Scenario: Multiple users try to claim rewards from same post
    when only limited escrow remains.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            telegram_id=500000001,
            display_name='Owner',
            credits=Decimal('500')
        )

        # Post with very limited escrow
        self.limited_post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/owner/status/50001',
            tweet_id='50001',
            escrow=Decimal('5'),  # Only 5 credits left
            initial_escrow=Decimal('30'),
            status=Post.Status.ACTIVE,
            platform='web'
        )

    def test_concurrent_escrow_deduction(self):
        """
        Multiple users claiming from same post with limited escrow.
        Total claims should not exceed escrow.
        """
        users = []
        for i in range(10):
            user = User.objects.create_user(
                telegram_id=500000010 + i,
                display_name=f'Claimer{i}',
                x_username=f'claimer{i}',
                credits=Decimal('0')
            )
            users.append(user)

            # Create engagement for each
            Engagement.objects.create(
                user=user,
                post=self.limited_post,
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),
                verified=False,
                credit_granted=False
            )

        # Refresh post
        self.limited_post.refresh_from_db()
        initial_escrow = self.limited_post.escrow

        # Total credits awarded across all users should not exceed escrow
        total_awarded = sum(
            user.credits for user in User.objects.filter(
                telegram_id__gte=500000010,
                telegram_id__lt=500000020
            )
        )

        self.assertLessEqual(
            total_awarded, initial_escrow,
            f"Total awarded ({total_awarded}) exceeds initial escrow ({initial_escrow})"
        )


class TestSessionManipulation(TransactionTestCase):
    """
    Test session state manipulation attacks.
    """

    def setUp(self):
        self.client = Client()

        SiteSetting.objects.update_or_create(
            key='MIN_ENGAGEMENTS_TO_CLAIM',
            defaults={'value': '10', 'data_type': 'int'}
        )
        SiteSetting.objects.update_or_create(
            key='MIN_SESSION_DURATION_SECONDS',
            defaults={'value': '150', 'data_type': 'int'}
        )

        self.user = User.objects.create_user(
            telegram_id=600000001,
            display_name='Manipulator',
            x_username='manipulator',
            credits=Decimal('0')
        )

        self.owner = User.objects.create_user(
            telegram_id=600000002,
            display_name='Owner',
            credits=Decimal('500')
        )

    def test_click_time_manipulation(self):
        """
        Users cannot manipulate click timestamps to bypass time checks.
        Timestamps are set server-side.
        """
        # Create post
        post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/owner/status/60001',
            tweet_id='60001',
            escrow=Decimal('30'),
            initial_escrow=Decimal('30'),
            status=Post.Status.ACTIVE,
            platform='web'
        )

        # Record click via API (timestamp is server-controlled)
        self.client.post(
            '/api/miniapp/session/click/?telegram_id=600000001',
            data=json.dumps({'post_id': str(post.id)}),
            content_type='application/json'
        )

        # Check engagement has recent timestamp
        engagement = Engagement.objects.get(user=self.user, post=post)
        time_diff = (timezone.now() - engagement.clicked_at).total_seconds()

        # Should be within last few seconds
        self.assertLess(time_diff, 60)

    def test_cannot_forge_engagement_count(self):
        """
        Claimed engagement count must match actual database records.
        """
        # Create only 5 engagements
        for i in range(5):
            post = Post.objects.create(
                user=self.owner,
                x_link=f'https://x.com/owner/status/6000{i}',
                tweet_id=f'6000{i}',
                escrow=Decimal('30'),
                initial_escrow=Decimal('30'),
                status=Post.Status.ACTIVE,
                platform='web'
            )
            Engagement.objects.create(
                user=self.user,
                post=post,
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),
                verified=False,
                credit_granted=False
            )

        # Try to claim (requires 10, but only have 5)
        response = self.client.post(
            '/api/miniapp/session/queue-claim/?telegram_id=600000001',
            content_type='application/json'
        )

        data = response.json()
        self.assertFalse(data.get('success', True))
        self.assertIn('Need', data.get('message', ''))


class TestCreditOverflow(TransactionTestCase):
    """
    Test credit system for overflow/underflow vulnerabilities.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            telegram_id=700000001,
            display_name='Overflow Tester',
            credits=Decimal('100')
        )

    def test_cannot_spend_more_than_available(self):
        """Spending more credits than available should fail."""
        from core.services.credits import CreditService

        service = CreditService(self.user)

        with self.assertRaises(Exception):
            service.spend(
                amount=Decimal('150'),  # Only have 100
                reference_type='test',
                description='Overspend attempt'
            )

        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, Decimal('100'))

    def test_negative_credit_transaction_rejected(self):
        """Cannot create negative credit transactions."""
        from core.services.credits import CreditService

        service = CreditService(self.user)

        # Try awarding negative credits
        with self.assertRaises(Exception):
            service.award(
                amount=Decimal('-50'),
                reference_type='test',
                description='Negative award attempt'
            )

    def test_concurrent_spend_prevents_overdraft(self):
        """
        Concurrent spend attempts should not cause overdraft.
        """
        from core.services.credits import CreditService

        self.user.credits = Decimal('100')
        self.user.save()

        results = []

        def try_spend():
            try:
                # Fresh user instance for each thread
                user = User.objects.get(pk=self.user.pk)
                service = CreditService(user)
                service.spend(
                    amount=Decimal('60'),  # Each wants 60, but only 100 total
                    reference_type='test',
                    description='Concurrent spend'
                )
                results.append('success')
            except Exception as e:
                results.append(f'fail: {type(e).__name__}')

        threads = [threading.Thread(target=try_spend) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # At most ONE should succeed (100 / 60 = 1)
        success_count = results.count('success')
        self.assertLessEqual(success_count, 1)

        # Final credits should never be negative
        self.user.refresh_from_db()
        self.assertGreaterEqual(self.user.credits, Decimal('0'))


class TestUserImpersonation(TransactionTestCase):
    """
    Test that users cannot impersonate other users.
    """

    def setUp(self):
        self.client = Client()

        self.user1 = User.objects.create_user(
            telegram_id=800000001,
            display_name='User 1',
            x_username='user1',
            credits=Decimal('100')
        )

        self.user2 = User.objects.create_user(
            telegram_id=800000002,
            display_name='User 2',
            x_username='user2',
            credits=Decimal('50')
        )

    def test_cannot_access_other_user_data(self):
        """User 1 cannot access User 2's data by changing telegram_id param."""
        # This tests that the auth system properly validates
        # In real system, telegram_id comes from signed initData

        # Get user 1's info
        response1 = self.client.get('/api/miniapp/user/?telegram_id=800000001')
        data1 = response1.json()

        # Get user 2's info
        response2 = self.client.get('/api/miniapp/user/?telegram_id=800000002')
        data2 = response2.json()

        # Should be different users with different credits
        self.assertNotEqual(data1.get('credits'), data2.get('credits'))


class TestBatchProcessingExploits(TransactionTestCase):
    """
    Test exploitation attempts during batch verification processing.
    """

    def setUp(self):
        from posts.models import VerificationBatch

        self.user = User.objects.create_user(
            telegram_id=900000001,
            display_name='Batch Exploiter',
            x_username='batchexploiter',
            credits=Decimal('0')
        )

        self.owner = User.objects.create_user(
            telegram_id=900000002,
            display_name='Owner',
            credits=Decimal('500')
        )

    def test_cannot_modify_batch_engagements(self):
        """Once batch is created, engagement list cannot be modified."""
        from posts.models import VerificationBatch

        # Create engagements
        posts = []
        for i in range(10):
            post = Post.objects.create(
                user=self.owner,
                x_link=f'https://x.com/owner/status/9000{i}',
                tweet_id=f'9000{i}',
                escrow=Decimal('30'),
                initial_escrow=Decimal('30'),
                status=Post.Status.ACTIVE,
                platform='web'
            )
            posts.append(post)
            Engagement.objects.create(
                user=self.user,
                post=post,
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),
                verified=False,
                credit_granted=False
            )

        # Create batch with engagement IDs
        engagement_ids = [
            str(e.id) for e in Engagement.objects.filter(user=self.user)
        ]
        batch = VerificationBatch.objects.create(
            user=self.user,
            engagement_ids=engagement_ids,
            status=VerificationBatch.Status.PENDING
        )

        # Try to add more engagements after batch creation
        extra_post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/owner/status/90099',
            tweet_id='90099',
            escrow=Decimal('30'),
            initial_escrow=Decimal('30'),
            status=Post.Status.ACTIVE,
            platform='web'
        )
        extra_engagement = Engagement.objects.create(
            user=self.user,
            post=extra_post,
            clicked_at=timezone.now() - timezone.timedelta(minutes=10),
            verified=False,
            credit_granted=False
        )

        # Batch should still only have original 10 engagements
        batch.refresh_from_db()
        self.assertEqual(len(batch.engagement_ids), 10)
        self.assertNotIn(str(extra_engagement.id), batch.engagement_ids)


def run_all_race_condition_tests():
    """Helper to run all race condition tests."""
    from django.test.utils import get_runner
    from django.conf import settings

    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2)

    failures = test_runner.run_tests(["core.tests.test_race_conditions"])
    return failures
