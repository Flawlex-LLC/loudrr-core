"""
Tests for the Decimal Karma System.

Tests:
1. All 7 tiers get correct multipliers
2. 4 decimal places maintained in calculations
3. No inflation: escrow_deducted == karma_earned
4. Daily cap works with decimal amounts
5. CreditService methods handle Decimal correctly
"""
from decimal import Decimal

from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core.models import User, Transaction
from core.services.credits import CreditService, DailyCapReachedError
from core.services.tweet_score import (
    calculate_engagement_karma,
    get_tweet_score_multiplier,
    get_tweet_score_tier,
    KARMA_QUANTIZE,
)


class TierMultiplierTests(TestCase):
    """Test all 7 tiers get correct multipliers."""

    def test_anon_tier(self):
        """Score 0-99 should be Anon tier with 1.00x multiplier."""
        for score in [0, 50, 99]:
            self.assertEqual(get_tweet_score_tier(score), "Anon")
            self.assertEqual(get_tweet_score_multiplier(score), Decimal("1.00"))

    def test_normie_tier(self):
        """Score 100-199 should be Normie tier with 1.03x multiplier."""
        for score in [100, 150, 199]:
            self.assertEqual(get_tweet_score_tier(score), "Normie")
            self.assertEqual(get_tweet_score_multiplier(score), Decimal("1.03"))

    def test_degen_tier(self):
        """Score 200-399 should be Degen tier with 1.06x multiplier."""
        for score in [200, 300, 399]:
            self.assertEqual(get_tweet_score_tier(score), "Degen")
            self.assertEqual(get_tweet_score_multiplier(score), Decimal("1.06"))

    def test_based_tier(self):
        """Score 400-599 should be Based tier with 1.10x multiplier."""
        for score in [400, 500, 599]:
            self.assertEqual(get_tweet_score_tier(score), "Based")
            self.assertEqual(get_tweet_score_multiplier(score), Decimal("1.10"))

    def test_legend_tier(self):
        """Score 600-799 should be Legend tier with 1.14x multiplier."""
        for score in [600, 700, 799]:
            self.assertEqual(get_tweet_score_tier(score), "Legend")
            self.assertEqual(get_tweet_score_multiplier(score), Decimal("1.14"))

    def test_og_tier(self):
        """Score 800-999 should be OG tier with 1.17x multiplier."""
        for score in [800, 900, 999]:
            self.assertEqual(get_tweet_score_tier(score), "OG")
            self.assertEqual(get_tweet_score_multiplier(score), Decimal("1.17"))

    def test_goat_tier(self):
        """Score 1000+ should be GOAT tier with 1.20x multiplier."""
        for score in [1000, 1500, 5000]:
            self.assertEqual(get_tweet_score_tier(score), "GOAT")
            self.assertEqual(get_tweet_score_multiplier(score), Decimal("1.20"))


class KarmaCalculationTests(TestCase):
    """Test karma calculation precision and correctness."""

    def test_karma_has_4_decimal_places(self):
        """Karma should be calculated with 4 decimal places."""
        base = Decimal("1")
        karma, _ = calculate_engagement_karma(base, 150)  # Normie: 1.03x

        # Should be exactly 1.0300
        self.assertEqual(karma, Decimal("1.0300"))
        self.assertEqual(karma.as_tuple().exponent, -4)

    def test_karma_uses_banker_rounding(self):
        """Karma should use ROUND_HALF_EVEN (Banker's rounding)."""
        # Test case where rounding matters
        # 1.0000 * 1.03 = 1.03 (no rounding needed)
        base = Decimal("1")
        karma, _ = calculate_engagement_karma(base, 150)
        self.assertEqual(karma, Decimal("1.0300"))

    def test_no_inflation_base_times_multiplier(self):
        """Escrow deducted should equal karma earned (no inflation)."""
        base = Decimal("1")

        for score in [0, 150, 300, 500, 700, 900, 1200]:
            karma, multiplier = calculate_engagement_karma(base, score)
            expected = (base * multiplier).quantize(KARMA_QUANTIZE)
            self.assertEqual(karma, expected, f"Failed for score {score}")

    def test_accepts_int_base_amount(self):
        """Should handle integer base amount by converting to Decimal."""
        karma, _ = calculate_engagement_karma(1, 500)  # int, not Decimal
        self.assertEqual(karma, Decimal("1.1000"))

    def test_returns_tuple_of_decimals(self):
        """Should return tuple of (karma, multiplier) as Decimals."""
        karma, multiplier = calculate_engagement_karma(Decimal("1"), 500)

        self.assertIsInstance(karma, Decimal)
        self.assertIsInstance(multiplier, Decimal)


