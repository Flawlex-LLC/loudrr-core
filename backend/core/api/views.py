from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User, Transaction
from core.services.credits import CreditService
from core.services.gamification import get_user_stats, get_leaderboard, get_rising_stars
from .serializers import (
    UserSerializer,
    BalanceSerializer,
    UserStatsSerializer,
    TransactionSerializer,
    LeaderboardEntrySerializer,
    LinkAccountSerializer,
)


class CurrentUserView(APIView):
    """Get or update current user profile."""

    def get(self, request):
        """Get current user's profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """Update user profile (x_username, display_name)."""
        user = request.user
        allowed_fields = ["x_username", "display_name"]

        for field in allowed_fields:
            if field in request.data:
                setattr(user, field, request.data[field])

        user.save(update_fields=[f for f in allowed_fields if f in request.data] + ["updated_at"])
        serializer = UserSerializer(user)
        return Response(serializer.data)


class BalanceView(APIView):
    """Get user's credit balance and limits."""

    def get(self, request):
        """Get current balance and daily/weekly limits."""
        user = request.user
        credit_service = CreditService(user)

        data = {
            "credits": user.credits,
            "daily_earned": user.daily_credits_earned,
            "daily_remaining": credit_service.get_daily_remaining(),
            "weekly_purchased": user.weekly_credits_purchased,
            "weekly_purchase_remaining": credit_service.get_weekly_purchase_remaining(),
        }
        serializer = BalanceSerializer(data)
        return Response(serializer.data)


class UserStatsView(APIView):
    """Get user's comprehensive stats."""

    def get(self, request):
        """Get engagement stats, streaks, tier info."""
        stats = get_user_stats(request.user)
        serializer = UserStatsSerializer(stats)
        return Response(serializer.data)


class TransactionHistoryView(APIView):
    """Get user's transaction history."""

    def get(self, request):
        """Get paginated transaction history."""
        transactions = Transaction.objects.filter(user=request.user)[:50]
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)


class LeaderboardView(APIView):
    """Get leaderboard data."""
    permission_classes = [AllowAny]

    def get(self, request):
        """Get leaderboard for specified period."""
        period = request.query_params.get("period", "all_time")
        leaderboard_type = request.query_params.get("type", "standard")
        limit = min(int(request.query_params.get("limit", 10)), 50)

        if leaderboard_type == "rising_stars":
            data = get_rising_stars(limit=limit)
        else:
            data = get_leaderboard(period=period, limit=limit)

        serializer = LeaderboardEntrySerializer(data, many=True)
        return Response({
            "period": period,
            "type": leaderboard_type,
            "entries": serializer.data,
        })


class LinkAccountView(APIView):
    """Link another platform account to current user."""

    def post(self, request):
        """Link a Telegram or Discord account."""
        serializer = LinkAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        platform = serializer.validated_data["platform"]
        platform_id = serializer.validated_data["platform_id"]
        display_name = serializer.validated_data.get("display_name")

        user = request.user
        field = f"{platform}_id"
        existing = User.objects.filter(**{field: platform_id}).exclude(pk=user.pk).first()
        if existing:
            return Response(
                {"error": f"This {platform} account is already linked to another user"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        setattr(user, field, platform_id)
        if display_name:
            user.display_name = display_name
        user.save()

        return Response(UserSerializer(user).data)


class CreateUserView(APIView):
    """Create a new user from bot authentication."""
    permission_classes = [AllowAny]

    def post(self, request):
        """Create or get user by platform ID."""
        platform = request.data.get("platform")
        platform_id = request.data.get("platform_id")
        display_name = request.data.get("display_name", "")

        if not platform or not platform_id:
            return Response(
                {"error": "platform and platform_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if platform not in ["telegram", "discord"]:
            return Response(
                {"error": "platform must be 'telegram' or 'discord'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        field = f"{platform}_id"

        try:
            user = User.objects.get(**{field: platform_id})
            created = False
        except User.DoesNotExist:
            user = User.objects.create(**{
                field: platform_id,
                "display_name": display_name,
            })
            created = True

        return Response({
            "user": UserSerializer(user).data,
            "created": created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
