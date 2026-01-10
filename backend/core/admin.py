from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User, Transaction, AuditLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "id", "display_name", "telegram_id", "discord_id",
        "credits", "tier", "current_streak", "is_banned", "created_at",
    ]
    list_filter = ["tier", "is_banned", "is_staff"]
    search_fields = ["display_name", "telegram_id", "discord_id", "x_username"]
    ordering = ["-created_at"]

    fieldsets = (
        (None, {"fields": ("display_name", "x_username")}),
        ("Platform IDs", {"fields": ("telegram_id", "discord_id")}),
        ("Credits", {"fields": (
            "credits", "total_credits_earned", "total_credits_spent",
            "daily_credits_earned", "weekly_credits_purchased",
        )}),
        ("Engagement", {"fields": (
            "total_engagements", "total_posts",
            "current_streak", "longest_streak", "last_engagement_date",
        )}),
        ("Status", {"fields": ("tier", "is_active", "is_banned", "ban_reason")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser")}),
    )

    readonly_fields = [
        "id", "total_credits_earned", "total_credits_spent",
        "total_engagements", "total_posts", "created_at", "updated_at",
    ]

    # Don't require password
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("telegram_id", "discord_id", "display_name"),
        }),
    )


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "type", "amount", "balance_after", "created_at"]
    list_filter = ["type"]
    search_fields = ["user__display_name", "user__telegram_id"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "user", "type", "amount", "balance_after", "reference_id", "created_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "result", "penalty_applied", "created_at"]
    list_filter = ["result"]
    search_fields = ["user__display_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "user", "engagement_id", "post_id", "created_at"]
