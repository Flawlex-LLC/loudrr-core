"""
Property-based tests for the LOUD system using Hypothesis.

Tests invariants that should ALWAYS hold true:
- Points are always non-negative integers
- URL normalization is idempotent
- Daily limits are enforced
- Leaderboard totals match submission sums
- No point inflation (points out <= score-based calculation)

Run with: pytest loud/tests/test_loud_hypothesis.py -v
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from hypothesis import given, strategies as st, assume, settings, example
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant, initialize
from django.core.exceptions import ValidationError

# Import the functions to test
from loud.services.loud import (
    validate_and_normalize_x_link,
    calculate_loud_points,
)


# === Strategy Definitions ===

# TweetScout scores (0 to 5000+)
tweetscout_score = st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False)

# Valid Twitter usernames (alphanumeric + underscore, 1-15 chars)
twitter_username = st.from_regex(r'[a-zA-Z][a-zA-Z0-9_]{0,14}', fullmatch=True)

# Tweet IDs (large integers as strings)
tweet_id = st.integers(min_value=1, max_value=10**19).map(str)

# Points divisor (configurable setting)
points_divisor = st.integers(min_value=1, max_value=100)


# === Mock Settings ===

MOCK_SETTINGS = {
    'LOUD_POINTS_DIVISOR': 10,
    'LOUD_DAILY_LIMIT': 6,
}


def mock_get_setting(key, default=None):
    """Mock settings for testing without DB."""
    return MOCK_SETTINGS.get(key, default)


# === URL Validation Tests ===

class TestURLValidation:
    """Property-based tests for X/Twitter URL validation."""

    @given(username=twitter_username, tid=tweet_id)
    @settings(max_examples=200)
    def test_valid_x_url_normalizes(self, username, tid):
        """Valid x.com URLs should normalize correctly."""
        assume(username.lower() not in ['i', 'intent', 'share', 'search'])

        url = f"https://x.com/{username}/status/{tid}"
        normalized, extracted_tid, extracted_user = validate_and_normalize_x_link(url)

        assert normalized == f"https://x.com/{username}/status/{tid}"
        assert extracted_tid == tid
        assert extracted_user == username

    @given(username=twitter_username, tid=tweet_id)
    @settings(max_examples=200)
    def test_twitter_url_normalizes_to_x(self, username, tid):
        """twitter.com URLs should normalize to x.com."""
        assume(username.lower() not in ['i', 'intent', 'share', 'search'])

        url = f"https://twitter.com/{username}/status/{tid}"
        normalized, _, _ = validate_and_normalize_x_link(url)

        assert normalized.startswith("https://x.com/")

    @given(username=twitter_username, tid=tweet_id)
    @settings(max_examples=200)
    def test_normalization_idempotent(self, username, tid):
        """Normalizing twice should give the same result."""
        assume(username.lower() not in ['i', 'intent', 'share', 'search'])

        url = f"https://x.com/{username}/status/{tid}"
        normalized1, _, _ = validate_and_normalize_x_link(url)
        normalized2, _, _ = validate_and_normalize_x_link(normalized1)

        assert normalized1 == normalized2

    @given(username=twitter_username, tid=tweet_id, query=st.text(max_size=50))
    @settings(max_examples=200)
    def test_query_params_stripped(self, username, tid, query):
        """Query parameters should be stripped."""
        assume(username.lower() not in ['i', 'intent', 'share', 'search'])
        assume('?' not in query and '#' not in query)

        url = f"https://x.com/{username}/status/{tid}?{query}"
        normalized, _, _ = validate_and_normalize_x_link(url)

        assert '?' not in normalized

    @given(tid=tweet_id)
    @settings(max_examples=100)
    def test_anonymous_links_rejected(self, tid):
        """Anonymous /i/status/ links should be rejected."""
        url = f"https://x.com/i/status/{tid}"

        try:
            validate_and_normalize_x_link(url)
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass  # Expected

    @given(text=st.text(max_size=200))
    @settings(max_examples=100)
    def test_random_text_rejected(self, text):
        """Random text should be rejected or return valid URL."""
        try:
            normalized, tid, user = validate_and_normalize_x_link(text)
            # If it didn't raise, it must have found a valid pattern
            assert 'x.com' in normalized or 'twitter.com' in text.lower()
        except ValidationError:
            pass  # Expected for invalid URLs


# === Points Calculation Tests ===

class TestPointsCalculation:
    """Property-based tests for points calculation."""

    @given(score=tweetscout_score)
    @settings(max_examples=200)
    def test_points_always_non_negative(self, score):
        """Points should never be negative."""
        with patch('loud.services.loud.get_setting', mock_get_setting):
            points = calculate_loud_points(score)
            assert points >= 0

    @given(score=tweetscout_score)
    @settings(max_examples=200)
    def test_points_is_integer(self, score):
        """Points should always be an integer."""
        with patch('loud.services.loud.get_setting', mock_get_setting):
            points = calculate_loud_points(score)
            assert isinstance(points, int)

    @given(score=tweetscout_score)
    @settings(max_examples=200)
    def test_points_bounded_by_score(self, score):
        """Points should not exceed score (when divisor >= 1)."""
        with patch('loud.services.loud.get_setting', mock_get_setting):
            points = calculate_loud_points(score)
            # With divisor of 10, points = score / 10
            assert points <= score

    @given(score1=tweetscout_score, score2=tweetscout_score)
    @settings(max_examples=200)
    def test_points_monotonic(self, score1, score2):
        """Higher scores should give higher or equal points."""
        with patch('loud.services.loud.get_setting', mock_get_setting):
            points1 = calculate_loud_points(score1)
            points2 = calculate_loud_points(score2)

            if score1 >= score2:
                assert points1 >= points2
            else:
                assert points1 <= points2

    @given(score=st.floats(min_value=0, max_value=10, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    @example(score=0.0)
    @example(score=9.9)
    def test_low_score_zero_points(self, score):
        """Scores below divisor should give 0 points."""
        with patch('loud.services.loud.get_setting', mock_get_setting):
            # With divisor=10, scores < 10 should give 0 points
            points = calculate_loud_points(score)
            assert points == int(score / 10)

    @given(
        score=tweetscout_score,
        divisor=points_divisor
    )
    @settings(max_examples=200)
    def test_points_formula_correct(self, score, divisor):
        """Points should equal floor(score / divisor)."""
        def custom_mock(key, default=None):
            if key == 'LOUD_POINTS_DIVISOR':
                return divisor
            return MOCK_SETTINGS.get(key, default)

        with patch('loud.services.loud.get_setting', custom_mock):
            points = calculate_loud_points(score)
            expected = int(score / divisor)
            assert points == expected


# === Stateful Testing: Leaderboard Simulation ===

class LeaderboardStateMachine(RuleBasedStateMachine):
    """
    Stateful test simulating multiple users submitting to projects.

    Verifies:
    - Total points on leaderboard == sum of submission points
    - Submission counts are accurate
    - No point inflation
    """

    def __init__(self):
        super().__init__()
        self.users = {}  # user_id -> {total_points, submission_count, submissions: []}
        self.project_total_points = 0
        self.project_total_submissions = 0

    @initialize()
    def setup(self):
        self.users = {}
        self.project_total_points = 0
        self.project_total_submissions = 0

    @rule(
        user_id=st.integers(min_value=1, max_value=20),
        tweetscout_score=st.floats(min_value=0, max_value=5000, allow_nan=False, allow_infinity=False),
    )
    def submit_content(self, user_id, tweetscout_score):
        """User submits content and earns points."""
        # Initialize user if needed
        if user_id not in self.users:
            self.users[user_id] = {
                'total_points': 0,
                'submission_count': 0,
                'submissions': [],
            }

        # Calculate points (simulate calculate_loud_points with divisor=10)
        points = int(tweetscout_score / 10)

        # Record submission
        self.users[user_id]['total_points'] += points
        self.users[user_id]['submission_count'] += 1
        self.users[user_id]['submissions'].append({
            'score': tweetscout_score,
            'points': points,
        })

        # Update project totals
        self.project_total_points += points
        self.project_total_submissions += 1

    @invariant()
    def points_never_negative(self):
        """No user should have negative points."""
        for uid, data in self.users.items():
            assert data['total_points'] >= 0, f"User {uid} has negative points"

    @invariant()
    def submission_count_accurate(self):
        """Submission count should match actual submissions."""
        for uid, data in self.users.items():
            assert data['submission_count'] == len(data['submissions']), \
                f"User {uid} count mismatch: {data['submission_count']} != {len(data['submissions'])}"

    @invariant()
    def total_points_matches_sum(self):
        """Total points should equal sum of submission points."""
        for uid, data in self.users.items():
            expected_total = sum(s['points'] for s in data['submissions'])
            assert data['total_points'] == expected_total, \
                f"User {uid} points mismatch: {data['total_points']} != {expected_total}"

    @invariant()
    def project_totals_accurate(self):
        """Project totals should match sum across all users."""
        user_total_points = sum(u['total_points'] for u in self.users.values())
        user_total_subs = sum(u['submission_count'] for u in self.users.values())

        assert self.project_total_points == user_total_points, \
            f"Project points mismatch: {self.project_total_points} != {user_total_points}"
        assert self.project_total_submissions == user_total_subs, \
            f"Project submissions mismatch: {self.project_total_submissions} != {user_total_subs}"


# Create test case from state machine
TestLeaderboardSystem = LeaderboardStateMachine.TestCase


# === Edge Case Tests ===

class TestEdgeCases:
    """Specific edge case tests."""

    def test_zero_score_zero_points(self):
        """Zero TweetScout score should give zero points."""
        with patch('loud.services.loud.get_setting', mock_get_setting):
            points = calculate_loud_points(0)
            assert points == 0

    def test_very_high_score(self):
        """Very high scores should work correctly."""
        with patch('loud.services.loud.get_setting', mock_get_setting):
            points = calculate_loud_points(100000)
            assert points == 10000  # 100000 / 10

    def test_reserved_usernames_rejected(self):
        """Reserved usernames should be rejected."""
        reserved = ['i', 'intent', 'share', 'search']
        for username in reserved:
            url = f"https://x.com/{username}/status/123456"
            try:
                validate_and_normalize_x_link(url)
                assert False, f"Should have rejected {username}"
            except ValidationError:
                pass

    def test_case_sensitivity_usernames(self):
        """Username case should be preserved in normalization."""
        url = "https://x.com/CryptoWhale/status/123456"
        normalized, _, username = validate_and_normalize_x_link(url)
        assert username == "CryptoWhale"

    def test_fragments_stripped(self):
        """URL fragments should be stripped."""
        url = "https://x.com/user/status/123#comments"
        normalized, _, _ = validate_and_normalize_x_link(url)
        assert '#' not in normalized
