import secrets
import uuid

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

    # Redirect tracking
    redirect_token = models.CharField(
        max_length=32,
        unique=True,
        default=generate_redirect_token,
        db_index=True,
    )

    # Credit escrow
    escrow = models.IntegerField(default=settings.ECHO_CONFIG["POST_COST"])
    initial_escrow = models.IntegerField(default=settings.ECHO_CONFIG["POST_COST"])

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
        return int((self.engagement_count / self.initial_escrow) * 100)

    @property
    def redirect_url(self):
        """Full redirect URL for this post."""
        # This would need to be configured with your domain
        base_url = settings.get("REDIRECT_BASE_URL", "http://localhost:8000")
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

        if refund and self.escrow > 0:
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
    credit_granted = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "engagements"
        # One engagement per user per post
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_user_post_engagement",
            )
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

    # Budget
    credit_reward = models.IntegerField(default=2)  # Extra credits per engagement
    total_budget = models.IntegerField()  # Total credits available
    remaining_budget = models.IntegerField()  # Credits left to distribute

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sponsored_posts"

    def __str__(self):
        return f"Sponsored by {self.sponsor_name}"

    @property
    def is_active(self):
        """Check if sponsorship still has budget."""
        return self.remaining_budget > 0 and self.post.status == Post.Status.ACTIVE
