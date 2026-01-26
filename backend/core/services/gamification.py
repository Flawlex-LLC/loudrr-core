"""
Gamification service.

Handles streaks, tiers, leaderboards, and achievements.
"""
from datetime import timedelta
from typing import List, Dict, Any

from django.db.models import Sum, Count
from django.utils import timezone

from core.models import User, Transaction


def get_user_stats(user: User) -> Dict[str, Any]:
    """
    Get comprehensive stats for a user.

    Returns:
        Dict with credits, engagements, streak, tier info
    """
    return {
        "credits": user.credits,
        "total_earned": user.total_credits_earned,
        "total_spent": user.total_credits_spent,
        "total_engagements": user.total_engagements,
        "total_posts": user.total_posts,
        "current_streak": user.current_streak,
        "longest_streak": user.longest_streak,
        "tier": user.tier,
        "tier_multiplier": user.tier_multiplier,
        "streak_multiplier": user.get_streak_multiplier(),
        "combined_multiplier": user.tier_multiplier * user.get_streak_multiplier(),
        "rank": get_user_rank(user),
    }


def get_user_rank(user: User) -> int:
    """
    Get user's rank based on total engagements.

    Returns:
        1-indexed rank (1 = first place)
    """
    return User.objects.filter(
        total_engagements__gt=user.total_engagements,
        is_banned=False,
    ).count() + 1


def get_leaderboard(
    period: str = "all_time",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Get leaderboard for specified period.

    Args:
        period: "daily", "weekly", or "all_time"
        limit: Number of entries to return

    Returns:
        List of user stats with rankings
    """
    now = timezone.now()

    if period == "daily":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Get today's engagements from transactions
        leaders = (
            Transaction.objects
            .filter(
                type=Transaction.Type.EARNED,
                created_at__gte=start_date,
            )
            .values("user")
            .annotate(
                engagement_count=Count("id"),
                credits_earned=Sum("amount"),
            )
            .order_by("-engagement_count")[:limit]
        )
    elif period == "weekly":
        start_date = now - timedelta(days=7)
        leaders = (
            Transaction.objects
            .filter(
                type=Transaction.Type.EARNED,
                created_at__gte=start_date,
            )
            .values("user")
            .annotate(
                engagement_count=Count("id"),
                credits_earned=Sum("amount"),
            )
            .order_by("-engagement_count")[:limit]
        )
    else:  # all_time
        leaders = (
            User.objects
            .filter(is_banned=False)
            .order_by("-total_engagements")
            .values("id", "display_name", "total_engagements", "tier", "current_streak")[:limit]
        )
        return [
            {
                "rank": i + 1,
                "user_id": str(entry["id"]),
                "display_name": entry["display_name"] or "Anonymous",
                "engagements": entry["total_engagements"],
                "tier": entry["tier"],
                "streak": entry["current_streak"],
            }
            for i, entry in enumerate(leaders)
        ]

    # For daily/weekly, we need to fetch user details separately
    result = []
    for i, entry in enumerate(leaders):
        try:
            user = User.objects.get(pk=entry["user"])
            result.append({
                "rank": i + 1,
                "user_id": str(user.id),
                "display_name": user.display_name or "Anonymous",
                "engagements": entry["engagement_count"],
                "credits_earned": entry["credits_earned"],
                "tier": user.tier,
                "streak": user.current_streak,
            })
        except User.DoesNotExist:
            continue

    return result


def get_rising_stars(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get users with biggest improvement this week vs last week.

    Returns:
        List of users sorted by week-over-week improvement
    """
    now = timezone.now()
    this_week_start = now - timedelta(days=7)
    last_week_start = now - timedelta(days=14)

    # This week's engagements
    this_week = dict(
        Transaction.objects
        .filter(
            type=Transaction.Type.EARNED,
            created_at__gte=this_week_start,
        )
        .values("user")
        .annotate(count=Count("id"))
        .values_list("user", "count")
    )

    # Last week's engagements
    last_week = dict(
        Transaction.objects
        .filter(
            type=Transaction.Type.EARNED,
            created_at__gte=last_week_start,
            created_at__lt=this_week_start,
        )
        .values("user")
        .annotate(count=Count("id"))
        .values_list("user", "count")
    )

    # Calculate improvement
    improvements = []
    for user_id, this_count in this_week.items():
        last_count = last_week.get(user_id, 0)
        if last_count > 0:
            improvement = ((this_count - last_count) / last_count) * 100
        else:
            improvement = 100 if this_count > 0 else 0

        improvements.append({
            "user_id": user_id,
            "this_week": this_count,
            "last_week": last_count,
            "improvement": improvement,
        })

    # Sort by improvement percentage
    improvements.sort(key=lambda x: x["improvement"], reverse=True)

    # Fetch user details
    result = []
    for i, entry in enumerate(improvements[:limit]):
        try:
            user = User.objects.get(pk=entry["user_id"])
            result.append({
                "rank": i + 1,
                "user_id": str(user.id),
                "display_name": user.display_name or "Anonymous",
                "this_week": entry["this_week"],
                "last_week": entry["last_week"],
                "improvement": round(entry["improvement"], 1),
            })
        except User.DoesNotExist:
            continue

    return result


def check_and_award_badges(user: User) -> List[str]:
    """
    Check if user has earned any new badges.

    Returns:
        List of newly awarded badge names
    """
    # TODO: Implement badge system
    # For now, return empty list
    return []
