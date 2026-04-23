"""
URL configuration for ECHO project.
"""
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.urls import include, path
from django.utils.html import format_html
from django.http import JsonResponse
from django.db import connection
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .admin_site import loudrr_admin


# Health check endpoint for Docker/Kubernetes
def health_check(request):
    """Health check endpoint for load balancers and container orchestration."""
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({
            "status": "healthy",
            "database": "connected",
        })
    except Exception as e:
        return JsonResponse({
            "status": "unhealthy",
            "error": str(e),
        }, status=503)


# === Admin Actions Log (Django's built-in) ===
# Tracks admin panel actions only (add, change, delete via admin UI)
class LogEntryAdmin(admin.ModelAdmin):
    """Admin panel action history - who did what in the admin."""
    list_display = [
        "action_time", "user_link", "content_type", "object_link",
        "action_flag_display", "change_message_display",
    ]
    list_filter = ["action_flag", "content_type", "user"]
    search_fields = ["object_repr", "change_message", "user__display_name"]
    ordering = ["-action_time"]
    readonly_fields = [
        "action_time", "user", "content_type", "object_id", "object_repr",
        "action_flag", "change_message",
    ]
    date_hierarchy = "action_time"
    list_per_page = 50
    list_select_related = ["user", "content_type"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def user_link(self, obj):
        if obj.user:
            return format_html(
                '<a href="/loudrr-admin/core/user/{}/change/">{}</a>',
                obj.user.pk, obj.user.display_name or obj.user
            )
        return "-"
    user_link.short_description = "Admin"

    def object_link(self, obj):
        if obj.content_type and obj.object_id:
            try:
                url = f"/loudrr-admin/{obj.content_type.app_label}/{obj.content_type.model}/{obj.object_id}/change/"
                return format_html('<a href="{}">{}</a>', url, obj.object_repr[:50])
            except Exception:
                pass
        return obj.object_repr[:50] if obj.object_repr else "-"
    object_link.short_description = "Object"

    def action_flag_display(self, obj):
        colors = {1: ("#27ae60", "ADD"), 2: ("#3498db", "CHANGE"), 3: ("#e74c3c", "DELETE")}
        color, label = colors.get(obj.action_flag, ("#95a5a6", "UNKNOWN"))
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, label)
    action_flag_display.short_description = "Action"

    def change_message_display(self, obj):
        msg = obj.change_message or ""
        return (msg[:80] + "...") if len(msg) > 80 else (msg or "-")
    change_message_display.short_description = "Details"


# Only register if not already registered
if not loudrr_admin.is_registered(LogEntry):
    loudrr_admin.register(LogEntry, LogEntryAdmin)


# === Change History (django-auditlog) ===
# Tracks ALL model changes from any source (admin, API, bot, etc.)
from auditlog.models import LogEntry as AuditLogEntry


class AuditLogEntryAdmin(admin.ModelAdmin):
    """
    Full audit trail - tracks ALL model changes (admin, API, bot, etc.)

    This is different from Django's LogEntry which only tracks admin actions.
    This tracks every create/update/delete regardless of source.
    """
    list_display = [
        "timestamp", "actor_link", "action_display", "content_type",
        "object_link", "changes_display",
    ]
    list_filter = ["action", "content_type", "actor"]
    search_fields = ["object_repr", "actor__display_name", "changes"]
    ordering = ["-timestamp"]
    readonly_fields = [
        "timestamp", "actor", "content_type", "object_id", "object_pk",
        "object_repr", "action", "changes", "remote_addr", "additional_data",
    ]
    date_hierarchy = "timestamp"

    list_per_page = 50
    list_select_related = ["actor", "content_type"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def actor_link(self, obj):
        if obj.actor:
            return format_html(
                '<a href="/loudrr-admin/core/user/{}/change/">{}</a>',
                obj.actor.pk, obj.actor.display_name or obj.actor
            )
        return format_html('<span style="color: #888;">System</span>')
    actor_link.short_description = "Changed By"

    def action_display(self, obj):
        """Color-coded action type."""
        colors = {
            0: ("#27ae60", "CREATE"),
            1: ("#3498db", "UPDATE"),
            2: ("#e74c3c", "DELETE"),
            3: ("#9b59b6", "ACCESS"),
        }
        color, label = colors.get(obj.action, ("#95a5a6", "UNKNOWN"))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, label
        )
    action_display.short_description = "Action"
    action_display.admin_order_field = "action"

    def object_link(self, obj):
        """Link to the affected object."""
        if obj.content_type and obj.object_pk:
            try:
                url = f"/loudrr-admin/{obj.content_type.app_label}/{obj.content_type.model}/{obj.object_pk}/change/"
                return format_html('<a href="{}">{}</a>', url, obj.object_repr[:50])
            except Exception:
                pass
        return obj.object_repr[:50] if obj.object_repr else "-"
    object_link.short_description = "Object"

    def changes_display(self, obj):
        """Show field changes summary."""
        if not obj.changes:
            return "-"

        try:
            changes = obj.changes
            if isinstance(changes, str):
                import json
                changes = json.loads(changes)

            # Format as field: old → new
            parts = []
            for field, values in changes.items():
                if isinstance(values, list) and len(values) == 2:
                    old_val = str(values[0])[:20] if values[0] else "∅"
                    new_val = str(values[1])[:20] if values[1] else "∅"
                    parts.append(f"<b>{field}</b>: {old_val} → {new_val}")
                else:
                    parts.append(f"<b>{field}</b>: {values}")

            if len(parts) > 3:
                return format_html("{} <i>(+{} more)</i>", format_html("<br>".join(parts[:3])), len(parts) - 3)
            return format_html("<br>".join(parts))
        except Exception:
            return str(obj.changes)[:100]
    changes_display.short_description = "Changes"


