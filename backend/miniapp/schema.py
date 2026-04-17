"""
OpenAPI schema definitions for Mini App API.

This module defines serializers used for API documentation with drf-spectacular.
These are documentation-only serializers - actual validation happens in views.
"""
from rest_framework import serializers


# =============================================================================
# HEALTH & SETTINGS
# =============================================================================

class HealthResponseSerializer(serializers.Serializer):
    """Health check response."""
    status = serializers.CharField(help_text="Health status: 'ok' or error message")
    timestamp = serializers.DateTimeField(help_text="Server timestamp")


class SettingsResponseSerializer(serializers.Serializer):
    """App settings response."""
    post_cost = serializers.IntegerField(help_text="Karma cost to create a post")
    credit_per_engagement = serializers.IntegerField(help_text="Base credit per engagement")
    daily_earn_cap = serializers.IntegerField(help_text="Maximum karma earnable per day")
    min_session_duration = serializers.IntegerField(help_text="Minimum seconds before claiming")
    tier_thresholds = serializers.DictField(help_text="TweetScout score thresholds for each tier")
    tier_multipliers = serializers.DictField(help_text="Karma multipliers for each tier")


# =============================================================================
# WAITLIST
# =============================================================================

class WaitlistRegisterRequestSerializer(serializers.Serializer):
    """Register for waitlist from mini app with email and X profile link."""
    email = serializers.EmailField(help_text="User's email address")
    x_link = serializers.CharField(help_text="X profile URL (e.g. https://x.com/username)")
    referral_code = serializers.CharField(
        required=False,
        help_text="Optional referral code from existing user"
    )
    region = serializers.CharField(required=False, help_text="User's region (e.g. 'north_america')")
    niche = serializers.CharField(required=False, help_text="User's niche (e.g. 'memecoins')")
    other_platforms = serializers.ListField(required=False, help_text="Other platforms [{platform, username, platform_name?}]")


class WaitlistRegisterResponseSerializer(serializers.Serializer):
    """Waitlist registration response."""
    status = serializers.ChoiceField(
        choices=["registered", "already_registered"],
        help_text="Registration result"
    )
    message = serializers.CharField(help_text="Status message")
    x_username = serializers.CharField(required=False, help_text="Extracted X username")
    referral_code = serializers.CharField(required=False, help_text="User's personal referral code for sharing")


class WaitlistStatusResponseSerializer(serializers.Serializer):
    """Waitlist status response."""
    status = serializers.ChoiceField(
        choices=["submitted", "approved", "rejected", "waitlisted", "not_registered"],
        help_text="Current waitlist status"
    )
    x_username = serializers.CharField(required=False, help_text="X username if provided")
    submitted_at = serializers.CharField(required=False, help_text="ISO timestamp of submission")
    referral_code = serializers.CharField(required=False, help_text="User's personal referral code for sharing")


# =============================================================================
# USER
# =============================================================================

class UserInfoResponseSerializer(serializers.Serializer):
    """User profile information."""
    id = serializers.UUIDField(help_text="User ID")
    telegram_id = serializers.IntegerField(help_text="Telegram user ID")
    telegram_username = serializers.CharField(help_text="Telegram username")
    display_name = serializers.CharField(help_text="Display name")
    x_username = serializers.CharField(required=False, help_text="Linked X username")

    # Credits
    credits = serializers.FloatField(help_text="Current karma balance")
    total_credits_earned = serializers.FloatField(help_text="Lifetime karma earned")
    total_credits_spent = serializers.FloatField(help_text="Lifetime karma spent")
    daily_credits_earned = serializers.FloatField(help_text="Karma earned today")

    # TweetScout
    tweetscout_score = serializers.FloatField(required=False, help_text="TweetScout score")
    tier = serializers.CharField(help_text="User tier based on TweetScout score")
    tier_multiplier = serializers.FloatField(help_text="Karma multiplier for tier")

    # Engagement stats
    total_engagements = serializers.IntegerField(help_text="Total engagements completed")
    total_posts = serializers.IntegerField(help_text="Total posts created")
    current_streak = serializers.IntegerField(help_text="Current daily streak")
    longest_streak = serializers.IntegerField(help_text="Longest streak achieved")
    honesty_score = serializers.IntegerField(help_text="Verification honesty score (0-50)")

    # Flags
    is_whitelisted = serializers.BooleanField(help_text="Whether user is approved")
    loud_access = serializers.BooleanField(help_text="Whether user has LOUD feature access")


class UserStatsResponseSerializer(serializers.Serializer):
    """Detailed user statistics."""
    credits = serializers.FloatField()
    total_earned = serializers.FloatField()
    total_spent = serializers.FloatField()
    daily_earned = serializers.FloatField()
    daily_cap = serializers.IntegerField()
    daily_remaining = serializers.FloatField()

    engagements_today = serializers.IntegerField()
    engagements_total = serializers.IntegerField()
    posts_active = serializers.IntegerField()
    posts_total = serializers.IntegerField()

    streak_current = serializers.IntegerField()
    streak_longest = serializers.IntegerField()
    streak_bonus = serializers.IntegerField()

    tier = serializers.CharField()
    tier_multiplier = serializers.FloatField()
    tweetscout_score = serializers.FloatField(required=False)


