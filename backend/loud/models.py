"""
Loud models for UGC rewards feature.

Models:
- LoudProject: Admin-created campaigns with time limits and TweetScout requirements
- LoudSubmission: User submissions with globally unique tweet_id
- LoudLeaderboardEntry: Denormalized leaderboard for fast queries
"""
import uuid

from django.db import models
from django.db.models import Index, UniqueConstraint

from core.models import User


class LoudProject(models.Model):
    """
    A sponsored project/campaign that users can submit UGC content to.
    Created and managed by admins via Django admin.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Project name, e.g. 'Uniswap V4 Launch'")
    slug = models.SlugField(unique=True, help_text="URL-friendly identifier")
    description = models.TextField(help_text="Description shown to users")
    logo_url = models.URLField(null=True, blank=True, help_text="Project logo URL")

    # Timing
    starts_at = models.DateTimeField(help_text="When the project becomes visible")
    ends_at = models.DateTimeField(help_text="When the project stops accepting submissions")

    # Eligibility (per-project)
    min_tweetscout_score = models.PositiveIntegerField(
        default=0,
        help_text="Minimum TweetScout score required to submit (0 = no minimum)"
    )

    # Limits (configurable per project)
    max_submissions_per_user = models.PositiveIntegerField(
        default=4,
        help_text="Maximum submissions per user for this project"
    )

    # Rewards pool (optional - for display only)
    reward_pool = models.CharField(
        max_length=100,
        blank=True,
        help_text="Display text for reward pool, e.g. '$5000 USDC'"
    )
    reward_description = models.TextField(
        blank=True,
        help_text="Additional reward details"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Admin can pause/unpause the project"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loud_projects'
        ordering = ['-created_at']
        indexes = [
            Index(fields=['is_active', 'ends_at']),
        ]

    def __str__(self):
        return self.name


class LoudSubmission(models.Model):
    """
    A user's UGC submission to a project.
    Points are calculated and frozen at submission time based on TweetScout score.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loud_submissions'
    )
    project = models.ForeignKey(
        LoudProject,
        on_delete=models.CASCADE,
        related_name='submissions'
    )

    # Submission data (normalized)
    x_link = models.URLField(help_text="Normalized X/Twitter link")
    tweet_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Extracted tweet ID for global uniqueness"
    )
    x_username = models.CharField(
        max_length=50,
        help_text="Username extracted from link"
    )

    # Points awarded (frozen at submission time)
    points_awarded = models.PositiveIntegerField(
        help_text="Points calculated from TweetScout score at submission"
    )
    tweetscout_score_at_submission = models.FloatField(
        help_text="Snapshot of user's TweetScout score for audit"
    )

    # Timestamps
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'loud_submissions'
        constraints = [
            # GLOBALLY unique - same tweet cannot be submitted anywhere
            UniqueConstraint(fields=['tweet_id'], name='unique_submission_tweet_id'),
            # Points must be non-negative
            models.CheckConstraint(
                check=models.Q(points_awarded__gte=0),
                name='loud_submission_points_non_negative'
            ),
            # TweetScout score snapshot must be non-negative
            models.CheckConstraint(
                check=models.Q(tweetscout_score_at_submission__gte=0),
                name='loud_submission_score_non_negative'
            ),
        ]
        indexes = [
            Index(fields=['user', 'submitted_at']),
            Index(fields=['project', '-points_awarded']),
        ]

    def __str__(self):
        return f"{self.user.display_name} -> {self.project.name} ({self.points_awarded} pts)"


class LoudLeaderboardEntry(models.Model):
    """
    Denormalized leaderboard entry for fast queries.
    Updated atomically using F() expressions on each submission.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        LoudProject,
        on_delete=models.CASCADE,
        related_name='leaderboard_entries'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='loud_leaderboard_entries'
    )

    total_points = models.PositiveIntegerField(default=0)
    submission_count = models.PositiveIntegerField(default=0)
    last_submission_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'loud_leaderboard'
        constraints = [
            UniqueConstraint(
                fields=['project', 'user'],
                name='unique_project_user_leaderboard'
            ),
            # Total points must be non-negative
            models.CheckConstraint(
                check=models.Q(total_points__gte=0),
                name='loud_leaderboard_points_non_negative'
            ),
            # Submission count must be non-negative
            models.CheckConstraint(
                check=models.Q(submission_count__gte=0),
                name='loud_leaderboard_count_non_negative'
            ),
        ]
        indexes = [
            Index(fields=['project', '-total_points']),
        ]

    def __str__(self):
        return f"{self.user.display_name} - {self.project.name}: {self.total_points} pts"
