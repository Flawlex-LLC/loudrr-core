"""
Tests for the new Settlement and Verification services.

Run with: python manage.py test core.tests.test_settlement_verification -v 2

These tests verify:
1. VerificationService - Stateless, no DB writes
2. SettlementService - Atomic escrow+credit transfers
3. Feed filtering by user's tier multiplier
4. Post expiry with refund
5. Partial payment when escrow < full karma
6. No karma leak on errors (savepoint rollback)
"""
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core.models import User, Transaction, SiteSetting
from core.services.verification import (
    VerificationService,
    EngagementToVerify,
    VerificationResult,
)
from core.services.settlement import SettlementService
from core.services.posts import get_feed_posts, get_feed_count
from posts.models import Post, Engagement


class VerificationServiceTest(TestCase):
    """Test VerificationService - pure API calls, no DB writes."""

    def setUp(self):
        self.service = VerificationService()
        self.user = User.objects.create(
            telegram_id=123456789,
            display_name="Test User",
            x_username="testuser",
            credits=Decimal('100'),
        )
        self.post = Post.objects.create(
            user=self.user,
            x_link="https://x.com/testuser/status/123456789",
            tweet_id="123456789",
            escrow=Decimal('10'),
            initial_escrow=Decimal('10'),
            platform="web",
        )

    @patch('core.services.verification.twitter_verification')
    def test_verify_single_passed(self, mock_twitter):
        """Test single verification that passes."""
        mock_twitter.verify_reply.return_value = {
            'passed': True,
            'reply_verified': True,
            'skipped': False,
        }

        engagement = EngagementToVerify(
            engagement_id=uuid.uuid4(),
            post_id=self.post.pk,
            tweet_id="123456789",
        )

        result = self.service.verify_single(engagement, "testuser")

        self.assertTrue(result.passed)
        self.assertTrue(result.reply_verified)
        self.assertFalse(result.skipped)
        mock_twitter.verify_reply.assert_called_once_with(
            tweet_id="123456789",
            x_username="testuser",
        )

    @patch('core.services.verification.twitter_verification')
    def test_verify_single_failed(self, mock_twitter):
        """Test single verification that fails."""
        mock_twitter.verify_reply.return_value = {
            'passed': False,
            'reply_verified': False,
            'error': 'Reply not found',
        }

        engagement = EngagementToVerify(
            engagement_id=uuid.uuid4(),
            post_id=self.post.pk,
            tweet_id="123456789",
        )

        result = self.service.verify_single(engagement, "testuser")

        self.assertFalse(result.passed)
        self.assertEqual(result.error, 'Reply not found')

    @patch('core.services.verification.twitter_verification')
    def test_verify_single_api_skipped(self, mock_twitter):
        """Test verification when API is skipped (no key)."""
        mock_twitter.verify_reply.return_value = {
            'passed': True,
            'skipped': True,
            'error': 'No API key configured',
        }

        engagement = EngagementToVerify(
            engagement_id=uuid.uuid4(),
            post_id=self.post.pk,
            tweet_id="123456789",
        )

        result = self.service.verify_single(engagement, "testuser")

        # Skipped = benefit of doubt = passed
        self.assertTrue(result.passed)
        self.assertTrue(result.skipped)

    def test_verify_single_no_tweet_id(self):
        """Test verification with no tweet_id."""
        engagement = EngagementToVerify(
            engagement_id=uuid.uuid4(),
            post_id=self.post.pk,
            tweet_id="",  # Empty
        )

        result = self.service.verify_single(engagement, "testuser")

        # No tweet_id = benefit of doubt
        self.assertTrue(result.passed)
        self.assertTrue(result.skipped)

    def test_verify_single_no_username(self):
        """Test verification with no x_username."""
        engagement = EngagementToVerify(
            engagement_id=uuid.uuid4(),
            post_id=self.post.pk,
            tweet_id="123456789",
        )

        result = self.service.verify_single(engagement, "")  # Empty username

        # No username = fail
        self.assertFalse(result.passed)

    @patch('core.services.verification.twitter_verification')
    def test_verify_batch(self, mock_twitter):
        """Test batch verification."""
        mock_twitter.verify_reply.side_effect = [
            {'passed': True, 'reply_verified': True, 'skipped': False},
            {'passed': False, 'reply_verified': False, 'error': 'Not found'},
            {'passed': True, 'reply_verified': True, 'skipped': False},
        ]

        engagements = [
            EngagementToVerify(uuid.uuid4(), self.post.pk, "111"),
            EngagementToVerify(uuid.uuid4(), self.post.pk, "222"),
            EngagementToVerify(uuid.uuid4(), self.post.pk, "333"),
        ]

        result = self.service.verify_engagements(engagements, "testuser")

        self.assertEqual(result.total_verified, 3)
        self.assertEqual(result.total_passed, 2)
        self.assertEqual(result.total_failed, 1)