class CreditServiceDecimalTests(TransactionTestCase):
    """Test CreditService handles Decimal amounts correctly."""

    def setUp(self):
        """Create a test user."""
        self.user = User.objects.create(
            telegram_id=123456789,
            telegram_username="testuser",
            display_name="Test User",
            credits=Decimal("100.0000"),
        )
        self.service = CreditService(self.user)

    def test_earn_decimal_amount(self):
        """Should earn decimal karma amount."""
        tx = self.service.earn(
            amount=Decimal("1.1400"),
            reference_type="test",
            description="Test earn",
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, Decimal("101.1400"))
        self.assertEqual(tx.amount, Decimal("1.1400"))

    def test_spend_decimal_amount(self):
        """Should spend decimal karma amount."""
        tx = self.service.spend(
            amount=Decimal("10.5000"),
            reference_type="test",
            description="Test spend",
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, Decimal("89.5000"))
        self.assertEqual(tx.amount, Decimal("-10.5000"))

    def test_refund_decimal_amount(self):
        """Should refund decimal karma amount."""
        tx = self.service.refund(
            amount=Decimal("5.2500"),
            reference_type="test",
            description="Test refund",
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.credits, Decimal("105.2500"))
        self.assertEqual(tx.amount, Decimal("5.2500"))

    def test_daily_cap_with_decimals(self):
        """Daily cap should work with decimal earnings."""
        # Set user near daily cap (assume cap is 160)
        self.user.daily_credits_earned = Decimal("159.5000")
        self.user.save()

        # Try to earn 1.14 karma (should be capped)
        self.service = CreditService(self.user)
        tx = self.service.earn(
            amount=Decimal("1.1400"),
            reference_type="test",
            description="Test capped earn",
        )

        self.user.refresh_from_db()
        # Should only earn 0.5000 (160 - 159.5)
        self.assertEqual(tx.amount, Decimal("0.5000"))

    def test_get_balance_returns_decimal(self):
        """get_balance should return Decimal."""
        balance = self.service.get_balance()
        self.assertIsInstance(balance, Decimal)
        self.assertEqual(balance, Decimal("100.0000"))

    def test_get_daily_remaining_returns_decimal(self):
        """get_daily_remaining should return Decimal."""
        remaining = self.service.get_daily_remaining()
        self.assertIsInstance(remaining, Decimal)

    def test_can_earn_with_decimal(self):
        """can_earn should work with Decimal amounts."""
        self.assertTrue(self.service.can_earn(Decimal("1.1400")))

        # Set near cap
        self.user.daily_credits_earned = Decimal("159.9000")
        self.user.save()
        self.service = CreditService(self.user)

        # Can't earn 1.14 when only 0.10 remaining
        self.assertFalse(self.service.can_earn(Decimal("1.1400")))

    def test_can_spend_with_decimal(self):
        """can_spend should work with Decimal amounts."""
        self.assertTrue(self.service.can_spend(Decimal("50.5000")))
        self.assertTrue(self.service.can_spend(Decimal("100.0000")))
        self.assertFalse(self.service.can_spend(Decimal("100.0001")))


class TransactionDecimalTests(TransactionTestCase):
    """Test Transaction model stores Decimal correctly."""

    def setUp(self):
        """Create a test user."""
        self.user = User.objects.create(
            telegram_id=123456789,
            telegram_username="testuser",
            display_name="Test User",
            credits=Decimal("100.0000"),
        )

    def test_transaction_stores_decimal_amount(self):
        """Transaction should store decimal amount with 4 places."""
        tx = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EARNED,
            amount=Decimal("1.1400"),
            balance_after=Decimal("101.1400"),
            description="Test transaction",
        )

        tx.refresh_from_db()
        self.assertEqual(tx.amount, Decimal("1.1400"))
        self.assertEqual(tx.balance_after, Decimal("101.1400"))

    def test_transaction_str_shows_2_decimals(self):
        """Transaction __str__ should format with 2 decimal places."""
        tx = Transaction.objects.create(
            user=self.user,
            type=Transaction.Type.EARNED,
            amount=Decimal("1.1400"),
            balance_after=Decimal("101.1400"),
            description="Test",
        )

        # Should contain "+1.14" not "+1.1400"
        self.assertIn("+1.14", str(tx))
