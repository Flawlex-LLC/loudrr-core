"""
End-to-End Gaming & Security Tests

Tests the entire flow from frontend perspective, attempting to:
1. Game the system (duplicate clicks, fast verification, etc.)
2. Test race conditions (concurrent requests)
3. Verify all security measures work
4. Test edge cases

Run with: python manage.py test core.tests.test_e2e_gaming -v 2
"""
import json
import time
import threading
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.db import connection

from core.models import User, Transaction, SiteSetting
from posts.models import Post, Engagement
from core.services.credits import CreditService


class TestUserSetup(TestCase):
    """Test user creation and setup."""

    def setUp(self):
        self.client = Client()

    def test_get_user_creates_new_user(self):
        """GET /user/ should create user if telegram_id provided."""
        response = self.client.get('/api/miniapp/user/?telegram_id=999999999')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('credits', data)
        self.assertEqual(data['credits'], 0)

        # User should exist in DB
        self.assertTrue(User.objects.filter(telegram_id=999999999).exists())

    def test_get_user_returns_existing_user(self):
        """GET /user/ should return existing user."""
        user = User.objects.create_user(
            telegram_id=888888888,
            display_name='Test User',
            credits=Decimal('100')
        )

        response = self.client.get('/api/miniapp/user/?telegram_id=888888888')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['credits'], 100)