class SettlementServiceTest(TransactionTestCase):
    """Test SettlementService - atomic escrow+credit transfers."""

    def setUp(self):
        # Create settings
        SiteSetting.objects.get_or_create(
            key='CREDIT_PER_ENGAGEMENT',
            defaults={'value': '1', 'data_type': 'int'}
        )
        SiteSetting.objects.get_or_create(
            key='DAILY_EARN_CAP',
            defaults={'value': '999999', 'data_type': 'int'}
        )

        self.creator = User.objects.create(
            telegram_id=111111111,
            display_name="Creator",
            x_username="creator",
            credits=Decimal('100'),
        )
        self.engager = User.objects.create(
            telegram_id=222222222,
            display_name="Engager",
            x_username="engager",
            credits=Decimal('0'),
            tweetscout_score=0,  # Anon tier = 1.0x
        )
        self.post = Post.objects.create(
            user=self.creator,
            x_link="https://x.com/creator/status/123456789",
            tweet_id="123456789",
            escrow=Decimal('10'),
            initial_escrow=Decimal('10'),
            platform="web",
        )
        self.engagement = Engagement.objects.create(
            user=self.engager,
            post=self.post,
            verified=False,
            credit_granted=False,
        )
        self.service = SettlementService()

    def test_settle_passed_verification(self):
        """Test settlement of passed verification."""
        verification_result = VerificationResult(
            engagement_id=self.engagement.pk,
            post_id=self.post.pk,
            passed=True,
            reply_verified=True,
        )

        initial_escrow = self.post.escrow
        initial_credits = self.engager.credits

        result = self.service.settle_engagements(
            user_id=self.engager.pk,
            verification_results=[verification_result],
        )

        self.assertEqual(result.total_passed, 1)
        self.assertEqual(result.total_failed, 0)
        self.assertGreater(result.total_awarded, Decimal('0'))

        # Refresh from DB
        self.post.refresh_from_db()
        self.engagement.refresh_from_db()
        self.engager.refresh_from_db()

        # Escrow should be reduced
        self.assertLess(self.post.escrow, initial_escrow)
        # User should have credits
        self.assertGreater(self.engager.credits, initial_credits)
        # Engagement should be marked
        self.assertTrue(self.engagement.verified)
        self.assertTrue(self.engagement.credit_granted)

    def test_settle_failed_verification(self):
        """Test settlement of failed verification - engagement deleted."""
        verification_result = VerificationResult(
            engagement_id=self.engagement.pk,
            post_id=self.post.pk,
            passed=False,
            error="Reply not found",
        )

        result = self.service.settle_engagements(
            user_id=self.engager.pk,
            verification_results=[verification_result],
        )

        self.assertEqual(result.total_passed, 0)
        self.assertEqual(result.total_failed, 1)

        # Engagement should be deleted
        self.assertFalse(
            Engagement.objects.filter(pk=self.engagement.pk).exists()
        )

    def test_partial_payment_when_escrow_low(self):
        """Test partial payment when escrow < full karma amount."""
        # Set up high tier user (1.2x multiplier)
        self.engager.tweetscout_score = 1000  # GOAT tier
        self.engager.save()

        # Set low escrow
        self.post.escrow = Decimal('0.5')  # Less than 1.0 * 1.2 = 1.2
        self.post.save()

        verification_result = VerificationResult(
            engagement_id=self.engagement.pk,
            post_id=self.post.pk,
            passed=True,
        )

        result = self.service.settle_engagements(
            user_id=self.engager.pk,
            verification_results=[verification_result],
        )

        # Should get partial payment (whatever was left)
        self.assertEqual(result.total_passed, 1)
        self.assertEqual(result.total_awarded, Decimal('0.5'))

        # Escrow should be 0
        self.post.refresh_from_db()
        self.assertEqual(self.post.escrow, Decimal('0'))

    def test_no_karma_leak_on_empty_escrow(self):
        """Test that karma is NOT awarded when escrow is empty."""
        self.post.escrow = Decimal('0')
        self.post.save()

        verification_result = VerificationResult(
            engagement_id=self.engagement.pk,
            post_id=self.post.pk,
            passed=True,
        )

        initial_credits = self.engager.credits

        result = self.service.settle_engagements(
            user_id=self.engager.pk,
            verification_results=[verification_result],
        )

        # No karma awarded
        self.assertEqual(result.total_awarded, Decimal('0'))

        # User credits unchanged
        self.engager.refresh_from_db()
        self.assertEqual(self.engager.credits, initial_credits)

    def test_atomic_rollback_on_credit_service_error(self):
        """Test that escrow is NOT deducted if credit award fails."""
        initial_escrow = self.post.escrow

        verification_result = VerificationResult(
            engagement_id=self.engagement.pk,
            post_id=self.post.pk,
            passed=True,
        )

        # Mock credit service to raise an error
        with patch('core.services.settlement.CreditService') as mock_cs:
            mock_instance = MagicMock()
            mock_instance.can_earn.return_value = True
            mock_instance.earn.side_effect = Exception("Credit service error")
            mock_cs.return_value = mock_instance

            result = self.service.settle_engagements(
                user_id=self.engager.pk,
                verification_results=[verification_result],
            )

        # Should have error status
        self.assertEqual(result.results[0].status, 'error')

        # Escrow should be unchanged (rolled back)
        self.post.refresh_from_db()
        self.assertEqual(self.post.escrow, initial_escrow)