class LinkXRequestSerializer(serializers.Serializer):
    """Link X account request."""
    x_username = serializers.CharField(help_text="X/Twitter username to link")


# =============================================================================
# ENGAGEMENT SESSION
# =============================================================================

class PostSerializer(serializers.Serializer):
    """Post data for engagement."""
    id = serializers.UUIDField()
    x_link = serializers.URLField(help_text="Link to X post")
    tweet_id = serializers.CharField()
    tweet_text = serializers.CharField()
    tweet_author_name = serializers.CharField()
    tweet_author_username = serializers.CharField()
    tweet_author_avatar = serializers.URLField(required=False)
    tweet_media = serializers.ListField(required=False)

    escrow_remaining = serializers.FloatField(help_text="Remaining escrow for rewards")
    engagement_goal = serializers.IntegerField()
    engagement_progress = serializers.IntegerField()
    hours_remaining = serializers.FloatField(help_text="Hours until post expires")

    creator_tier = serializers.CharField(help_text="Post creator's tier")
    creator_username = serializers.CharField()


class StartSessionResponseSerializer(serializers.Serializer):
    """Start session response with posts to engage."""
    success = serializers.BooleanField()
    posts = PostSerializer(many=True, help_text="List of posts to engage with")
    session_id = serializers.CharField(required=False, help_text="Session identifier")


class RecordClickRequestSerializer(serializers.Serializer):
    """Record click on post."""
    post_id = serializers.UUIDField(help_text="Post ID that was clicked")


class RecordClickResponseSerializer(serializers.Serializer):
    """Click recorded response."""
    success = serializers.BooleanField()
    redirect_url = serializers.URLField(help_text="URL to redirect user to X post")


class QueueClaimRequestSerializer(serializers.Serializer):
    """Queue claims for verification."""
    post_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="List of post IDs to claim engagement for"
    )


class QueueClaimResponseSerializer(serializers.Serializer):
    """Queue claim response."""
    success = serializers.BooleanField()
    batch_id = serializers.UUIDField(help_text="Verification batch ID")
    queued_count = serializers.IntegerField(help_text="Number of claims queued")
    message = serializers.CharField()


class ClaimBatchSerializer(serializers.Serializer):
    """Claim batch history item."""
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=["pending", "processing", "completed", "failed"])
    claims_count = serializers.IntegerField()
    verified_count = serializers.IntegerField()
    credits_awarded = serializers.FloatField()
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(required=False)


class ClaimHistoryResponseSerializer(serializers.Serializer):
    """Claim history response."""
    batches = ClaimBatchSerializer(many=True)
    total_batches = serializers.IntegerField()


# =============================================================================
# POSTS
# =============================================================================

class SubmitPostRequestSerializer(serializers.Serializer):
    """Submit new post for promotion."""
    x_link = serializers.URLField(help_text="URL to X post")
    escrow = serializers.IntegerField(
        help_text="Karma to escrow for rewards (determines engagement goal)"
    )


class SubmitPostResponseSerializer(serializers.Serializer):
    """Post submission response."""
    success = serializers.BooleanField()
    post_id = serializers.UUIDField(help_text="Created post ID")
    escrow_deducted = serializers.FloatField()
    engagement_goal = serializers.IntegerField()
    message = serializers.CharField()


# =============================================================================
# REFERRAL
# =============================================================================

class ReferralInfoResponseSerializer(serializers.Serializer):
    """Referral information and stats."""
    referral_code = serializers.CharField(help_text="User's referral code")
    referral_link_web = serializers.URLField(help_text="Web referral link")
    referral_link_telegram = serializers.URLField(help_text="Telegram referral link")
    total_referrals = serializers.IntegerField(help_text="Total approved referrals")
    referred_by = serializers.CharField(required=False, help_text="Username who referred this user")


# =============================================================================
# FEATURE INTEREST
# =============================================================================

class FeatureInterestRequestSerializer(serializers.Serializer):
    """Register interest in features."""
    features = serializers.ListField(
        child=serializers.CharField(),
        help_text="List of feature names user is interested in"
    )


class FeatureInterestResponseSerializer(serializers.Serializer):
    """Feature interest response."""
    success = serializers.BooleanField()
    registered_features = serializers.ListField(child=serializers.CharField())


# =============================================================================
# ONBOARDING
# =============================================================================

class CompleteOnboardingResponseSerializer(serializers.Serializer):
    """Onboarding completion response."""
    success = serializers.BooleanField()
    tweetscout_score = serializers.FloatField(required=False, help_text="Fetched TweetScout score")
    tier = serializers.CharField(help_text="Assigned tier")
    message = serializers.CharField()


# =============================================================================
# ERROR RESPONSES
# =============================================================================

class ErrorResponseSerializer(serializers.Serializer):
    """Standard error response."""
    error = serializers.CharField(help_text="Error message")
    code = serializers.CharField(required=False, help_text="Error code")
    details = serializers.DictField(required=False, help_text="Additional error details")
