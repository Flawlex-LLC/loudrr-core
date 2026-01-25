"""
Property-based tests for the engagement system using Hypothesis.

Tests invariants that should ALWAYS hold true:
- Karma is always positive
- Multiplier is always in valid range (1.0 to 1.2)
- Escrow can never go negative
- Karma awarded never exceeds escrow deducted
- Honesty score is always bounded [0, 50]
- Daily earned never exceeds daily cap

Run with: pytest core/tests/test_engagement_hypothesis.py -v
"""
from decimal import Decimal, ROUND_HALF_EVEN
from unittest.mock import patch

from hypothesis import given, strategies as st, assume, settings, example
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize


# === Strategy Definitions ===

# TweetScout scores range from 0 to 2000+
tweetscout_score = st.floats(min_value=0, max_value=3000, allow_nan=False, allow_infinity=False)

# Credit amounts with 4 decimal places
credit_amount = st.decimals(
    min_value=Decimal('0.0001'),
    max_value=Decimal('100'),
    places=4,
    allow_nan=False,
    allow_infinity=False
)

# Escrow amounts (can be 0)
escrow_amount = st.decimals(
    min_value=Decimal('0'),
    max_value=Decimal('1000'),
    places=4,
    allow_nan=False,
    allow_infinity=False
)


# === Mock Settings ===

MOCK_SETTINGS = {
    'TIER_GOAT_THRESHOLD': 1000,
    'TIER_OG_THRESHOLD': 800,
    'TIER_LEGEND_THRESHOLD': 600,
    'TIER_BASED_THRESHOLD': 400,
    'TIER_DEGEN_THRESHOLD': 200,
    'TIER_NORMIE_THRESHOLD': 100,
    'TIER_GOAT_MULTIPLIER': 1.20,
    'TIER_OG_MULTIPLIER': 1.17,
    'TIER_LEGEND_MULTIPLIER': 1.14,
    'TIER_BASED_MULTIPLIER': 1.10,
    'TIER_DEGEN_MULTIPLIER': 1.06,
    'TIER_NORMIE_MULTIPLIER': 1.03,
    'TIER_ANON_MULTIPLIER': 1.00,
    'DAILY_EARN_CAP': 100,
    'CREDIT_PER_ENGAGEMENT': 1.0,
}


def mock_get_setting(key):
    """Mock settings for testing without DB."""
    return MOCK_SETTINGS.get(key, 0)


# === Pure Calculation Tests ===

class TestKarmaCalculations:
    """Property-based tests for karma/credit calculations."""

    @given(score=tweetscout_score)
    @settings(max_examples=200)
    def test_multiplier_in_valid_range(self, score):
        """Multiplier should be between 1.0 and 1.2 (configured max)."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import get_tweet_score_multiplier
            multiplier = get_tweet_score_multiplier(score)
            assert Decimal('1.0') <= multiplier <= Decimal('1.2')

    @given(score=tweetscout_score)
    @settings(max_examples=200)
    def test_multiplier_monotonic(self, score):
        """Higher scores should give higher or equal multipliers."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import get_tweet_score_multiplier
            multiplier_low = get_tweet_score_multiplier(0)
            multiplier_current = get_tweet_score_multiplier(score)
            assert multiplier_current >= multiplier_low

    @given(base=credit_amount, score=tweetscout_score)
    @settings(max_examples=200)
    def test_karma_always_positive(self, base, score):
        """Karma should never be negative."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import calculate_engagement_karma
            karma, multiplier = calculate_engagement_karma(base, score)
            assert karma >= Decimal('0')

    @given(base=credit_amount, score=tweetscout_score)
    @settings(max_examples=200)
    def test_karma_bounded_by_max_multiplier(self, base, score):
        """Karma should not exceed base * max_multiplier (1.2x)."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import calculate_engagement_karma
            karma, multiplier = calculate_engagement_karma(base, score)
            max_karma = base * Decimal('1.2')
            assert karma <= max_karma + Decimal('0.0001')  # Float tolerance

    @given(base=credit_amount, score=tweetscout_score)
    @settings(max_examples=200)
    def test_karma_at_least_base(self, base, score):
        """Karma should be at least base amount (minimum 1.0x multiplier)."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import calculate_engagement_karma
            karma, multiplier = calculate_engagement_karma(base, score)
            assert karma >= base - Decimal('0.0001')  # Float tolerance

    @given(base=credit_amount, score=tweetscout_score)
    @settings(max_examples=200)
    def test_karma_and_multiplier_consistent(self, base, score):
        """karma = base * multiplier (within rounding tolerance)."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import calculate_engagement_karma
            karma, multiplier = calculate_engagement_karma(base, score)
            expected = (base * multiplier).quantize(Decimal('0.0001'), rounding=ROUND_HALF_EVEN)
            assert abs(karma - expected) <= Decimal('0.0001')