class TestEngagementFlow(TransactionTestCase):
    """Test the full engagement flow."""

    def setUp(self):
        self.client = Client()

        # Create test user with X account
        self.user = User.objects.create_user(
            telegram_id=111111111,
            display_name='Engager',
            x_username='test_engager',
            credits=Decimal('0')
        )

        # Create post owner
        self.owner = User.objects.create_user(
            telegram_id=222222222,
            display_name='Post Owner',
            x_username='post_owner',
            credits=Decimal('100')
        )

        # Create active posts
        self.posts = []
        for i in range(15):
            post = Post.objects.create(
                user=self.owner,
                x_link=f'https://x.com/test/status/{1000+i}',
                tweet_id=str(1000+i),
                escrow=Decimal('30'),
                initial_escrow=Decimal('30'),
                status=Post.Status.ACTIVE,
                platform='web'
            )
            self.posts.append(post)

    def test_start_session_returns_posts(self):
        """Start session should return up to 10 posts."""
        response = self.client.post(
            '/api/miniapp/session/start/',
            content_type='application/json',
            HTTP_X_TELEGRAM_ID='111111111'
        )
        response = self.client.post(
            '/api/miniapp/session/start/?telegram_id=111111111',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn('posts', data)
        self.assertLessEqual(len(data['posts']), 10)
        self.assertEqual(data['pending_count'], 0)
        self.assertFalse(data['show_verification'])

    def test_record_click_creates_engagement(self):
        """Recording a click should create an engagement."""
        post = self.posts[0]

        response = self.client.post(
            f'/api/miniapp/session/click/?telegram_id=111111111',
            data=json.dumps({'post_id': str(post.id)}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(data['pending_count'], 1)

        # Engagement should exist
        self.assertTrue(Engagement.objects.filter(
            user=self.user,
            post=post,
            verified=False
        ).exists())

    def test_duplicate_click_is_idempotent(self):
        """Clicking same post twice should not create duplicate."""
        post = self.posts[0]

        # First click
        response1 = self.client.post(
            f'/api/miniapp/session/click/?telegram_id=111111111',
            data=json.dumps({'post_id': str(post.id)}),
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, 200)

        # Second click - should not fail
        response2 = self.client.post(
            f'/api/miniapp/session/click/?telegram_id=111111111',
            data=json.dumps({'post_id': str(post.id)}),
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)

        # Should still only have 1 engagement
        count = Engagement.objects.filter(user=self.user, post=post).count()
        self.assertEqual(count, 1)

    def test_cannot_engage_own_post(self):
        """User should not be able to engage their own post."""
        # Create user's own post
        own_post = Post.objects.create(
            user=self.user,  # Same as engager
            x_link='https://x.com/test/status/9999',
            tweet_id='9999',
            escrow=Decimal('30'),
            initial_escrow=Decimal('30'),
            status=Post.Status.ACTIVE,
            platform='web'
        )

        response = self.client.post(
            f'/api/miniapp/session/click/?telegram_id=111111111',
            data=json.dumps({'post_id': str(own_post.id)}),
            content_type='application/json'
        )

        # Should return error or just not create engagement
        # The exact behavior depends on implementation
        if response.status_code == 200:
            data = response.json()
            # If success, check no engagement was created
            self.assertFalse(Engagement.objects.filter(
                user=self.user,
                post=own_post
            ).exists())


class TestVerificationSecurity(TransactionTestCase):
    """Test verification security measures."""

    def setUp(self):
        self.client = Client()

        # Ensure settings exist
        SiteSetting.objects.update_or_create(
            key='VERIFICATION_BATCH_SIZE',
            defaults={'value': '10', 'data_type': 'int'}
        )
        SiteSetting.objects.update_or_create(
            key='VERIFICATION_SAMPLE_SIZE',
            defaults={'value': '3', 'data_type': 'int'}
        )
        SiteSetting.objects.update_or_create(
            key='MIN_SESSION_DURATION_SECONDS',
            defaults={'value': '150', 'data_type': 'int'}
        )

        # Create user WITHOUT X account
        self.user_no_x = User.objects.create_user(
            telegram_id=333333333,
            display_name='No X Account',
            x_username='',  # No X account!
            credits=Decimal('0')
        )

        # Create user WITH X account
        self.user_with_x = User.objects.create_user(
            telegram_id=444444444,
            display_name='Has X Account',
            x_username='real_user',
            credits=Decimal('0')
        )

        # Create post owner
        self.owner = User.objects.create_user(
            telegram_id=555555555,
            display_name='Owner',
            x_username='owner',
            credits=Decimal('500')
        )

        # Create posts
        self.posts = []
        for i in range(15):
            post = Post.objects.create(
                user=self.owner,
                x_link=f'https://x.com/owner/status/{2000+i}',
                tweet_id=str(2000+i),
                escrow=Decimal('30'),
                initial_escrow=Decimal('30'),
                status=Post.Status.ACTIVE,
                platform='web'
            )
            self.posts.append(post)

    def test_verification_requires_x_account(self):
        """Verification should fail without X account linked."""
        # Create 10 engagements for user without X
        for i in range(10):
            Engagement.objects.create(
                user=self.user_no_x,
                post=self.posts[i],
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),
                verified=False,
                credit_granted=False
            )

        response = self.client.post(
            '/api/miniapp/session/complete/?telegram_id=333333333',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['error'], 'x_account_required')

    def test_verification_requires_minimum_time(self):
        """Verification should fail if too fast."""
        # Create 10 engagements for user WITH X, but just now (too fast)
        for i in range(10):
            Engagement.objects.create(
                user=self.user_with_x,
                post=self.posts[i],
                clicked_at=timezone.now(),  # Just now - too fast!
                verified=False,
                credit_granted=False
            )

        response = self.client.post(
            '/api/miniapp/session/complete/?telegram_id=444444444',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['error'], 'insufficient_engagement_time')
        self.assertIn('remaining_seconds', data)

    def test_verification_passes_with_sufficient_time(self):
        """Verification should pass if enough time elapsed."""
        # Create 10 engagements with old timestamp (sufficient time)
        for i in range(10):
            Engagement.objects.create(
                user=self.user_with_x,
                post=self.posts[i],
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),  # 10 min ago
                verified=False,
                credit_granted=False
            )

        # Mock Twitter verification to pass
        with patch('miniapp.views.twitter_verification') as mock_tv:
            mock_tv.extract_tweet_id.return_value = '2000'
            mock_tv.verify_engagement_sync.return_value = {
                'passed': True,
                'like_verified': True,
                'reply_verified': True,
                'skipped': False
            }

            response = self.client.post(
                '/api/miniapp/session/complete/?telegram_id=444444444',
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertGreater(data['credits_awarded'], 0)

    def test_verification_needs_10_engagements(self):
        """Verification should fail with less than 10 engagements."""
        # Create only 5 engagements
        for i in range(5):
            Engagement.objects.create(
                user=self.user_with_x,
                post=self.posts[i],
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),
                verified=False,
                credit_granted=False
            )

        response = self.client.post(
            '/api/miniapp/session/complete/?telegram_id=444444444',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Need 10 engagements', data['message'])


class TestConcurrencyRaceConditions(TransactionTestCase):
    """Test race conditions and concurrent access."""

    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            telegram_id=666666666,
            display_name='Concurrent User',
            x_username='concurrent',
            credits=Decimal('100')
        )

        # Create owner
        self.owner = User.objects.create_user(
            telegram_id=777777777,
            display_name='Owner',
            credits=Decimal('500')
        )

        # Create post
        self.post = Post.objects.create(
            user=self.owner,
            x_link='https://x.com/test/status/3000',
            tweet_id='3000',
            escrow=Decimal('30'),
            initial_escrow=Decimal('30'),
            status=Post.Status.ACTIVE,
            platform='web'
        )

    def test_concurrent_clicks_create_single_engagement(self):
        """Concurrent clicks on same post should only create one engagement."""
        results = []
        errors = []

        def make_click():
            try:
                client = Client()
                response = client.post(
                    f'/api/miniapp/session/click/?telegram_id=666666666',
                    data=json.dumps({'post_id': str(self.post.id)}),
                    content_type='application/json'
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Fire 10 concurrent requests
        threads = []
        for _ in range(10):
            t = threading.Thread(target=make_click)
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All should succeed (idempotent)
        self.assertEqual(len([r for r in results if r == 200]), 10)

        # But only ONE engagement should exist
        count = Engagement.objects.filter(user=self.user, post=self.post).count()
        self.assertEqual(count, 1)


class TestPostSubmission(TransactionTestCase):
    """Test post submission flow."""

    def setUp(self):
        self.client = Client()

        # Create settings
        SiteSetting.objects.update_or_create(
            key='POST_COST_MIN',
            defaults={'value': '20', 'data_type': 'int'}
        )
        SiteSetting.objects.update_or_create(
            key='POST_COST_MAX',
            defaults={'value': '40', 'data_type': 'int'}
        )

        # Create user with credits
        self.user = User.objects.create_user(
            telegram_id=888888888,
            display_name='Poster',
            x_username='poster',
            credits=Decimal('50')
        )

    def test_submit_post_deducts_credits(self):
        """Submitting a post should deduct credits."""
        initial_credits = self.user.credits

        response = self.client.post(
            '/api/miniapp/post/submit/?telegram_id=888888888',
            data=json.dumps({
                'x_link': 'https://x.com/poster/status/4000',
                'karma_amount': 25
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        # Check credits deducted
        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, initial_credits - Decimal('25'))

    def test_submit_post_fails_insufficient_credits(self):
        """Cannot submit post without enough credits."""
        # Set credits to less than minimum
        self.user.credits = Decimal('10')
        self.user.save()

        response = self.client.post(
            '/api/miniapp/post/submit/?telegram_id=888888888',
            data=json.dumps({
                'x_link': 'https://x.com/poster/status/4001',
                'karma_amount': 25
            }),
            content_type='application/json'
        )

        # Should fail
        data = response.json()
        self.assertFalse(data.get('success', True))

    def test_submit_post_validates_karma_range(self):
        """Karma amount must be within allowed range."""
        # Try to submit with too little karma
        response = self.client.post(
            '/api/miniapp/post/submit/?telegram_id=888888888',
            data=json.dumps({
                'x_link': 'https://x.com/poster/status/4002',
                'karma_amount': 5  # Below minimum (20)
            }),
            content_type='application/json'
        )

        data = response.json()
        self.assertFalse(data.get('success', True))


class TestGamingAttempts(TransactionTestCase):
    """Test various gaming/cheating attempts."""

    def setUp(self):
        self.client = Client()

        # Create settings
        for key, value in [
            ('VERIFICATION_BATCH_SIZE', '10'),
            ('VERIFICATION_SAMPLE_SIZE', '3'),
            ('MIN_SESSION_DURATION_SECONDS', '150'),
        ]:
            SiteSetting.objects.update_or_create(
                key=key,
                defaults={'value': value, 'data_type': 'int'}
            )

        # Create users
        self.user = User.objects.create_user(
            telegram_id=999999999,
            display_name='Gamer',
            x_username='gamer',
            credits=Decimal('0')
        )

        self.owner = User.objects.create_user(
            telegram_id=111222333,
            display_name='Owner',
            credits=Decimal('500')
        )

        # Create posts
        self.posts = []
        for i in range(20):
            post = Post.objects.create(
                user=self.owner,
                x_link=f'https://x.com/owner/status/{5000+i}',
                tweet_id=str(5000+i),
                escrow=Decimal('30'),
                initial_escrow=Decimal('30'),
                status=Post.Status.ACTIVE,
                platform='web'
            )
            self.posts.append(post)

    def test_cannot_verify_twice(self):
        """Already verified engagements should not grant double credits."""
        # Create 10 engagements with sufficient time
        for i in range(10):
            Engagement.objects.create(
                user=self.user,
                post=self.posts[i],
                clicked_at=timezone.now() - timezone.timedelta(minutes=10),
                verified=False,
                credit_granted=False
            )

        # Mock verification
        with patch('miniapp.views.twitter_verification') as mock_tv:
            mock_tv.extract_tweet_id.return_value = '5000'
            mock_tv.verify_engagement_sync.return_value = {
                'passed': True,
                'skipped': False
            }

            # First verification
            response1 = self.client.post(
                '/api/miniapp/session/complete/?telegram_id=999999999',
                content_type='application/json'
            )
            self.assertEqual(response1.status_code, 200)
            data1 = response1.json()
            first_credits = data1.get('credits_awarded', 0)

            # Second verification - should not grant more credits
            response2 = self.client.post(
                '/api/miniapp/session/complete/?telegram_id=999999999',
                content_type='application/json'
            )
            data2 = response2.json()

            # Should fail - not enough unverified engagements
            self.assertFalse(data2.get('success', True))

    def test_instant_verify_blocked(self):
        """Clicking 10 posts instantly and verifying should be blocked."""
        # Simulate clicking 10 posts very fast
        for post in self.posts[:10]:
            response = self.client.post(
                f'/api/miniapp/session/click/?telegram_id=999999999',
                data=json.dumps({'post_id': str(post.id)}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)

        # Immediately try to verify
        response = self.client.post(
            '/api/miniapp/session/complete/?telegram_id=999999999',
            content_type='application/json'
        )

        data = response.json()
        # Should be blocked by time check
        self.assertEqual(data.get('error'), 'insufficient_engagement_time')

    def test_completed_post_not_in_feed(self):
        """Completed posts should not appear in feed."""
        # Mark all posts as completed
        Post.objects.filter(id__in=[p.id for p in self.posts]).update(
            status=Post.Status.COMPLETED
        )

        response = self.client.post(
            '/api/miniapp/session/start/?telegram_id=999999999',
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should have no posts
        self.assertEqual(len(data['posts']), 0)


class TestCreditSystem(TransactionTestCase):
    """Test credit system integrity."""

    def setUp(self):
        self.user = User.objects.create_user(
            telegram_id=123123123,
            display_name='Credit Test',
            credits=Decimal('100')
        )

    def test_credits_cannot_go_negative(self):
        """Credits should never go below 0 (database constraint)."""
        service = CreditService(self.user)

        # Try to spend more than available
        with self.assertRaises(Exception):
            service.spend(
                amount=Decimal('200'),  # More than available
                reference_type='test',
                description='Test overspend'
            )

        # Credits should be unchanged
        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, Decimal('100'))

    def test_concurrent_spend_atomic(self):
        """Concurrent spend operations should be atomic."""
        # Set credits to exact amount
        self.user.credits = Decimal('50')
        self.user.save()

        results = []

        def try_spend():
            try:
                service = CreditService(User.objects.get(pk=self.user.pk))
                service.spend(
                    amount=Decimal('30'),
                    reference_type='test',
                    description='Concurrent spend'
                )
                results.append('success')
            except Exception as e:
                results.append(f'fail: {e}')

        # Two concurrent attempts to spend 30 each (but only 50 available)
        threads = [threading.Thread(target=try_spend) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly ONE should succeed
        successes = [r for r in results if r == 'success']
        self.assertEqual(len(successes), 1)

        # Final balance should be 20 (50 - 30)
        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, Decimal('20'))


def run_all_tests():
    """Helper to run all tests from shell."""
    import django
    from django.test.utils import get_runner
    from django.conf import settings

    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2)

    failures = test_runner.run_tests(["core.tests.test_e2e_gaming"])
    return failures