"""
End-to-end integration test wrapper.

This module provides Django TestCase wrappers for the integration tests.
For the full integration test with real API calls, use:

    python manage.py run_integration_test

For individual unit test assertions:

    python manage.py test core.tests.test_integration_e2e -v 2
"""
from decimal import Decimal
from django.test import TestCase

from core.models import User
from core.services.tweet_score import (
    get_tweet_score_tier,
    get_tweet_score_multiplier,
    calculate_engagement_karma,
)
from core.services.credits import CreditService, InsufficientCreditsError
from core.services.twitter_verification import twitter_verification
from posts.models import Post, Engagement


class TierMultiplierTests(TestCase):
    """Test tier calculation and multiplier logic."""

    def test_tier_thresholds(self):
        """Test that tier names are assigned correctly based on score."""
        test_cases = [
            (0, "Anon"),
            (50, "Anon"),
            (99, "Anon"),
            (100, "Normie"),
            (150, "Normie"),
            (200, "Degen"),
            (350, "Degen"),
            (400, "Based"),
            (500, "Based"),
            (600, "Legend"),
            (700, "Legend"),
            (800, "OG"),
            (900, "OG"),
            (1000, "GOAT"),
            (1500, "GOAT"),
        ]

        for score, expected_tier in test_cases:
            tier = get_tweet_score_tier(score)
            self.assertEqual(
                tier, expected_tier,
                f"Score {score} should be {expected_tier}, got {tier}"
            )

    def test_multiplier_values(self):
        """Test that multipliers are in correct range."""
        for score in range(0, 1500, 100):
            multiplier = get_tweet_score_multiplier(score)
            self.assertGreaterEqual(multiplier, Decimal('1.0'))
            self.assertLessEqual(multiplier, Decimal('1.2'))

    def test_karma_calculation(self):
        """Test karma calculation with multipliers."""
        base = Decimal('1')

        # Anon tier (1.0x)
        karma, mult = calculate_engagement_karma(base, 50)
        self.assertEqual(karma, Decimal('1.0000'))

        # GOAT tier (1.2x)
        karma, mult = calculate_engagement_karma(base, 1000)
        self.assertEqual(karma, Decimal('1.2000'))

    def test_karma_decimal_precision(self):
        """Test that karma maintains 4 decimal precision."""
        base = Decimal('1.5')  # Non-standard base for testing

        karma, mult = calculate_engagement_karma(base, 500)  # Based tier
        # Should be 1.5 * 1.10 = 1.6500
        self.assertEqual(karma.as_tuple().exponent, -4)  # 4 decimal places


class TweetIdExtractionTests(TestCase):
    """Test tweet ID extraction from URLs."""

    def test_standard_x_url(self):
        """Test extraction from standard x.com URLs."""
        url = "https://x.com/username/status/1234567890123456789"
        tweet_id = twitter_verification.extract_tweet_id(url)
        self.assertEqual(tweet_id, "1234567890123456789")

    def test_twitter_url(self):
        """Test extraction from twitter.com URLs."""
        url = "https://twitter.com/username/status/1234567890123456789"
        tweet_id = twitter_verification.extract_tweet_id(url)
        self.assertEqual(tweet_id, "1234567890123456789")

    def test_url_with_query_params(self):
        """Test extraction from URLs with query params."""
        url = "https://x.com/username/status/1234567890123456789?s=20"
        tweet_id = twitter_verification.extract_tweet_id(url)
        self.assertEqual(tweet_id, "1234567890123456789")

    def test_invalid_url(self):
        """Test that invalid URLs return None."""
        url = "https://example.com/not-a-tweet"
        tweet_id = twitter_verification.extract_tweet_id(url)
        self.assertIsNone(tweet_id)


