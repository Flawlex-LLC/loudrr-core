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
from posts.models import Post, Engagement


class PostService:
    """Service for managing posts."""

    def __init__(self, user: User):
        self.user = user
        self.config = settings.ECHO_CONFIG

    def can_post(self) -> bool:
        """Check if user can create a new post."""
        return self.user.credits >= self.config["POST_COST"]

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
        post_cost = self.config["POST_COST"]

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

        # Update user stats
        self.user.total_posts += 1
        self.user.save(update_fields=["total_posts"])

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


def get_feed_posts(
    user: User,
    limit: int = 1,
    exclude_engaged: bool = True,
) -> List[Post]:
    """
    Get posts available for a user to engage with.

    Posts are returned in FIFO order (oldest first) to ensure
    fair distribution of engagements.

    Args:
        user: User requesting the feed
        limit: Maximum number of posts to return
        exclude_engaged: Whether to exclude posts user already engaged with

    Returns:
        List of Post instances
    """
    queryset = Post.objects.filter(
        status=Post.Status.ACTIVE,
    ).exclude(
        user=user,  # Can't engage with own posts
    ).order_by("created_at")  # FIFO - oldest first

    if exclude_engaged:
        # Exclude posts this user has already engaged with
        engaged_post_ids = Engagement.objects.filter(
            user=user,
        ).values_list("post_id", flat=True)
        queryset = queryset.exclude(id__in=engaged_post_ids)

    return list(queryset[:limit])


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
