from rest_framework import serializers

from posts.models import Post, Engagement, SponsoredPost


class PostSerializer(serializers.ModelSerializer):
    """Serializer for posts."""

    engagement_count = serializers.ReadOnlyField()
    engagement_progress = serializers.ReadOnlyField()
    user_display_name = serializers.CharField(source="user.display_name", read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "user",
            "user_display_name",
            "x_link",
            "escrow",
            "initial_escrow",
            "engagement_count",
            "engagement_progress",
            "status",
            "platform",
            "created_at",
            "completed_at",
        ]
        read_only_fields = [
            "id", "user", "escrow", "initial_escrow",
            "status", "created_at", "completed_at",
        ]


class PostCreateSerializer(serializers.Serializer):
    """Serializer for creating a post."""

    x_link = serializers.URLField(max_length=500)
    platform = serializers.ChoiceField(choices=["telegram", "discord", "web"])
    channel_id = serializers.IntegerField(required=False, allow_null=True)
    message_id = serializers.IntegerField(required=False, allow_null=True)


class FeedPostSerializer(serializers.ModelSerializer):
    """Serializer for posts in the feed (for engagement)."""

    redirect_url = serializers.SerializerMethodField()
    user_display_name = serializers.CharField(source="user.display_name", read_only=True)
    x_username = serializers.CharField(source="user.x_username", read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "user_display_name",
            "x_username",
            "x_link",
            "redirect_url",
            "escrow",
            "initial_escrow",
            "created_at",
        ]

    def get_redirect_url(self, obj):
        """Get personalized redirect URL for the requesting user."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.get_redirect_url_for_user(request.user)
        return None


class EngagementSerializer(serializers.ModelSerializer):
    """Serializer for engagements."""

    post_x_link = serializers.CharField(source="post.x_link", read_only=True)

    class Meta:
        model = Engagement
        fields = [
            "id",
            "post",
            "post_x_link",
            "clicked_at",
            "credit_granted",
            "created_at",
        ]
        read_only_fields = fields


class SponsoredPostSerializer(serializers.ModelSerializer):
    """Serializer for sponsored posts."""

    post = PostSerializer(read_only=True)

    class Meta:
        model = SponsoredPost
        fields = [
            "id",
            "post",
            "sponsor_name",
            "credit_reward",
            "total_budget",
            "remaining_budget",
            "created_at",
        ]
        read_only_fields = fields