class FeedMultiplierFilterTest(TestCase):
    """Test feed filtering by user's tier multiplier."""

    def setUp(self):
        SiteSetting.objects.get_or_create(
            key='CREDIT_PER_ENGAGEMENT',
            defaults={'value': '1', 'data_type': 'int'}
        )

        self.creator = User.objects.create(
            telegram_id=111111111,
            display_name="Creator",
            credits=Decimal('100'),
        )
        # Create GOAT tier user (1.2x multiplier)
        self.goat_user = User.objects.create(
            telegram_id=222222222,
            display_name="GOAT User",
            tweetscout_score=1000,  # GOAT tier
            credits=Decimal('0'),
        )
        # Create Anon tier user (1.0x multiplier)
        self.anon_user = User.objects.create(
            telegram_id=333333333,
            display_name="Anon User",
            tweetscout_score=0,  # Anon tier
            credits=Decimal('0'),
        )

    def test_goat_user_doesnt_see_low_escrow_posts(self):
        """GOAT user (1.2x) should not see posts with escrow < 1.2."""
        # Create post with 1.0 escrow (less than GOAT's 1.2 karma)
        post = Post.objects.create(
            user=self.creator,
            x_link="https://x.com/creator/status/1",
            escrow=Decimal('1.0'),
            initial_escrow=Decimal('10'),
            platform="web",
        )

        # GOAT user needs 1.2 karma, post only has 1.0
        posts = get_feed_posts(self.goat_user, limit=10, filter_by_multiplier=True)

        # Should NOT see the post
        self.assertEqual(len(posts), 0)

    def test_anon_user_sees_low_escrow_posts(self):
        """Anon user (1.0x) should see posts with escrow >= 1.0."""
        post = Post.objects.create(
            user=self.creator,
            x_link="https://x.com/creator/status/2",
            escrow=Decimal('1.0'),
            initial_escrow=Decimal('10'),
            platform="web",
        )

        # Anon user needs 1.0 karma, post has 1.0
        posts = get_feed_posts(self.anon_user, limit=10, filter_by_multiplier=True)

        # Should see the post
        self.assertEqual(len(posts), 1)

    def test_goat_user_sees_high_escrow_posts(self):
        """GOAT user should see posts with sufficient escrow."""
        post = Post.objects.create(
            user=self.creator,
            x_link="https://x.com/creator/status/3",
            escrow=Decimal('10'),  # Plenty of escrow
            initial_escrow=Decimal('10'),
            platform="web",
        )

        posts = get_feed_posts(self.goat_user, limit=10, filter_by_multiplier=True)

        # Should see the post
        self.assertEqual(len(posts), 1)

    def test_feed_count_respects_multiplier(self):
        """get_feed_count should also respect multiplier filter."""
        # Post with low escrow
        Post.objects.create(
            user=self.creator,
            x_link="https://x.com/creator/status/4",
            escrow=Decimal('1.0'),
            initial_escrow=Decimal('10'),
            platform="web",
        )

        # GOAT user (1.2x) shouldn't count it
        goat_count = get_feed_count(self.goat_user, filter_by_multiplier=True)
        self.assertEqual(goat_count, 0)

        # Anon user (1.0x) should count it
        anon_count = get_feed_count(self.anon_user, filter_by_multiplier=True)
        self.assertEqual(anon_count, 1)


