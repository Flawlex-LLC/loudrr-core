"""
Loud service for UGC rewards.

Handles submissions, rate limiting, and leaderboard updates with atomic operations.

Concurrency Model (100 simultaneous users to same project):
- Each user locks their OWN User row (select_for_update) - no blocking between users
- LoudSubmission unique constraint on tweet_id handles duplicate posts
- LoudLeaderboardEntry uses F() expressions - no read-modify-write races
- Each user updates their own (project, user) leaderboard entry - no conflicts
"""
import logging
import re
from typing import Optional

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from core.models import User
from core.services.settings import get_setting
from loud.models import LoudProject, LoudSubmission, LoudLeaderboardEntry

logger = logging.getLogger(__name__)


def validate_and_normalize_x_link(url: str) -> tuple[str, str, str]:
    """
    Validate and normalize an X/Twitter link.

    Returns:
        tuple: (normalized_url, tweet_id, username)

    Raises:
        ValidationError: If link format is invalid
    """
    # Strip query params and fragments
    url = url.split('?')[0].split('#')[0]

    # Reject i/status pattern (anonymous links)
    if '/i/status/' in url:
        logger.debug("URL validation failed: anonymous link", extra={'url': url[:100]})
        raise ValidationError("Anonymous links not accepted. Use link with username.")

    # Extract username and tweet_id
    pattern = r'(?:x\.com|twitter\.com)/([^/]+)/status/(\d+)'
    match = re.search(pattern, url)

    if not match:
        logger.debug("URL validation failed: invalid format", extra={'url': url[:100]})
        raise ValidationError("Invalid X/Twitter link format. Use: x.com/username/status/...")

    username, tweet_id = match.groups()

    # Reject special usernames
    if username.lower() in ['i', 'intent', 'share', 'search']:
        logger.debug("URL validation failed: reserved username", extra={'url': url[:100], 'username': username})
        raise ValidationError("Invalid link format")

    # Normalize to x.com format
    normalized = f"https://x.com/{username}/status/{tweet_id}"

    return normalized, tweet_id, username


def calculate_loud_points(tweetscout_score: float) -> int:
    """
    Calculate points from TweetScout score.

    Formula: points = floor(tweetscout_score / divisor)
    Default divisor is 10.
    """
    divisor = get_setting('LOUD_POINTS_DIVISOR', 10)
    return int(tweetscout_score / divisor)


