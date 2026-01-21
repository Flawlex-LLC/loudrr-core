import secrets
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_redirect_token():
    """Generate a unique token for redirect URLs."""
    return secrets.token_urlsafe(16)


class Post(models.Model):
    """
    A post submitted by a creator for engagement.

    Posts hold credits in escrow that are distributed to engagers.
    When escrow reaches 0, the post is automatically completed.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Platform(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        DISCORD = "discord", "Discord"
        WEB = "web", "Web"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="posts",
    )

    # X/Twitter link
    x_link = models.URLField(max_length=500)
    tweet_id = models.CharField(max_length=50, blank=True, db_index=True)  # Extracted from URL (v1)

    # Cached tweet content (fetched on submission for feed display)
    tweet_text = models.TextField(blank=True, help_text="Tweet text content")
    tweet_author_name = models.CharField(max_length=100, blank=True, help_text="Author display name")
    tweet_author_username = models.CharField(max_length=50, blank=True, help_text="Author @handle")
    tweet_author_avatar = models.URLField(max_length=500, blank=True, help_text="Author profile image URL")
    tweet_media = models.JSONField(default=list, blank=True, help_text="Array of media URLs")
    tweet_created_at = models.DateTimeField(null=True, blank=True, help_text="When tweet was posted")

    # Sponsored post flag (v1)
    is_sponsored = models.BooleanField(default=False)

    # Redirect tracking
    redirect_token = models.CharField(
        max_length=32,
        unique=True,
        default=generate_redirect_token,
        db_index=True,
    )

    # Credit escrow (Decimal for multiplier precision - 4 decimal places)
    escrow = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal(str(settings.ECHO_CONFIG["POST_COST"]))
    )
    initial_escrow = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal(str(settings.ECHO_CONFIG["POST_COST"]))
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    # Platform where post was submitted
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
    )

    # Platform-specific message tracking (for updates/deletions)
    channel_id = models.BigIntegerField(null=True, blank=True)
    message_id = models.BigIntegerField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "posts"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["redirect_token"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(escrow__gte=0),
                name="post_escrow_non_negative"
            ),
        ]

    def __str__(self):
        return f"Post by {self.user} ({self.status})"

    @property
    def engagement_count(self):
        """Number of engagements received."""
        return self.initial_escrow - self.escrow

    @property
    def engagement_progress(self):
        """Progress as percentage (0-100)."""
        if self.initial_escrow == 0:
            return 100
        return int((float(self.engagement_count) / float(self.initial_escrow)) * 100)

    @property
    def redirect_url(self):
        """Full redirect URL for this post."""
        # This would need to be configured with your domain
        base_url = getattr(settings, "REDIRECT_BASE_URL", "http://localhost:8000")
        return f"{base_url}/r/{self.redirect_token}/"

    def get_redirect_url_for_user(self, user):
        """
        Get personalized redirect URL for a specific user.

        The URL includes encrypted user ID for engagement tracking.
        """
        from core.services.engagements import encrypt_user_id

        base_url = self.redirect_url
        encrypted_id = encrypt_user_id(str(user.id))
        return f"{base_url}?u={encrypted_id}"

    def cancel(self, refund: bool = True):
        """
        Cancel this post.

        Args:
            refund: Whether to refund remaining escrow to user
        """
        if self.status != self.Status.ACTIVE:
            return

        if refund and self.escrow > Decimal('0'):
            from core.services.credits import CreditService

            credit_service = CreditService(self.user)
            credit_service.refund(
                amount=self.escrow,
                reference_id=self.id,
                reference_type="post",
                description=f"Refund for cancelled post",
            )

        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])


class Engagement(models.Model):
    """
    Record of a user engaging with a post.

    Created when a user clicks the redirect link.
    Each user can only engage once per post.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="engagements",
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="engagements",
    )

    # Tracking
    clicked_at = models.DateTimeField(default=timezone.now)
    credit_granted = models.BooleanField(default=False)

    # Verification status
    verified = models.BooleanField(default=False)
    like_verified = models.BooleanField(default=False)
    reply_verified = models.BooleanField(default=False)
    verification_data = models.JSONField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "engagements"
        # One engagement per user per post
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_user_post_engagement",
            ),
            # Prevent invalid state: can't grant credit without verification
            models.CheckConstraint(
                check=~models.Q(verified=False, credit_granted=True),
                name="engagement_credit_requires_verification"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["post", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} engaged with {self.post}"


class SponsoredPost(models.Model):
    """
    Sponsored post configuration.

    Sponsored posts don't consume the poster's credits.
    Instead, a sponsor funds the engagement rewards.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.OneToOneField(
        Post,
        on_delete=models.CASCADE,
        related_name="sponsorship",
    )

    # Sponsor info
    sponsor_name = models.CharField(max_length=100)
    sponsor_contact = models.CharField(max_length=200, blank=True)

    # Budget (Decimal for multiplier precision - 4 decimal places)
    credit_reward = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal('2'))  # Extra credits per engagement
    total_budget = models.DecimalField(max_digits=12, decimal_places=4)  # Total credits available
    remaining_budget = models.DecimalField(max_digits=12, decimal_places=4)  # Credits left to distribute

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sponsored_posts"
        constraints = [
            models.CheckConstraint(
                check=models.Q(remaining_budget__gte=0),
                name="sponsored_budget_non_negative"
            ),
        ]

    def __str__(self):
        return f"Sponsored by {self.sponsor_name}"

    @property
    def is_active(self):
        """Check if sponsorship still has budget."""
        return self.remaining_budget > Decimal('0') and self.post.status == Post.Status.ACTIVE


class Campaign(models.Model):
    """
    Campaign/Giveaway for reward-based engagement.

    Types:
    - Raffle: Random winners from participants
    - Score-based: Weighted payouts based on XP or TweetScout score

    Eligibility:
    - All criteria fields default to 0/False (no requirement)
    - Set min_sponsored_xp=0 for open giveaways
    - All criteria must be met for entry
    """

    class Type(models.TextChoices):
        RAFFLE = "raffle", "Raffle"
        SCORE_BASED = "score_based", "Score Based"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class WinnerMethod(models.TextChoices):
        RANDOM = "random", "Random Draw"
        WEIGHTED_XP = "weighted_xp", "Weighted by XP"
        WEIGHTED_SCORE = "weighted_score", "Weighted by TweetScout"
        FIRST_COME = "first_come", "First Come First Served"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=Type.choices)

    # Budget (in USD or credits depending on use case)
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_budget = models.DecimalField(max_digits=10, decimal_places=2)

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # Timing
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    entry_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text="Deadline for entries. Defaults to ends_at if not set."
    )

    # === Eligibility Criteria (0 or False = no requirement) ===
    min_sponsored_xp = models.IntegerField(
        default=0,
        help_text="Minimum XP required to enter (0 = open to all)"
    )
    min_engagements = models.IntegerField(
        default=0,
        help_text="Minimum total engagements required"
    )
    min_posts = models.IntegerField(
        default=0,
        help_text="Minimum posts submitted required"
    )
    min_streak = models.IntegerField(
        default=0,
        help_text="Minimum current streak required"
    )
    min_tweetscout_score = models.FloatField(
        default=0,
        help_text="Minimum TweetScout score required"
    )
    require_x_linked = models.BooleanField(
        default=False,
        help_text="Require X/Twitter account linked"
    )

    # === Giveaway Configuration ===
    max_entries = models.IntegerField(
        null=True, blank=True,
        help_text="Max entries allowed (null = unlimited)"
    )
    max_winners = models.IntegerField(
        default=1,
        help_text="Number of winners to select"
    )
    prize_description = models.TextField(
        blank=True,
        help_text="Description of prize(s)"
    )
    prize_value = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Prize value in USD (optional)"
    )
    winner_selection_method = models.CharField(
        max_length=20,
        choices=WinnerMethod.choices,
        default=WinnerMethod.RANDOM
    )

    # Results
    winners_announced_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "campaigns"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(remaining_budget__gte=0),
                name="campaign_budget_non_negative"
            ),
            models.CheckConstraint(
                check=models.Q(min_sponsored_xp__gte=0),
                name="campaign_min_xp_non_negative"
            ),
            models.CheckConstraint(
                check=models.Q(max_winners__gte=1),
                name="campaign_max_winners_positive"
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.type})"

    @property
    def is_active(self):
        """Check if campaign is currently active and accepting entries."""
        now = timezone.now()
        deadline = self.entry_deadline or self.ends_at
        return (
            self.status == self.Status.ACTIVE
            and self.starts_at <= now <= deadline
            and self.remaining_budget > 0
        )

    @property
    def entry_count(self):
        """Get count of eligible entries."""
        return self.entries.filter(status='eligible').count()

    def get_eligibility_requirements(self):
        """Get human-readable list of requirements."""
        reqs = []
        if self.min_sponsored_xp > 0:
            reqs.append(f"{self.min_sponsored_xp} XP")
        if self.min_engagements > 0:
            reqs.append(f"{self.min_engagements} engagements")
        if self.min_posts > 0:
            reqs.append(f"{self.min_posts} posts")
        if self.min_streak > 0:
            reqs.append(f"{self.min_streak} day streak")
        if self.min_tweetscout_score > 0:
            reqs.append(f"TweetScout {self.min_tweetscout_score}+")
        if self.require_x_linked:
            reqs.append("X account linked")
        return reqs or ["Open to all"]


class CampaignEntry(models.Model):
    """
    User entry in a campaign/giveaway.

    Tracks:
    - Entry status (pending, eligible, ineligible, winner)
    - Eligibility snapshot at time of entry (for audit)
    - Payout status for winners
    """

    class EntryStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ELIGIBLE = "eligible", "Eligible"
        INELIGIBLE = "ineligible", "Ineligible"
        WINNER = "winner", "Winner"
        CLAIMED = "claimed", "Prize Claimed"

    class EntrySource(models.TextChoices):
        MINIAPP = "miniapp", "Mini App"
        BOT = "bot", "Telegram Bot"
        ADMIN = "admin", "Admin Panel"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="campaign_entries",
    )

    # Entry Status
    status = models.CharField(
        max_length=20,
        choices=EntryStatus.choices,
        default=EntryStatus.PENDING
    )

    # Eligibility snapshot (captured at entry time for audit)
    # Stores: sponsored_xp, total_engagements, tweetscout_score, etc.
    eligibility_snapshot = models.JSONField(
        default=dict,
        help_text="User stats captured at time of entry"
    )
    ineligibility_reason = models.TextField(
        blank=True,
        help_text="Why entry was marked ineligible"
    )

    # Submitted tweet for the campaign (optional)
    tweet_url = models.URLField(max_length=500, blank=True)
    tweet_id = models.CharField(max_length=50, blank=True)

    # Legacy verification fields
    verified = models.BooleanField(default=False)
    verification_data = models.JSONField(null=True, blank=True)

    # Winner status
    is_winner = models.BooleanField(default=False)
    prize_claimed = models.BooleanField(default=False)
    prize_claimed_at = models.DateTimeField(null=True, blank=True)

    # Payout (null until campaign completes)
    payout_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payout_status = models.CharField(max_length=20, blank=True)  # pending, paid, failed

    # Entry metadata
    entry_source = models.CharField(
        max_length=20,
        choices=EntrySource.choices,
        default=EntrySource.MINIAPP
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "campaign_entries"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"],
                name="unique_campaign_user_entry",
            )
        ]

    def __str__(self):
        return f"{self.user} in {self.campaign.name} ({self.status})"

    @property
    def xp_at_entry(self):
        """Get XP from eligibility snapshot."""
        return self.eligibility_snapshot.get('sponsored_xp', 0)


class VerificationBatch(models.Model):
    """
    Queued verification batch for async processing.

    Similar to spot trading orders - users can queue verifications
    and continue engaging while verification processes in background.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="verification_batches",
    )

    # Engagements in this batch (stored as list of engagement IDs)
    engagement_ids = models.JSONField(default=list, help_text="List of engagement UUIDs in this batch")

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Results (filled after verification completes)
    passed = models.IntegerField(null=True, blank=True, help_text="Number of verifications passed")
    failed = models.IntegerField(null=True, blank=True, help_text="Number of verifications failed")
    credits_awarded = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Total karma awarded"
    )
    message = models.TextField(blank=True, help_text="Result message for user")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "verification_batches"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"Batch {self.id} - {self.user} ({self.status})"


# === Auditlog Registration ===
# Track all changes to models (admin + API + any other source)
from auditlog.registry import auditlog

auditlog.register(Post)
auditlog.register(Engagement)
auditlog.register(SponsoredPost)
auditlog.register(Campaign)
auditlog.register(CampaignEntry)
auditlog.register(VerificationBatch)