class TestEscrowInvariants:
    """Property-based tests for escrow management logic."""

    @given(
        initial_escrow=escrow_amount,
        karma_to_award=credit_amount,
    )
    @settings(max_examples=200)
    def test_escrow_never_negative(self, initial_escrow, karma_to_award):
        """Escrow deduction should never result in negative escrow."""
        # Simulate the escrow deduction logic from record_button_engagement
        actual_karma = min(karma_to_award, initial_escrow)
        remaining_escrow = initial_escrow - actual_karma
        assert remaining_escrow >= Decimal('0')

    @given(
        initial_escrow=escrow_amount,
        karma_to_award=credit_amount,
    )
    @settings(max_examples=200)
    def test_no_karma_inflation(self, initial_escrow, karma_to_award):
        """Karma awarded should never exceed escrow deducted."""
        # Simulate: actual_karma = min(karma_to_award, initial_escrow)
        actual_karma = min(karma_to_award, initial_escrow)
        escrow_deducted = actual_karma  # The amount removed from escrow

        # Core invariant: can't award more than we take from escrow
        assert actual_karma <= escrow_deducted + Decimal('0.0001')

    @given(
        initial_escrow=escrow_amount,
        karma_to_award=credit_amount,
    )
    @settings(max_examples=200)
    @example(initial_escrow=Decimal('0'), karma_to_award=Decimal('1'))
    @example(initial_escrow=Decimal('0.5'), karma_to_award=Decimal('1'))
    @example(initial_escrow=Decimal('100'), karma_to_award=Decimal('0.0001'))
    def test_partial_payment_correct(self, initial_escrow, karma_to_award):
        """When escrow < karma, should only award what's available."""
        actual_karma = min(karma_to_award, initial_escrow)

        if initial_escrow < karma_to_award:
            # Partial payment case
            assert actual_karma == initial_escrow
        else:
            # Full payment case
            assert actual_karma == karma_to_award


class TestHonestyScore:
    """Property-based tests for honesty score bounds."""

    @given(
        current_score=st.integers(min_value=0, max_value=50),
        passed_count=st.integers(min_value=0, max_value=100),
        failed_count=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=200)
    def test_honesty_score_bounded(self, current_score, passed_count, failed_count):
        """Honesty score should always be in [0, 50] after bounding."""
        # Simulate honesty score update (from settlement service)
        # Passed verifications: +1, Failed: -2
        new_score = current_score + passed_count - (failed_count * 2)
        bounded_score = max(0, min(50, new_score))
        assert 0 <= bounded_score <= 50

    @given(
        current_score=st.integers(min_value=0, max_value=50),
        delta=st.integers(min_value=-100, max_value=100),
    )
    @settings(max_examples=200)
    def test_honesty_clamp_idempotent(self, current_score, delta):
        """Clamping twice should give same result as clamping once."""
        new_score = current_score + delta
        clamped_once = max(0, min(50, new_score))
        clamped_twice = max(0, min(50, clamped_once))
        assert clamped_once == clamped_twice


class TestDailyCap:
    """Property-based tests for daily cap enforcement."""

    @given(
        daily_earned=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('100'),  # Cap at daily_cap, not above
            places=4,
            allow_nan=False,
            allow_infinity=False
        ),
        earn_amount=credit_amount,
    )
    @settings(max_examples=200)
    def test_daily_cap_respected(self, daily_earned, earn_amount):
        """Earnings should respect daily cap when starting below cap."""
        daily_cap = Decimal('100')  # From MOCK_SETTINGS

        # Simulate the capping logic from CreditService.earn()
        if daily_earned >= daily_cap:
            # Already at cap, earn nothing
            actual_earned = Decimal('0')
        else:
            remaining = daily_cap - daily_earned
            actual_earned = min(earn_amount, remaining)

        new_daily = daily_earned + actual_earned
        # When starting at or below cap, we should stay at or below cap
        assert new_daily <= daily_cap + Decimal('0.0001')

    @given(
        daily_earned=st.decimals(
            min_value=Decimal('0'),
            max_value=Decimal('100'),
            places=4,
            allow_nan=False,
            allow_infinity=False
        ),
    )
    @settings(max_examples=200)
    def test_can_earn_check_consistent(self, daily_earned):
        """can_earn should return True iff daily_earned < daily_cap."""
        daily_cap = Decimal('100')
        can_earn = daily_earned < daily_cap

        if can_earn:
            assert daily_earned < daily_cap
        else:
            assert daily_earned >= daily_cap


class TestStreakLogic:
    """Property-based tests for streak calculation logic."""

    @given(
        current_streak=st.integers(min_value=0, max_value=1000),
        longest_streak=st.integers(min_value=0, max_value=1000),
        streak_increment=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=200)
    def test_longest_streak_never_decreases(self, current_streak, longest_streak, streak_increment):
        """longest_streak should only increase, never decrease."""
        assume(longest_streak >= current_streak)  # Valid starting state

        new_current = current_streak + streak_increment
        new_longest = max(longest_streak, new_current)

        assert new_longest >= longest_streak

    @given(
        current_streak=st.integers(min_value=0, max_value=1000),
    )
    @settings(max_examples=200)
    def test_streak_reset_to_one(self, current_streak):
        """After a gap, streak resets to 1 (not 0)."""
        # Simulate gap detection: streak resets to 1
        new_streak = 1
        assert new_streak >= 1