class LoudService:
    """Service for managing Loud submissions and leaderboards."""

    def __init__(self, user: User):
        self.user = user

    def get_live_projects(self) -> list[LoudProject]:
        """Get active, non-expired projects."""
        now = timezone.now()
        return list(LoudProject.objects.filter(
            is_active=True,
            starts_at__lte=now,
            ends_at__gt=now,
        ).order_by('-created_at'))

    def can_submit(self, project: LoudProject) -> tuple[bool, str]:
        """
        Check if user can submit to a project.

        Returns:
            tuple: (can_submit, error_message)
        """
        # Check 0: X account linked
        if not self.user.x_username:
            return False, "Link your X account to submit"

        # Check 1: TweetScout minimum for this project
        score = self.user.tweetscout_score or 0
        if score < project.min_tweetscout_score:
            return False, f"Requires TweetScout score of {project.min_tweetscout_score}+"

        # Check 2: Global daily limit
        today_count = LoudSubmission.objects.filter(
            user=self.user,
            submitted_at__date=timezone.now().date()
        ).count()

        daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)
        if today_count >= daily_limit:
            return False, f"Daily limit reached ({daily_limit} posts)"

        # Check 3: Per-project limit
        project_count = LoudSubmission.objects.filter(
            user=self.user,
            project=project
        ).count()

        if project_count >= project.max_submissions_per_user:
            return False, f"Project limit reached ({project.max_submissions_per_user} posts)"

        return True, ""

    def get_daily_submissions_remaining(self) -> int:
        """Get remaining submissions for today."""
        today_count = LoudSubmission.objects.filter(
            user=self.user,
            submitted_at__date=timezone.now().date()
        ).count()
        daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)
        return max(0, daily_limit - today_count)

    def get_project_submissions_remaining(self, project: LoudProject) -> int:
        """Get remaining submissions for a specific project."""
        project_count = LoudSubmission.objects.filter(
            user=self.user,
            project=project
        ).count()
        return max(0, project.max_submissions_per_user - project_count)

    @transaction.atomic
    def submit(self, project: LoudProject, x_link: str) -> LoudSubmission:
        """
        Submit content to a project.

        Uses atomic operations to prevent race conditions:
        1. Lock user row FIRST to prevent daily limit race condition
        2. Unique constraint on tweet_id prevents duplicate submissions
        3. F() expressions for leaderboard updates prevent read-modify-write races

        Returns:
            LoudSubmission: The created submission

        Raises:
            ValidationError: If validation fails or duplicate submission
        """
        logger.info(
            "LOUD submit started",
            extra={
                'user_id': str(self.user.id),
                'project_id': str(project.id),
                'project_slug': project.slug,
                'x_link': x_link[:100],  # Truncate for safety
            }
        )

        # LOCK USER ROW FIRST - critical for preventing daily limit race conditions
        # This ensures eligibility check happens on locked data
        locked_user = User.objects.select_for_update().get(pk=self.user.pk)

        # Validate eligibility with locked user
        # Re-check limits using the locked user context
        can, reason = self._can_submit_locked(project, locked_user)
        if not can:
            logger.warning(
                "LOUD submit rejected: eligibility check failed",
                extra={
                    'user_id': str(self.user.id),
                    'project_id': str(project.id),
                    'reason': reason,
                }
            )
            raise ValidationError(reason)

        # Validate and normalize URL
        normalized_url, tweet_id, x_username = validate_and_normalize_x_link(x_link)

        # Calculate points using locked user data
        score = locked_user.tweetscout_score or 0
        points = calculate_loud_points(score)

        try:
            # Create submission (unique constraint on tweet_id handles race)
            submission = LoudSubmission.objects.create(
                user=locked_user,
                project=project,
                x_link=normalized_url,
                tweet_id=tweet_id,
                x_username=x_username,
                points_awarded=points,
                tweetscout_score_at_submission=score,
            )
        except IntegrityError:
            # Duplicate tweet_id - another user submitted this link
            logger.warning(
                "LOUD submit rejected: duplicate tweet_id",
                extra={
                    'user_id': str(self.user.id),
                    'project_id': str(project.id),
                    'tweet_id': tweet_id,
                }
            )
            raise ValidationError("This post has already been submitted")

        # Update leaderboard atomically
        self._update_leaderboard_atomic(project, points)

        # Invalidate leaderboard cache
        self._invalidate_leaderboard_cache(project.slug)

        logger.info(
            "LOUD submit success",
            extra={
                'user_id': str(self.user.id),
                'project_id': str(project.id),
                'submission_id': str(submission.id),
                'tweet_id': tweet_id,
                'points_awarded': points,
                'tweetscout_score': float(score),
            }
        )

        return submission

    def _can_submit_locked(self, project: LoudProject, locked_user: User) -> tuple[bool, str]:
        """
        Check if user can submit to a project (with user row locked).

        This is called INSIDE the atomic transaction after locking the user,
        preventing race conditions on daily limit checks.

        Returns:
            tuple: (can_submit, error_message)
        """
        # Check 0: X account linked
        if not locked_user.x_username:
            return False, "Link your X account to submit"

        # Check 1: TweetScout minimum for this project
        score = locked_user.tweetscout_score or 0
        if score < project.min_tweetscout_score:
            return False, f"Requires TweetScout score of {project.min_tweetscout_score}+"

        # Check 2: Global daily limit (checked with locked user)
        today_count = LoudSubmission.objects.filter(
            user=locked_user,
            submitted_at__date=timezone.now().date()
        ).count()

        daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)
        if today_count >= daily_limit:
            return False, f"Daily limit reached ({daily_limit} posts)"

        # Check 3: Per-project limit
        project_count = LoudSubmission.objects.filter(
            user=locked_user,
            project=project
        ).count()

        if project_count >= project.max_submissions_per_user:
            return False, f"Project limit reached ({project.max_submissions_per_user} posts)"

        return True, ""

    def _update_leaderboard_atomic(self, project: LoudProject, points: int):
        """
        Update user's leaderboard entry atomically using F() expressions.
        No read-modify-write = no race conditions.
        """
        # Try to update existing entry
        updated = LoudLeaderboardEntry.objects.filter(
            project=project,
            user=self.user,
        ).update(
            total_points=F('total_points') + points,
            submission_count=F('submission_count') + 1,
            last_submission_at=timezone.now(),
        )

        if updated:
            logger.debug(
                "Leaderboard entry updated",
                extra={
                    'user_id': str(self.user.id),
                    'project_id': str(project.id),
                    'points_added': points,
                }
            )
        else:
            # First submission - create entry
            try:
                LoudLeaderboardEntry.objects.create(
                    project=project,
                    user=self.user,
                    total_points=points,
                    submission_count=1,
                    last_submission_at=timezone.now(),
                )
                logger.info(
                    "Leaderboard entry created (first submission)",
                    extra={
                        'user_id': str(self.user.id),
                        'project_id': str(project.id),
                        'initial_points': points,
                    }
                )
            except IntegrityError:
                # Race: another request created it, retry update
                logger.warning(
                    "Leaderboard race condition: retrying update after create conflict",
                    extra={
                        'user_id': str(self.user.id),
                        'project_id': str(project.id),
                    }
                )
                LoudLeaderboardEntry.objects.filter(
                    project=project,
                    user=self.user,
                ).update(
                    total_points=F('total_points') + points,
                    submission_count=F('submission_count') + 1,
                    last_submission_at=timezone.now(),
                )

    def _invalidate_leaderboard_cache(self, project_slug: str):
        """Invalidate cached leaderboard for a project."""
        cache.delete(f"loud:leaderboard:{project_slug}")

    def get_leaderboard(
        self,
        project: LoudProject,
        limit: int = 50,
        use_cache: bool = True
    ) -> list[dict]:
        """
        Get project leaderboard with optional caching.

        Returns list of dicts with rank, user info, points, and submission count.
        """
        cache_key = f"loud:leaderboard:{project.slug}"

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        entries = LoudLeaderboardEntry.objects.filter(
            project=project
        ).select_related('user', 'user__x_profile').order_by('-total_points')[:limit]

        result = []
        for i, entry in enumerate(entries, 1):
            avatar_url = None
            if hasattr(entry.user, 'x_profile') and entry.user.x_profile:
                avatar_url = entry.user.x_profile.avatar_url

            result.append({
                'rank': i,
                'user': {
                    'id': str(entry.user.id),
                    'display_name': entry.user.display_name,
                    'x_username': entry.user.x_username,
                    'avatar': avatar_url,
                },
                'total_points': entry.total_points,
                'submission_count': entry.submission_count,
            })

        if use_cache:
            cache.set(cache_key, result, 60)  # 60 second TTL

        return result

    def get_user_rank(self, project: LoudProject) -> Optional[int]:
        """Get user's rank in project leaderboard."""
        try:
            entry = LoudLeaderboardEntry.objects.get(project=project, user=self.user)
            # Count users with more points
            rank = LoudLeaderboardEntry.objects.filter(
                project=project,
                total_points__gt=entry.total_points
            ).count() + 1
            return rank
        except LoudLeaderboardEntry.DoesNotExist:
            return None

    def get_user_entry(self, project: LoudProject) -> Optional[dict]:
        """Get user's leaderboard entry for a project."""
        try:
            entry = LoudLeaderboardEntry.objects.get(project=project, user=self.user)
            rank = self.get_user_rank(project)
            return {
                'user_id': str(self.user.id),
                'rank': rank,
                'total_points': entry.total_points,
                'submission_count': entry.submission_count,
            }
        except LoudLeaderboardEntry.DoesNotExist:
            return None

    def get_project_stats(self, project: LoudProject) -> dict:
        """Get statistics for a project."""
        total_participants = LoudLeaderboardEntry.objects.filter(project=project).count()
        total_submissions = LoudSubmission.objects.filter(project=project).count()

        return {
            'total_participants': total_participants,
            'total_submissions': total_submissions,
        }
