from django.contrib import admin

from .models import Post, Engagement, SponsoredPost


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        "id", "user", "status", "escrow", "engagement_count",
        "platform", "created_at", "completed_at",
    ]
    list_filter = ["status", "platform"]
    search_fields = ["user__display_name", "x_link"]
    ordering = ["-created_at"]
    readonly_fields = [
        "id", "redirect_token", "initial_escrow",
        "created_at", "updated_at", "completed_at",
    ]

    def engagement_count(self, obj):
        return obj.engagement_count
    engagement_count.short_description = "Engagements"


@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "post", "credit_granted", "clicked_at", "created_at"]
    list_filter = ["credit_granted"]
    search_fields = ["user__display_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "user", "post", "clicked_at", "created_at"]


@admin.register(SponsoredPost)
class SponsoredPostAdmin(admin.ModelAdmin):
    list_display = [
        "id", "post", "sponsor_name", "credit_reward",
        "remaining_budget", "total_budget", "created_at",
    ]
    search_fields = ["sponsor_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
