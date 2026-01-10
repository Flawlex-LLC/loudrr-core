import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager for ECHO users."""

    def create_user(self, telegram_id=None, discord_id=None, **extra_fields):
        """Create a user with either Telegram or Discord ID."""
        if not telegram_id and not discord_id:
            raise ValueError("User must have either telegram_id or discord_id")

        user = self.model(telegram_id=telegram_id, discord_id=discord_id, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, telegram_id=None, discord_id=None, **extra_fields):
        """Create a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(telegram_id, discord_id, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for ECHO.

    Users can link both Telegram and Discord accounts to the same identity.
    Credits are shared across platforms.
    """

    class Tier(models.TextChoices):
        BRONZE = "bronze", "Bronze"
        SILVER = "silver", "Silver"
        GOLD = "gold", "Gold"
        PLATINUM = "platinum", "Platinum"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Platform identifiers (at least one required)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    discord_id = models.BigIntegerField(unique=True, null=True, blank=True)

    # X/Twitter info
    x_username = models.CharField(max_length=50, blank=True)

    # Display name (from platform)
    display_name = models.CharField(max_length=100, blank=True)

    # Credits
    credits = models.IntegerField(default=0)
    total_credits_earned = models.IntegerField(default=0)
    total_credits_spent = models.IntegerField(default=0)

    # Daily/weekly limits (reset by Celery tasks)
    daily_credits_earned = models.IntegerField(default=0)
    daily_earned_reset_at = models.DateTimeField(default=timezone.now)
    weekly_credits_purchased = models.IntegerField(default=0)
    weekly_purchased_reset_at = models.DateTimeField(default=timezone.now)

    # Engagement stats
    total_engagements = models.IntegerField(default=0)
    total_posts = models.IntegerField(default=0)

    # Streaks
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_engagement_date = models.DateField(null=True, blank=True)
    streak_freeze_available = models.BooleanField(default=True)

    # Tier (computed from total_engagements)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.BRONZE)

    # Status
    is_active = models.BooleanField(default=True)
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True)

    # Admin
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Audit tracking
    audit_fail_count = models.IntegerField(default=0)
    last_audit_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "id"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["telegram_id"]),
            models.Index(fields=["discord_id"]),
            models.Index(fields=["total_engagements"]),
            models.Index(fields=["current_streak"]),
        ]

    def __str__(self):
        if self.display_name:
            return self.display_name
        if self.telegram_id:
            return f"TG:{self.telegram_id}"
        if self.discord_id:
            return f"DC:{self.discord_id}"
        return str(self.id)

    @property
    def platform_ids(self):
        """Get all linked platform IDs."""
        ids = {}
        if self.telegram_id:
            ids["telegram"] = self.telegram_id
        if self.discord_id:
            ids["discord"] = self.discord_id
        return ids

    def get_tier_multiplier(self):
        """Get credit earning multiplier based on tier."""
        config = settings.ECHO_CONFIG
        multipliers = {
            self.Tier.BRONZE: 1.0,
            self.Tier.SILVER: config["TIER_SILVER_MULTIPLIER"],
            self.Tier.GOLD: config["TIER_GOLD_MULTIPLIER"],
            self.Tier.PLATINUM: config["TIER_PLATINUM_MULTIPLIER"],
        }
        return multipliers.get(self.tier, 1.0)

    def get_streak_multiplier(self):
        """Get credit earning multiplier based on streak."""
        config = settings.ECHO_CONFIG
        if self.current_streak >= 30:
            return config["STREAK_30_DAY_MULTIPLIER"]
        elif self.current_streak >= 7:
            return config["STREAK_7_DAY_MULTIPLIER"]
        return 1.0

    def update_tier(self):
        """Update tier based on total engagements."""
        config = settings.ECHO_CONFIG
        if self.total_engagements >= config["TIER_PLATINUM_THRESHOLD"]:
            self.tier = self.Tier.PLATINUM
        elif self.total_engagements >= config["TIER_GOLD_THRESHOLD"]:
            self.tier = self.Tier.GOLD
        elif self.total_engagements >= config["TIER_SILVER_THRESHOLD"]:
            self.tier = self.Tier.SILVER
        else:
            self.tier = self.Tier.BRONZE


class Transaction(models.Model):
    """
    Record of all credit transactions.

    Provides audit trail for credits earned, spent, purchased, etc.
    """

    class Type(models.TextChoices):
        EARNED = "earned", "Earned from engagement"
        SPENT = "spent", "Spent on post"
        PURCHASED = "purchased", "Purchased"
        SPONSORED_REWARD = "sponsored_reward", "Sponsored post reward"
        REFUND = "refund", "Refund"
        PENALTY = "penalty", "Audit penalty"
        ADMIN_GRANT = "admin_grant", "Admin grant"
        ADMIN_REVOKE = "admin_revoke", "Admin revoke"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.IntegerField()  # Positive for gains, negative for losses
    balance_after = models.IntegerField()  # User's balance after this transaction

    # Reference to related object (post, engagement, etc.)
    reference_id = models.UUIDField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, blank=True)

    # Metadata
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.user} {self.type} {self.amount:+d}"


class AuditLog(models.Model):
    """
    Record of engagement audits.

    Random audits verify that users actually engaged with posts.
    """

    class Result(models.TextChoices):
        PENDING = "pending", "Pending"
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="audits")

    # What was audited
    engagement_id = models.UUIDField()
    post_id = models.UUIDField()

    # Result
    result = models.CharField(max_length=20, choices=Result.choices, default=Result.PENDING)
    penalty_applied = models.IntegerField(default=0)

    # Details
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Audit {self.user} - {self.result}"
