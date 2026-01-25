import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager for ECHO users."""

    def create_user(self, email=None, telegram_id=None, password=None, **extra_fields):
        """Create a user with Telegram ID or email."""
        if not telegram_id and not email:
            raise ValueError("User must have telegram_id or email")

        user = self.model(email=email, telegram_id=telegram_id, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
        """Create a superuser with email login."""
        if not email:
            raise ValueError("Superuser must have an email")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for Loudrr.

    Users authenticate via Telegram. Credits are managed per user.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Platform identifiers
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=50, blank=True, db_index=True)
    telegram_photo_url = models.URLField(max_length=500, blank=True)  # Profile photo from Telegram

    # X/Twitter info (unique constraint skipped - duplicates exist in production)
    x_username = models.CharField(max_length=50, blank=True, null=True, db_index=True)

    # Whitelist (for gated access)
    is_whitelisted = models.BooleanField(default=False, db_index=True)

    # Admin login (optional, only for superusers)
    email = models.EmailField(unique=True, null=True, blank=True)

    # Display name (from platform)
    display_name = models.CharField(max_length=100, blank=True)

    # Credits (Decimal for multiplier precision - 4 decimal places internal)
    credits = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    total_credits_earned = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    total_credits_spent = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    # Daily limits (reset by Celery tasks)
    daily_credits_earned = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    daily_earned_reset_at = models.DateTimeField(default=timezone.now)

    # Engagement stats
    total_engagements = models.IntegerField(default=0)
    total_posts = models.IntegerField(default=0)

    # Streaks
    current_streak = models.IntegerField(default=0)
    longest_streak = models.IntegerField(default=0)
    last_engagement_date = models.DateField(null=True, blank=True)
    streak_freeze_available = models.BooleanField(default=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True)
    has_claimed_bonus = models.BooleanField(default=False)

    # Admin
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Audit tracking
    audit_fail_count = models.IntegerField(default=0)
    last_audit_at = models.DateTimeField(null=True, blank=True)

    # Honesty score (0-50, drops on failed verification, no karma penalty)
    # 50 = perfect starting score
    # Drop scaled by failures: ceil(failures/2) per claim
    honesty_score = models.IntegerField(default=50)

    # Wallet for future payouts (v1)
    wallet_address = models.CharField(max_length=255, blank=True)

    # Activity tracking (v1)
    last_active_at = models.DateTimeField(auto_now=True)

    # TweetScout data (primary score for tier calculation)
    tweetscout_score = models.FloatField(default=0)  # Score from TweetScout API
    tweetscout_last_updated = models.DateTimeField(null=True, blank=True)

    # Sponsored XP (earned from sponsored post engagements)
    # Non-spendable reputation score for giveaway eligibility
    sponsored_xp = models.IntegerField(default=0)
    total_sponsored_xp_earned = models.IntegerField(default=0)  # Lifetime XP
    sponsored_engagements = models.IntegerField(default=0)  # Count of sponsored engagements

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        indexes = [
            models.Index(fields=["telegram_id"]),
            models.Index(fields=["total_engagements"]),
            models.Index(fields=["current_streak"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(credits__gte=0),
                name="user_credits_non_negative"
            ),
            models.CheckConstraint(
                check=models.Q(honesty_score__gte=0) & models.Q(honesty_score__lte=50),
                name="user_honesty_score_valid_range"
            ),
            models.CheckConstraint(
                check=models.Q(sponsored_xp__gte=0),
                name="user_sponsored_xp_non_negative"
            ),
            # Hard cap safety net - prevents corruption even if app logic fails
            # Actual configurable cap is enforced via DAILY_EARN_CAP setting
            models.CheckConstraint(
                check=models.Q(daily_credits_earned__gte=0) & models.Q(daily_credits_earned__lte=500),
                name="user_daily_credits_earned_valid_range"
            ),
            # Total earned/spent must be non-negative
            models.CheckConstraint(
                check=models.Q(total_credits_earned__gte=0),
                name="user_total_credits_earned_non_negative"
            ),
            models.CheckConstraint(
                check=models.Q(total_credits_spent__gte=0),
                name="user_total_credits_spent_non_negative"
            ),
        ]

    def __str__(self):
        if self.display_name:
            return self.display_name
        if self.telegram_id:
            return f"TG:{self.telegram_id}"
        return str(self.id)

    @property
    def platform_ids(self):
        """Get linked platform IDs."""
        ids = {}
        if self.telegram_id:
            ids["telegram"] = self.telegram_id
        return ids

    @property
    def tier(self):
        """Get tier name based on TweetScout score."""
        from core.services.tweet_score import get_tweet_score_tier
        return get_tweet_score_tier(self.tweetscout_score)

    @property
    def tier_multiplier(self):
        """Get karma multiplier based on TweetScout score."""
        from core.services.tweet_score import get_tweet_score_multiplier
        return float(get_tweet_score_multiplier(self.tweetscout_score))


class Transaction(models.Model):
    """
    Record of all credit transactions.

    Provides audit trail for credits earned, spent, purchased, etc.

    IDEMPOTENCY:
    - idempotency_key prevents duplicate transactions from retries
    - For engagements: use engagement_id as idempotency_key
    - For posts: use post_id as idempotency_key
    - Unique constraint on (user, type, idempotency_key) prevents duplicates
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
    amount = models.DecimalField(max_digits=12, decimal_places=4)  # Positive for gains, negative for losses
    balance_after = models.DecimalField(max_digits=12, decimal_places=4)  # User's balance after this transaction

    # Reference to related object (post, engagement, etc.)
    reference_id = models.UUIDField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, blank=True)

    # Idempotency key - prevents duplicate transactions from retries
    # Set to reference_id for most transactions, or a unique key for admin operations
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)

    # Metadata
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["type"]),
            models.Index(fields=["idempotency_key"]),
        ]
        constraints = [
            # Prevent duplicate transactions for same operation
            # idempotency_key can be empty for legacy transactions
            models.UniqueConstraint(
                fields=["user", "type", "idempotency_key"],
                name="transaction_idempotency_unique",
                condition=~models.Q(idempotency_key=''),  # Only enforce when key is set
            ),
            # Amount cannot be zero (no-op transactions)
            models.CheckConstraint(
                check=~models.Q(amount=0),
                name="transaction_amount_non_zero"
            ),
            # Balance after transaction must be non-negative (except penalties)
            # Note: Penalties can make balance negative temporarily
        ]

    def __str__(self):
        return f"{self.user} {self.type} {self.amount:+.2f}"


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
        verbose_name = "Engagement Audit"
        verbose_name_plural = "Engagement Audits"

    def __str__(self):
        return f"Audit {self.user} - {self.result}"


