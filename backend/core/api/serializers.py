from rest_framework import serializers

from core.models import User, Transaction, AuditLog


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profile."""

    tier_multiplier = serializers.SerializerMethodField()
    streak_multiplier = serializers.SerializerMethodField()
    combined_multiplier = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "telegram_id",
            "discord_id",
            "x_username",
            "display_name",
            "credits",
            "total_credits_earned",
            "total_credits_spent",
            "total_engagements",
            "total_posts",
            "current_streak",
            "longest_streak",
            "tier",
            "tier_multiplier",
            "streak_multiplier",
            "combined_multiplier",
            "created_at",
        ]
        read_only_fields = fields

    def get_tier_multiplier(self, obj):
        return obj.get_tier_multiplier()

    def get_streak_multiplier(self, obj):
        return obj.get_streak_multiplier()

    def get_combined_multiplier(self, obj):
        return obj.get_tier_multiplier() * obj.get_streak_multiplier()


class BalanceSerializer(serializers.Serializer):
    """Serializer for balance response."""

    credits = serializers.IntegerField()
    daily_earned = serializers.IntegerField()
    daily_remaining = serializers.IntegerField()
    weekly_purchased = serializers.IntegerField()
    weekly_purchase_remaining = serializers.IntegerField()


class UserStatsSerializer(serializers.Serializer):
    """Serializer for user stats."""

    credits = serializers.IntegerField()
    total_earned = serializers.IntegerField()
    total_spent = serializers.IntegerField()
    total_engagements = serializers.IntegerField()
    total_posts = serializers.IntegerField()
    current_streak = serializers.IntegerField()
    longest_streak = serializers.IntegerField()
    tier = serializers.CharField()
    tier_multiplier = serializers.FloatField()
    streak_multiplier = serializers.FloatField()
    combined_multiplier = serializers.FloatField()
    rank = serializers.IntegerField()


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for transactions."""

    class Meta:
        model = Transaction
        fields = [
            "id",
            "type",
            "amount",
            "balance_after",
            "reference_id",
            "reference_type",
            "description",
            "created_at",
        ]
        read_only_fields = fields


class LeaderboardEntrySerializer(serializers.Serializer):
    """Serializer for leaderboard entries."""

    rank = serializers.IntegerField()
    user_id = serializers.CharField()
    display_name = serializers.CharField()
    engagements = serializers.IntegerField()
    tier = serializers.CharField()
    streak = serializers.IntegerField()
    credits_earned = serializers.IntegerField(required=False)
    improvement = serializers.FloatField(required=False)


class LinkAccountSerializer(serializers.Serializer):
    """Serializer for linking platform accounts."""

    platform = serializers.ChoiceField(choices=["telegram", "discord"])
    platform_id = serializers.IntegerField()
    display_name = serializers.CharField(max_length=100, required=False)
