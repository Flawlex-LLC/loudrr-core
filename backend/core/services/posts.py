"""
Post service.

Handles creating posts, managing escrow, and post lifecycle.
"""
from typing import Optional, List
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from core.models import User
from core.services.credits import CreditService, InsufficientCreditsError
from core.services.settings import get_setting
from posts.models import Post, Engagement


class PostService:
    """Service for managing posts."""

    def __init__(self, user: User):
        self.user = user

    def can_post(self) -> bool:
        """Check if user can create a new post."""
        post_cost = get_setting('POST_COST')
        return self.user.credits >= post_cost

    @transaction.atomic
    def create_post(
        self,
        x_link: str,
        platform: str,
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
    ) -> Post:
        """
        Create a new post with credits locked in escrow.

        Args:
            x_link: The X/Twitter link to the post
            platform: Platform where post was submitted ("telegram", "discord", "web")
            channel_id: Platform channel/chat ID
            message_id: Bot message ID for updates

        Returns:
            Created Post instance

        Raises:
            InsufficientCreditsError: If user doesn't have enough credits
        """
        post_cost = get_setting('POST_COST')

        # Deduct credits
        credit_service = CreditService(self.user)
        credit_service.spend(
            amount=post_cost,
            reference_type="post",
            description=f"Created new post",
        )

        # Create post
        post = Post.objects.create(
            user=self.user,
            x_link=x_link,
            platform=platform,
            channel_id=channel_id,
            message_id=message_id,
            escrow=post_cost,
            initial_escrow=post_cost,
        )

        # Update transaction with post reference
        from core.models import Transaction
        Transaction.objects.filter(
            user=self.user,
            type=Transaction.Type.SPENT,
            reference_type="post",
            reference_id__isnull=True,
        ).order_by("-created_at").update(reference_id=post.id)

        # Update user stats atomically (avoid race condition)
        from django.db.models import F
        User.objects.filter(pk=self.user.pk).update(
            total_posts=F('total_posts') + 1
        )
        self.user.refresh_from_db()

        return post

    def get_user_posts(
        self,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Post]:
        """
        Get posts created by this user.

        Args:
            status: Filter by status (active, completed, cancelled)
            limit: Maximum number of posts to return

        Returns:
            List of Post instances
        """
        queryset = Post.objects.filter(user=self.user)
        if status:
            queryset = queryset.filter(status=status)
        return list(queryset[:limit])

    def cancel_post(self, post: Post, refund: bool = True) -> bool:
        """
        Cancel a post and optionally refund remaining escrow.

        Args:
            post: Post to cancel
            refund: Whether to refund remaining credits

        Returns:
            True if cancelled, False if not allowed
        """
        if post.user_id != self.user.id:
            return False
        if post.status != Post.Status.ACTIVE:
            return False

        post.cancel(refund=refund)
        return True


def calculate_feed_score(post: Post, viewer: User) -> float:
    """
    Calculate feed score for a post (v1).

    Formula:
        feed_score = (author_score × 0.5) + (freshness × 0.3) + (engagement_remaining × 0.2)

    Author score is based on TweetScout score (normalized to 0.2-1.0).

    Args:
        post: The post to score
        viewer: The user viewing the feed

    Returns:
        Score between 0 and 1
    """
    from django.utils import timezone

    # Get author score from TweetScout (0.2-1.0 normalized)
    tweetscout = post.user.tweetscout_score if post.user else 0
    if tweetscout >= 1000:
        author_score = 1.0  # GOAT
    elif tweetscout >= 800:
        author_score = 0.9  # OG
    elif tweetscout >= 600:
        author_score = 0.8  # Legend
    elif tweetscout >= 400:
        author_score = 0.65  # Based
    elif tweetscout >= 200:
        author_score = 0.5  # Degen
    elif tweetscout >= 100:
        author_score = 0.35  # Normie
    else:
        author_score = 0.2  # Anon

    # Freshness: newer = higher score (0-1)
    # Decay over 7 days (168 hours)
    hours_old = (timezone.now() - post.created_at).total_seconds() / 3600
    freshness_score = max(0.0, 1.0 - (hours_old / 168))

    # Engagement remaining: more remaining = higher score (0-1)
    # Convert Decimal to float to avoid type errors
    initial = float(post.initial_escrow or 1)
    engagement_score = float(post.escrow) / initial if initial > 0 else 0.0

    # Weighted sum (all floats now)
    score = (author_score * 0.5) + (freshness_score * 0.3) + (engagement_score * 0.2)

    return min(score, 1.0)


def get_feed_posts(
    user: User,
    limit: int = 1,
    exclude_engaged: bool = True,
    exclude_post_ids: Optional[List] = None,
    use_scoring: bool = True,
) -> List[Post]:
    """
    Get posts available for a user to engage with.

    v1: Uses tier-weighted scoring algorithm instead of FIFO.
    Posts are ranked by: (author_tier × 0.5) + (freshness × 0.3) + (engagement_remaining × 0.2)

    Args:
        user: User requesting the feed
        limit: Maximum number of posts to return
        exclude_engaged: Whether to exclude posts user already engaged with
        exclude_post_ids: Additional post IDs to exclude (e.g., pending engagements)
        use_scoring: Whether to use scoring algorithm (v1) or FIFO (legacy)

    Returns:
        List of Post instances
    """
    queryset = Post.objects.filter(
        status=Post.Status.ACTIVE,
        escrow__gt=0,  # Only posts with remaining escrow
    ).exclude(
        user=user,  # Can't engage with own posts
    ).select_related("user", "user__x_profile")  # Prefetch user + X profile for response

    if exclude_engaged:
        # Exclude posts this user has already engaged with
        engaged_post_ids = Engagement.objects.filter(
            user=user,
        ).values_list("post_id", flat=True)
        queryset = queryset.exclude(id__in=engaged_post_ids)

    # Exclude additional specific post IDs (e.g., pending unverified engagements)
    if exclude_post_ids:
        queryset = queryset.exclude(id__in=exclude_post_ids)

    posts = list(queryset)

    if not use_scoring:
        # Legacy FIFO ordering
        posts.sort(key=lambda p: p.created_at)
        return posts[:limit]

    # v1: Score and sort posts
    scored_posts = [(post, calculate_feed_score(post, user)) for post in posts]
    scored_posts.sort(key=lambda x: x[1], reverse=True)  # Highest score first

    return [p[0] for p in scored_posts[:limit]]


def get_feed_count(user: User) -> int:
    """
    Get count of posts available for engagement.

    Args:
        user: User to check feed for

    Returns:
        Number of available posts
    """
    engaged_post_ids = Engagement.objects.filter(
        user=user,
    ).values_list("post_id", flat=True)

    return Post.objects.filter(
        status=Post.Status.ACTIVE,
    ).exclude(
        user=user,
    ).exclude(
        id__in=engaged_post_ids,
    ).count()