class XPTransaction(models.Model):
    """
    Audit trail for XP (experience points) changes.

    XP is separate from credits - it's a non-spendable reputation score
    earned from sponsored post engagements, used for giveaway eligibility.
    """

    class Type(models.TextChoices):
        EARNED = "earned", "Earned from sponsored engagement"
        ADMIN_GRANT = "admin_grant", "Admin grant"
        ADMIN_REVOKE = "admin_revoke", "Admin revoke"
        BONUS = "bonus", "Bonus XP"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="xp_transactions")
    type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=4)  # Positive for gains, negative for revokes
    balance_after = models.DecimalField(max_digits=12, decimal_places=4)  # User's XP balance after this transaction

    # Reference to related object (post, engagement, etc.)
    reference_id = models.UUIDField(null=True, blank=True)
    reference_type = models.CharField(max_length=50, blank=True)  # e.g., 'sponsored_post'

    # Metadata
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "xp_transactions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return f"{self.user} {self.type} {self.amount:+.2f} XP"


class XProfile(models.Model):
    """
    X/Twitter profile data from TweetScout API.

    Design principles:
    - OneToOne with User (each user has one X profile)
    - Stores ALL data from TweetScout in one place
    - Only fetched ONCE when user links their X account
    - Never called during operations - use cached data
    - Extensible: add new fields as TweetScout adds them

    Data source: TweetScout API (https://api.tweetscout.io/v2)
    - /score/{username} -> score
    - /info/{username} -> all other fields
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="x_profile"
    )

    # === Basic Info (from /info endpoint) ===
    x_user_id = models.CharField(max_length=50, db_index=True)  # Twitter's user ID
    username = models.CharField(max_length=50, db_index=True)   # @handle (screen_name)
    display_name = models.CharField(max_length=100)             # name
    bio = models.TextField(blank=True)                          # description

    # === Metrics ===
    followers_count = models.IntegerField(default=0)
    following_count = models.IntegerField(default=0)            # friends_count
    tweets_count = models.IntegerField(default=0)

    # === TweetScout Score (from /score endpoint) ===
    score = models.FloatField(default=0)                        # The main score for tier

    # === Profile Assets ===
    avatar_url = models.URLField(max_length=500, blank=True)
    banner_url = models.URLField(max_length=500, blank=True)

    # === Account Status ===
    is_verified = models.BooleanField(default=False)            # Blue check
    can_dm = models.BooleanField(default=False)                 # DMs open

    # === Account Age ===
    x_created_at = models.DateField(null=True, blank=True)      # register_date

    # === Metadata ===
    fetched_at = models.DateTimeField(auto_now_add=True)        # When we fetched this data
    updated_at = models.DateTimeField(auto_now=True)            # Last update

    # === Raw JSON (for future-proofing) ===
    # Store raw API response so we never lose data if we add fields later
    raw_tweetscout_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "x_profiles"
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["x_user_id"]),
            models.Index(fields=["score"]),
        ]

    def __str__(self):
        return f"@{self.username} (score: {self.score})"

    @property
    def tier(self) -> str:
        """Get web3-style tier name based on score."""
        from core.services.tweet_score import get_tweet_score_tier
        return get_tweet_score_tier(self.score)

    @property
    def multiplier(self) -> float:
        """Get karma multiplier based on score."""
        from core.services.tweet_score import get_tweet_score_multiplier
        return float(get_tweet_score_multiplier(self.score))


class SiteSetting(models.Model):
    """
    Dynamic settings that can be adjusted from admin panel.

    Design principles:
    - All operational constants (caps, costs, cooldowns) stored in DB
    - Cached for 5 minutes to avoid DB hits on every request
    - Falls back to ECHO_CONFIG if setting doesn't exist
    - Audit trail via updated_by field
    """

    class DataType(models.TextChoices):
        INTEGER = 'int', 'Integer'
        FLOAT = 'float', 'Float'
        DECIMAL = 'decimal', 'Decimal'
        BOOLEAN = 'bool', 'Boolean'
        STRING = 'str', 'String'

    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.CharField(max_length=500)
    data_type = models.CharField(max_length=10, choices=DataType.choices, default=DataType.INTEGER)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='setting_updates'
    )

    class Meta:
        db_table = 'site_settings'
        ordering = ['key']

    def __str__(self):
        return f"{self.key} = {self.value}"

    def get_value(self):
        """Get typed value based on data_type with crash protection."""
        try:
            if self.data_type == 'int':
                return int(self.value)
            elif self.data_type == 'float':
                return float(self.value)
            elif self.data_type == 'decimal':
                return Decimal(self.value)
            elif self.data_type == 'bool':
                return self.value.lower() in ('true', '1', 'yes')
            return self.value
        except (ValueError, TypeError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Invalid setting value for {self.key}: {self.value} (type: {self.data_type}) - {e}")
            # Return safe defaults to prevent app crash
            defaults = {'int': 0, 'float': 0.0, 'decimal': Decimal('0'), 'bool': False}
            return defaults.get(self.data_type, self.value)

    def save(self, *args, **kwargs):
        """Clear cache on save."""
        from django.core.cache import cache
        cache.delete(f'setting:{self.key}')
        super().save(*args, **kwargs)


class WaitlistEntry(models.Model):
    """
    Waitlist entries for users wanting to join Loudrr.

    Flow:
    1. User enters email on landing page -> PENDING
    2. User connects Telegram via deep link -> telegram_id linked
    3. User submits X username via bot -> SUBMITTED
    4. Admin approves -> APPROVED, User created
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending (email only)"
        SUBMITTED = "submitted", "Submitted (waiting approval)"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    join_token = models.CharField(max_length=32, unique=True, db_index=True)

    # Email (primary identifier from landing page)
    email = models.EmailField(unique=True, db_index=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=32, blank=True)

    # Email tracking for idempotency (prevents duplicate emails)
    email_confirmation_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When confirmation email was successfully sent"
    )
    email_already_registered_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When 'already registered' email was last sent"
    )
    email_send_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of email send attempts"
    )
    email_last_error = models.TextField(
        blank=True, default='',
        help_text="Last email error message for debugging"
    )

    # Telegram (from deep link)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_username = models.CharField(max_length=50, blank=True)
    telegram_display_name = models.CharField(max_length=100, blank=True)

    # X/Twitter (from bot popup)
    x_username = models.CharField(max_length=50, blank=True, db_index=True)

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Approval
    approved_at = models.DateTimeField(null=True, blank=True)
    created_user = models.OneToOneField(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='waitlist_entry'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "waitlist_entries"
        ordering = ["-created_at"]
        verbose_name = "Waitlist Entry"
        verbose_name_plural = "Waitlist Entries"

    def __str__(self):
        return f"{self.email} ({self.status})"


# === Auditlog Registration ===
# Track all changes to models (admin + API + any other source)
from auditlog.registry import auditlog

auditlog.register(User, exclude_fields=['password'])  # Only exclude password for security
auditlog.register(Transaction)
auditlog.register(AuditLog)  # Yes, audit the audit log too
auditlog.register(XPTransaction)
auditlog.register(XProfile)
auditlog.register(SiteSetting)
auditlog.register(WaitlistEntry)