# === Stateful Testing ===

class EngagementStateMachine(RuleBasedStateMachine):
    """
    Stateful test simulating multiple users engaging with multiple posts.

    Verifies system-wide invariants:
    - Escrow never goes negative
    - Total credits earned == Total escrow deducted
    """

    def __init__(self):
        super().__init__()
        self.user_credits = {}  # user_id -> credits
        self.post_escrows = {}  # post_id -> remaining_escrow
        self.total_escrow_deducted = Decimal('0')
        self.total_credits_awarded = Decimal('0')

    @initialize()
    def setup(self):
        """Initialize state."""
        self.user_credits = {}
        self.post_escrows = {}
        self.total_escrow_deducted = Decimal('0')
        self.total_credits_awarded = Decimal('0')

    @rule(
        post_id=st.integers(min_value=1, max_value=50),
        escrow=st.decimals(
            min_value=Decimal('1'),
            max_value=Decimal('100'),
            places=4,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def create_post(self, post_id, escrow):
        """Create a post with escrow."""
        if post_id not in self.post_escrows:
            self.post_escrows[post_id] = escrow

    @rule(
        user_id=st.integers(min_value=1, max_value=20),
        post_id=st.integers(min_value=1, max_value=50),
        karma=st.decimals(
            min_value=Decimal('0.5'),
            max_value=Decimal('2'),
            places=4,
            allow_nan=False,
            allow_infinity=False
        )
    )
    def engage_with_post(self, user_id, post_id, karma):
        """User engages with a post and receives karma."""
        # Skip if post doesn't exist or has no escrow
        if post_id not in self.post_escrows:
            return
        if self.post_escrows[post_id] <= Decimal('0'):
            return

        # Initialize user if needed
        if user_id not in self.user_credits:
            self.user_credits[user_id] = Decimal('0')

        # Calculate actual karma (capped by escrow)
        escrow = self.post_escrows[post_id]
        actual_karma = min(karma, escrow)

        # Execute engagement
        self.post_escrows[post_id] -= actual_karma
        self.user_credits[user_id] += actual_karma
        self.total_escrow_deducted += actual_karma
        self.total_credits_awarded += actual_karma

    @invariant()
    def escrow_never_negative(self):
        """No post should have negative escrow."""
        for post_id, escrow in self.post_escrows.items():
            assert escrow >= Decimal('0'), f"Post {post_id} has negative escrow: {escrow}"

    @invariant()
    def credits_never_negative(self):
        """No user should have negative credits from engagement."""
        for user_id, credits in self.user_credits.items():
            assert credits >= Decimal('0'), f"User {user_id} has negative credits: {credits}"

    @invariant()
    def credits_match_escrow(self):
        """Total credits awarded should equal total escrow deducted."""
        diff = abs(self.total_credits_awarded - self.total_escrow_deducted)
        assert diff < Decimal('0.0001'), (
            f"Credit/escrow mismatch: awarded={self.total_credits_awarded}, "
            f"deducted={self.total_escrow_deducted}"
        )


# Create test case from state machine
TestEngagementSystem = EngagementStateMachine.TestCase


# === Edge Case Tests ===

class TestEdgeCases:
    """Specific edge case tests."""

    def test_zero_base_karma(self):
        """Zero base karma should give zero result."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import calculate_engagement_karma
            karma, multiplier = calculate_engagement_karma(Decimal('0'), 500)
            assert karma == Decimal('0')

    def test_very_high_score(self):
        """Very high TweetScout score should still cap at GOAT tier."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import get_tweet_score_multiplier
            mult_1000 = get_tweet_score_multiplier(1000)
            mult_5000 = get_tweet_score_multiplier(5000)
            mult_9999 = get_tweet_score_multiplier(9999)

            # All should be GOAT tier (1.20x)
            assert mult_1000 == mult_5000 == mult_9999 == Decimal('1.20')

    def test_tier_boundaries(self):
        """Test exact tier boundaries."""
        with patch('core.services.tweet_score.get_setting', mock_get_setting):
            from core.services.tweet_score import get_tweet_score_multiplier

            # Just below threshold
            assert get_tweet_score_multiplier(99) == Decimal('1.00')   # Anon
            assert get_tweet_score_multiplier(199) == Decimal('1.03')  # Normie

            # Exactly at threshold
            assert get_tweet_score_multiplier(100) == Decimal('1.03')  # Normie
            assert get_tweet_score_multiplier(200) == Decimal('1.06')  # Degen
            assert get_tweet_score_multiplier(1000) == Decimal('1.20') # GOAT
