from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services.credits import InsufficientCreditsError
from core.services.posts import PostService, get_feed_posts, get_feed_count
from core.services.engagements import get_cooldown_remaining
from posts.models import Post, Engagement
from .serializers import (
    PostSerializer,
    PostCreateSerializer,
    FeedPostSerializer,
    EngagementSerializer,
)


class PostListCreateView(APIView):
    """List user's posts or create a new post."""

    def get(self, request):
        """Get current user's posts."""
        status_filter = request.query_params.get("status")
        post_service = PostService(request.user)
        posts = post_service.get_user_posts(status=status_filter)
        serializer = PostSerializer(posts, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new post (costs 40 credits)."""
        serializer = PostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post_service = PostService(request.user)

        if not post_service.can_post():
            return Response(
                {"error": "Insufficient credits", "required": 40, "current": request.user.credits},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            post = post_service.create_post(
                x_link=serializer.validated_data["x_link"],
                platform=serializer.validated_data["platform"],
                channel_id=serializer.validated_data.get("channel_id"),
                message_id=serializer.validated_data.get("message_id"),
            )
        except InsufficientCreditsError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PostSerializer(post).data, status=status.HTTP_201_CREATED)


class PostDetailView(APIView):
    """Get or cancel a specific post."""

    def get(self, request, pk):
        """Get post details."""
        try:
            post = Post.objects.get(pk=pk)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = PostSerializer(post)
        return Response(serializer.data)

    def delete(self, request, pk):
        """Cancel a post and refund remaining escrow."""
        try:
            post = Post.objects.get(pk=pk)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        if post.user_id != request.user.id:
            return Response({"error": "Not your post"}, status=status.HTTP_403_FORBIDDEN)

        if post.status != Post.Status.ACTIVE:
            return Response({"error": "Post is not active"}, status=status.HTTP_400_BAD_REQUEST)

        post.cancel(refund=True)
        return Response({"message": f"Post cancelled. Refunded {post.escrow} credits."})


class FeedView(APIView):
    """Get posts available for engagement."""

    def get(self, request):
        """
        Get next post(s) to engage with.

        Query params:
            limit: Number of posts (default 1, max 10)
        """
        limit = min(int(request.query_params.get("limit", 1)), 10)
        posts = get_feed_posts(request.user, limit=limit)
        total_available = get_feed_count(request.user)
        cooldown_remaining = get_cooldown_remaining(request.user)

        serializer = FeedPostSerializer(posts, many=True, context={"request": request})
        return Response({
            "posts": serializer.data,
            "total_available": total_available,
            "cooldown_remaining": cooldown_remaining,
            "user_credits": request.user.credits,
            "daily_earned": request.user.daily_credits_earned,
        })


class UserEngagementsView(APIView):
    """Get user's engagement history."""

    def get(self, request):
        """Get paginated engagement history."""
        engagements = Engagement.objects.filter(user=request.user).select_related("post")[:50]
        serializer = EngagementSerializer(engagements, many=True)
        return Response(serializer.data)


class PostEngagementsView(APIView):
    """Get engagements for a specific post."""

    def get(self, request, pk):
        """Get all engagements on a post (owner only)."""
        try:
            post = Post.objects.get(pk=pk)
        except Post.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        if post.user_id != request.user.id:
            return Response({"error": "Not your post"}, status=status.HTTP_403_FORBIDDEN)

        engagements = Engagement.objects.filter(post=post).select_related("user")
        data = [
            {
                "id": str(e.id),
                "user_display_name": e.user.display_name or "Anonymous",
                "clicked_at": e.clicked_at,
                "credit_granted": e.credit_granted,
            }
            for e in engagements
        ]
        return Response(data)