# Only register if not already registered
if not loudrr_admin.is_registered(AuditLogEntry):
    loudrr_admin.register(AuditLogEntry, AuditLogEntryAdmin)


# Register ALL models with default admin.site
# Core models
from core.models import User, Transaction, AuditLog, SiteSetting, XProfile, XPTransaction, WaitlistEntry, FeatureInterest, XVerificationRequest
from core.admin import (
    UserAdmin, TransactionAdmin, AuditLogAdmin,
    SiteSettingAdmin, XProfileAdmin, XPTransactionAdmin, WaitlistEntryAdmin, FeatureInterestAdmin,
    XVerificationRequestAdmin,
)

for model, model_admin in [
    (User, UserAdmin),
    (Transaction, TransactionAdmin),
    (AuditLog, AuditLogAdmin),
    (SiteSetting, SiteSettingAdmin),
    (XProfile, XProfileAdmin),
    (XPTransaction, XPTransactionAdmin),
    (WaitlistEntry, WaitlistEntryAdmin),
    (FeatureInterest, FeatureInterestAdmin),
    (XVerificationRequest, XVerificationRequestAdmin),
]:
    if not admin.site.is_registered(model):
        admin.site.register(model, model_admin)

# Posts models
from posts.models import Post, Engagement, SponsoredPost, Campaign, CampaignEntry
from posts.admin import (
    PostAdmin, EngagementAdmin, SponsoredPostAdmin,
    CampaignAdmin, CampaignEntryAdmin
)

for model, model_admin in [
    (Post, PostAdmin),
    (Engagement, EngagementAdmin),
    (SponsoredPost, SponsoredPostAdmin),
    (Campaign, CampaignAdmin),
    (CampaignEntry, CampaignEntryAdmin),
]:
    if not admin.site.is_registered(model):
        admin.site.register(model, model_admin)

# Loud models
from loud.models import LoudProject, LoudSubmission, LoudLeaderboardEntry
from loud.admin import LoudProjectAdmin, LoudSubmissionAdmin, LoudLeaderboardEntryAdmin

for model, model_admin in [
    (LoudProject, LoudProjectAdmin),
    (LoudSubmission, LoudSubmissionAdmin),
    (LoudLeaderboardEntry, LoudLeaderboardEntryAdmin),
]:
    if not admin.site.is_registered(model):
        admin.site.register(model, model_admin)

# Note: miniapp.EngagementSession and SessionClick models were removed (dead code)
# Engagement tracking is done via posts.Engagement directly


from bots.telegram.views import telegram_webhook
from miniapp.views_x_verification import x_oauth_callback


urlpatterns = [
    # Health check (for Docker/K8s)
    path("health/", health_check, name="health_check"),

    # Admin - all models registered with default admin.site
    path("admin/", admin.site.urls),

    # API Documentation (OpenAPI 3.0)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # API endpoints
    path("api/", include("core.api.urls")),
    path("api/posts/", include("posts.api.urls")),
    path("api/miniapp/", include("miniapp.urls")),
    path("api/loud/", include("loud.urls")),

    # Telegram bot webhook (production mode)
    path("api/telegram/webhook/", telegram_webhook, name="telegram_webhook"),

    # X OAuth callback (X redirects here from external browser)
    path("api/auth/x/callback/", x_oauth_callback, name="x_oauth_callback"),

    # Redirects
    path("r/", include("redirects.urls")),
]