class CreditServiceTests(TestCase):
    """Test credit operations."""

    def setUp(self):
        self.user = User.objects.create(
            telegram_id=9999999,
            display_name="Test User",
            credits=Decimal('100'),
        )
        self.credit_service = CreditService(self.user)

    def test_earn_credits(self):
        """Test earning credits."""
        initial = self.user.credits
        self.credit_service.earn(Decimal('10'), description="Test earn")
        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, initial + Decimal('10'))

    def test_spend_credits(self):
        """Test spending credits."""
        initial = self.user.credits
        self.credit_service.spend(Decimal('25'), description="Test spend")
        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, initial - Decimal('25'))

    def test_insufficient_credits(self):
        """Test that spending more than balance raises error."""
        with self.assertRaises(InsufficientCreditsError):
            self.credit_service.spend(Decimal('9999'))

    def test_decimal_precision(self):
        """Test that decimal operations maintain precision."""
        self.credit_service.earn(Decimal('1.2345'), description="Precision test")
        self.user.refresh_from_db()
        # Balance should have 4 decimal places
        self.assertEqual(self.user.credits.as_tuple().exponent, -4)


class EngagementFlowTests(TestCase):
    """Test engagement creation and constraints."""

    def setUp(self):
        self.poster = User.objects.create(
            telegram_id=8888888,
            display_name="Poster",
            x_username="poster",
            credits=Decimal('100'),
        )
        self.engager = User.objects.create(
            telegram_id=7777777,
            display_name="Engager",
            x_username="engager",
            credits=Decimal('50'),
        )
        self.post = Post.objects.create(
            user=self.poster,
            x_link="https://x.com/poster/status/123456789",
            platform=Post.Platform.WEB,
            escrow=Decimal('20'),
            initial_escrow=Decimal('20'),
        )

    def test_create_engagement(self):
        """Test creating an engagement."""
        engagement = Engagement.objects.create(
            user=self.engager,
            post=self.post,
            verified=False,
            credit_granted=False,
        )
        self.assertIsNotNone(engagement.id)
        self.assertFalse(engagement.verified)

    def test_duplicate_engagement_prevented(self):
        """Test that duplicate engagements are prevented."""
        Engagement.objects.create(
            user=self.engager,
            post=self.post,
            verified=False,
            credit_granted=False,
        )

        # Second engagement should fail due to unique constraint
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Engagement.objects.create(
                user=self.engager,
                post=self.post,
                verified=False,
                credit_granted=False,
            )

    def test_self_engagement_model_allows(self):
        """Test that model doesn't prevent self-engagement (business logic does)."""
        # The actual blocking happens in the view/service layer
        # Here we just verify the model allows it (constraint is in business logic)
        self_engagement = Engagement.objects.create(
            user=self.poster,  # Same as post owner
            post=self.post,
            verified=False,
            credit_granted=False,
        )
        self.assertIsNotNone(self_engagement.id)
        # Note: Business logic should prevent this in views


class PostModelTests(TestCase):
    """Test post model constraints and properties."""

    def setUp(self):
        self.user = User.objects.create(
            telegram_id=6666666,
            display_name="Post Creator",
            credits=Decimal('100'),
        )

    def test_post_creation(self):
        """Test post creation with escrow."""
        post = Post.objects.create(
            user=self.user,
            x_link="https://x.com/test/status/123",
            platform=Post.Platform.WEB,
            escrow=Decimal('30'),
            initial_escrow=Decimal('30'),
        )
        self.assertEqual(post.status, Post.Status.ACTIVE)
        self.assertEqual(post.escrow, Decimal('30'))

    def test_escrow_non_negative_constraint(self):
        """Test that negative escrow is prevented by check constraint."""
        from django.db.models import F
        from django.db import IntegrityError

        post = Post.objects.create(
            user=self.user,
            x_link="https://x.com/test/status/456",
            platform=Post.Platform.WEB,
            escrow=Decimal('10'),
            initial_escrow=Decimal('10'),
        )

        # Try to decrement escrow below zero using F() expression
        # The check constraint should prevent this
        with self.assertRaises(IntegrityError):
            # Decrement by more than available (10 - 20 = -10)
            Post.objects.filter(pk=post.pk).update(escrow=F('escrow') - Decimal('20'))

    def test_engagement_progress(self):
        """Test engagement progress calculation."""
        post = Post.objects.create(
            user=self.user,
            x_link="https://x.com/test/status/789",
            platform=Post.Platform.WEB,
            escrow=Decimal('20'),
            initial_escrow=Decimal('40'),
        )
        # 20 of 40 used = 50%
        self.assertEqual(post.engagement_progress, 50)