class PostExpiryTest(TransactionTestCase):
    """Test post expiry with refund."""

    def setUp(self):
        SiteSetting.objects.get_or_create(
            key='POST_EXPIRY_HOURS',
            defaults={'value': '48', 'data_type': 'int'}
        )

        self.creator = User.objects.create(
            telegram_id=111111111,
            display_name="Creator",
            credits=Decimal('50'),  # After posting
        )
        self.post = Post.objects.create(
            user=self.creator,
            x_link="https://x.com/creator/status/123456789",
            escrow=Decimal('10'),
            initial_escrow=Decimal('40'),  # 30 already earned
            platform="web",
        )

    def test_expire_single_post_refunds_escrow(self):
        """Test that expiring a post refunds remaining escrow."""
        from posts.tasks import _expire_single_post

        initial_credits = self.creator.credits
        escrow_amount = self.post.escrow

        _expire_single_post(self.post.pk)

        # Post should be cancelled
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.CANCELLED)

        # Creator should have escrow refunded
        self.creator.refresh_from_db()
        self.assertEqual(
            self.creator.credits,
            initial_credits + escrow_amount
        )

        # Transaction should be recorded
        refund_tx = Transaction.objects.filter(
            user=self.creator,
            type=Transaction.Type.REFUND,
            reference_id=self.post.pk,
        ).first()
        self.assertIsNotNone(refund_tx)
        self.assertEqual(refund_tx.amount, escrow_amount)

    def test_expire_old_posts_task(self):
        """Test the periodic task finds and expires old posts."""
        from posts.tasks import expire_old_posts

        # Make post old
        old_time = timezone.now() - timedelta(hours=49)  # > 48 hours
        Post.objects.filter(pk=self.post.pk).update(created_at=old_time)

        result = expire_old_posts()

        self.assertEqual(result['expired'], 1)
        self.assertEqual(result['failed'], 0)

        # Post should be cancelled
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.CANCELLED)

    def test_expire_skips_recent_posts(self):
        """Test that recent posts are not expired."""
        from posts.tasks import expire_old_posts

        # Post is recent (default created_at is now)
        result = expire_old_posts()

        self.assertEqual(result['expired'], 0)

        # Post should still be active
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.ACTIVE)


class IntegrationTest(TransactionTestCase):
    """End-to-end integration tests."""

    def setUp(self):
        SiteSetting.objects.get_or_create(
            key='CREDIT_PER_ENGAGEMENT',
            defaults={'value': '1', 'data_type': 'int'}
        )
        SiteSetting.objects.get_or_create(
            key='DAILY_EARN_CAP',
            defaults={'value': '999999', 'data_type': 'int'}
        )
        SiteSetting.objects.get_or_create(
            key='POST_EXPIRY_HOURS',
            defaults={'value': '48', 'data_type': 'int'}
        )

        self.creator = User.objects.create(
            telegram_id=111111111,
            display_name="Creator",
            x_username="creator",
            credits=Decimal('100'),
        )
        self.engager = User.objects.create(
            telegram_id=222222222,
            display_name="Engager",
            x_username="engager",
            credits=Decimal('0'),
            tweetscout_score=500,  # Based tier = 1.1x
        )

    @patch('core.services.verification.twitter_verification')
    def test_full_verification_flow(self, mock_twitter):
        """Test complete flow: engage → verify → settle."""
        mock_twitter.verify_reply.return_value = {
            'passed': True,
            'reply_verified': True,
            'skipped': False,
        }

        # Create post
        post = Post.objects.create(
            user=self.creator,
            x_link="https://x.com/creator/status/123",
            tweet_id="123",
            escrow=Decimal('10'),
            initial_escrow=Decimal('10'),
            platform="web",
        )

        # Create engagement
        engagement = Engagement.objects.create(
            user=self.engager,
            post=post,
            verified=False,
            credit_granted=False,
        )

        # Phase 1: Verify
        verification_service = VerificationService()
        verification_results = verification_service.verify_engagements(
            engagements=[EngagementToVerify(
                engagement_id=engagement.pk,
                post_id=post.pk,
                tweet_id="123",
            )],
            x_username=self.engager.x_username,
        )

        self.assertEqual(verification_results.total_passed, 1)

        # Phase 2: Settle
        settlement_service = SettlementService()
        settlement_results = settlement_service.settle_engagements(
            user_id=self.engager.pk,
            verification_results=verification_results.results,
        )

        self.assertEqual(settlement_results.total_passed, 1)
        self.assertGreater(settlement_results.total_awarded, Decimal('0'))

        # Verify final state
        post.refresh_from_db()
        engagement.refresh_from_db()
        self.engager.refresh_from_db()

        self.assertLess(post.escrow, Decimal('10'))
        self.assertTrue(engagement.verified)
        self.assertTrue(engagement.credit_granted)
        self.assertGreater(self.engager.credits, Decimal('0'))

        # Transaction should exist
        tx = Transaction.objects.filter(
            user=self.engager,
            type=Transaction.Type.EARNED,
        ).first()
        self.assertIsNotNone(tx)
