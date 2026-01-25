from django.contrib import admin
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils.html import format_html

from .models import User, Transaction, AuditLog, SiteSetting, XProfile, XPTransaction, WaitlistEntry
from .services.credits import CreditService
from .services.xp import XPService


def log_admin_action(request, obj, message):
    """Helper to log admin actions for bulk operations."""
    LogEntry.objects.log_action(
        user_id=request.user.pk,
        content_type_id=ContentType.objects.get_for_model(obj).pk,
        object_id=obj.pk,
        object_repr=str(obj),
        action_flag=CHANGE,
        change_message=message,
    )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """
    Custom User admin for Telegram authentication.

    Uses ModelAdmin instead of BaseUserAdmin since our User model
    doesn't use username/password - users authenticate via Telegram.
    """
    list_display = [
        "id", "display_name", "telegram_id", "telegram_username",
        "x_username_display", "tweetscout_display", "xp_display",
        "credits_display", "tier_display", "total_engagements", "current_streak", "is_banned", "created_at",
    ]
    list_filter = ["is_banned", "is_staff", "is_active"]
    search_fields = ["display_name", "telegram_id", "telegram_username", "x_username"]
    ordering = ["-created_at"]
    actions = [
        "grant_10_credits", "grant_50_credits", "grant_100_credits", "revoke_10_credits",
        "grant_10_xp", "grant_50_xp",
        "fetch_x_profile",
        "ban_users", "unban_users"
    ]

    fieldsets = (
        (None, {"fields": ("display_name", "x_username")}),
        ("Telegram", {"fields": ("telegram_id", "telegram_username")}),
        ("Credits", {"fields": (
            "credits", "total_credits_earned", "total_credits_spent",
            "daily_credits_earned",
        )}),
        ("XP (Sponsored)", {"fields": (
            "sponsored_xp", "total_sponsored_xp_earned", "sponsored_engagements",
        )}),
        ("Engagement", {"fields": (
            "total_engagements", "total_posts",
            "current_streak", "longest_streak", "last_engagement_date",
        )}),
        ("TweetScout", {"fields": ("tweetscout_score",)}),
        ("Status", {"fields": ("is_active", "is_banned", "ban_reason")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
    )

    # Fields shown when adding a new user
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("telegram_id", "display_name", "is_staff", "is_superuser"),
        }),
    )

    readonly_fields = [
        "id", "total_credits_earned", "total_credits_spent",
        "total_engagements", "total_posts",
        "total_sponsored_xp_earned", "sponsored_engagements",
        "created_at", "updated_at",
    ]

    filter_horizontal = ("groups", "user_permissions")

    def get_fieldsets(self, request, obj=None):
        """Use add_fieldsets for new users, regular fieldsets for editing."""
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def save_model(self, request, obj, form, change):
        """Set unusable password for new users (they auth via Telegram)."""
        if not change:  # New user
            obj.set_unusable_password()
        super().save_model(request, obj, form, change)

    def credits_display(self, obj):
        """Display credits with color coding."""
        if obj.credits >= 40:
            color = "#27ae60"  # Green - healthy
        elif obj.credits > 0:
            color = "#f39c12"  # Orange - low
        else:
            color = "#e74c3c"  # Red - zero
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.credits)
    credits_display.short_description = "Credits"
    credits_display.admin_order_field = "credits"

    def x_username_display(self, obj):
        """Display X username with link."""
        if obj.x_username:
            return format_html(
                '<a href="https://x.com/{}" target="_blank" style="color: #1da1f2;">@{}</a>',
                obj.x_username, obj.x_username
            )
        return format_html('<span style="color: rgba(255,255,255,0.3);">-</span>')
    x_username_display.short_description = "X Account"
    x_username_display.admin_order_field = "x_username"

    def tweetscout_display(self, obj):
        """Display TweetScout score."""
        score = obj.tweetscout_score or 0
        if score > 0:
            return format_html(
                '<span style="font-weight: bold;">{}</span>',
                int(score)
            )
        return format_html('<span style="color: rgba(255,255,255,0.3);">-</span>')
    tweetscout_display.short_description = "Score"
    tweetscout_display.admin_order_field = "tweetscout_score"

    def tier_display(self, obj):
        """Display user tier with color coding."""
        tier = obj.tier
        # Colors for each tier (Anon → Normie → Degen → Based → Legend → OG → GOAT)
        tier_colors = {
            "Anon": "rgba(255,255,255,0.5)",
            "Normie": "#27ae60",   # Green
            "Degen": "#3498db",    # Blue
            "Based": "#9b59b6",    # Purple
            "Legend": "#f1c40f",   # Yellow
            "OG": "#e67e22",       # Orange
            "GOAT": "#FF6B00",     # Bright Orange
        }
        color = tier_colors.get(tier, "rgba(255,255,255,0.5)")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, tier
        )
    tier_display.short_description = "Tier"
    tier_display.admin_order_field = "tweetscout_score"

    def xp_display(self, obj):
        """Display XP with color coding."""
        xp = obj.sponsored_xp or 0
        if xp >= 100:
            color = "#9b59b6"  # Purple - High
        elif xp >= 50:
            color = "#3498db"  # Blue - Medium
        elif xp > 0:
            color = "#27ae60"  # Green - Some
        else:
            color = "rgba(255,255,255,0.3)"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} XP</span>',
            color, xp
        )
    xp_display.short_description = "XP"
    xp_display.admin_order_field = "sponsored_xp"

    @admin.action(description="Grant 10 credits to selected users")
    def grant_10_credits(self, request, queryset):
        self._grant_credits(request, queryset, 10)

    @admin.action(description="Grant 50 credits to selected users")
    def grant_50_credits(self, request, queryset):
        self._grant_credits(request, queryset, 50)

    @admin.action(description="Grant 100 credits to selected users")
    def grant_100_credits(self, request, queryset):
        self._grant_credits(request, queryset, 100)

    @admin.action(description="Revoke 10 credits from selected users")
    def revoke_10_credits(self, request, queryset):
        for user in queryset:
            credit_service = CreditService(user)
            credit_service.apply_penalty(
                amount=10,
                description=f"Admin revoked via Django admin by {request.user}",
            )
            log_admin_action(request, user, f"Revoked 10 credits (balance: {user.credits})")
        self.message_user(request, f"Revoked 10 credits from {queryset.count()} users.", messages.SUCCESS)

    @admin.action(description="Grant 10 XP to selected users")
    def grant_10_xp(self, request, queryset):
        self._grant_xp(request, queryset, 10)

    @admin.action(description="Grant 50 XP to selected users")
    def grant_50_xp(self, request, queryset):
        self._grant_xp(request, queryset, 50)

    @admin.action(description="Ban selected users")
    def ban_users(self, request, queryset):
        for user in queryset:
            user.is_banned = True
            user.ban_reason = "Banned by admin"
            user.save(update_fields=["is_banned", "ban_reason", "updated_at"])
            log_admin_action(request, user, "Banned user")
        self.message_user(request, f"Banned {queryset.count()} users.", messages.WARNING)

    @admin.action(description="Unban selected users")
    def unban_users(self, request, queryset):
        for user in queryset:
            user.is_banned = False
            user.ban_reason = ""
            user.save(update_fields=["is_banned", "ban_reason", "updated_at"])
            log_admin_action(request, user, "Unbanned user")
        self.message_user(request, f"Unbanned {queryset.count()} users.", messages.SUCCESS)

    def _grant_credits(self, request, queryset, amount):
        for user in queryset:
            credit_service = CreditService(user)
            credit_service.admin_grant(
                amount=amount,
                admin_id=0,  # Django admin
                description=f"Admin granted via Django admin by {request.user}",
            )
            user.refresh_from_db()
            log_admin_action(request, user, f"Granted {amount} credits (balance: {user.credits})")
        self.message_user(request, f"Granted {amount} credits to {queryset.count()} users.", messages.SUCCESS)

    def _grant_xp(self, request, queryset, amount):
        for user in queryset:
            xp_service = XPService(user)
            xp_service.admin_grant(
                amount=amount,
                admin_user=request.user,
                description=f"Admin granted via Django admin by {request.user}",
            )
            user.refresh_from_db()
            log_admin_action(request, user, f"Granted {amount} XP (balance: {user.sponsored_xp})")
        self.message_user(request, f"Granted {amount} XP to {queryset.count()} users.", messages.SUCCESS)

    @admin.action(description="Fetch X Profile from TweetScout (requires x_username)")
    def fetch_x_profile(self, request, queryset):
        """
        Fetch X profile data from TweetScout for selected users.

        Requires user to have x_username set. Creates/updates XProfile record
        with avatar, display_name, score, followers, etc.
        """
        from .services.tweetscout import TweetScoutService
        from django.utils import timezone

        tweetscout = TweetScoutService()
        success_count = 0
        error_count = 0

        for user in queryset:
            if not user.x_username:
                self.message_user(
                    request,
                    f"Skipped {user.display_name or user.id}: no x_username set",
                    messages.WARNING
                )
                error_count += 1
                continue

            try:
                # Fetch data from TweetScout (includes both info AND score)
                ts_data = tweetscout.get_user_data(user.x_username)
                if not ts_data:
                    self.message_user(
                        request,
                        f"TweetScout returned no data for @{user.x_username}",
                        messages.WARNING
                    )
                    error_count += 1
                    continue

                # Create or update XProfile
                # API returns: screen_name, name, description, avatar, banner, friends_count
                x_profile, created = XProfile.objects.update_or_create(
                    user=user,
                    defaults={
                        "x_user_id": ts_data.get("id", ""),
                        "username": ts_data.get("screen_name", user.x_username),
                        "display_name": ts_data.get("name", ""),
                        "bio": ts_data.get("description", ""),
                        "followers_count": ts_data.get("followers_count", 0),
                        "following_count": ts_data.get("friends_count", 0),
                        "tweets_count": ts_data.get("tweets_count", 0),
                        "score": ts_data.get("score", 0),
                        "avatar_url": ts_data.get("avatar", ""),
                        "banner_url": ts_data.get("banner", ""),
                        "is_verified": ts_data.get("verified", False),
                        "can_dm": ts_data.get("can_dm", False),
                        "raw_tweetscout_data": ts_data,
                        "fetched_at": timezone.now(),
                    }
                )

                # Update user's tweetscout_score
                user.tweetscout_score = ts_data.get("score", 0)
                user.tweetscout_last_updated = timezone.now()
                user.save(update_fields=["tweetscout_score", "tweetscout_last_updated", "updated_at"])

                action = "Created" if created else "Updated"
                log_admin_action(request, user, f"{action} XProfile from TweetScout (score: {x_profile.score})")
                success_count += 1

            except Exception as e:
                self.message_user(
                    request,
                    f"Error fetching @{user.x_username}: {str(e)}",
                    messages.ERROR
                )
                error_count += 1

        if success_count:
            self.message_user(
                request,
                f"Successfully fetched X profiles for {success_count} user(s).",
                messages.SUCCESS
            )
        if error_count:
            self.message_user(
                request,
                f"Failed/skipped {error_count} user(s).",
                messages.WARNING
            )


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Transaction admin - READ-ONLY.

    Transactions are created by CreditService, never manually.
    This is an audit trail - no edits or deletions allowed.
    """
    list_display = ["id", "user", "type", "amount", "balance_after", "created_at"]
    list_filter = ["type"]
    search_fields = ["user__display_name", "user__telegram_id"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "user", "type", "amount", "balance_after", "reference_id", "reference_type", "description", "created_at"]

    # Efficient loading
    list_select_related = ['user']
    list_per_page = 50
    show_full_result_count = False

    def has_add_permission(self, request):
        """Transactions are created by services only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Transactions are immutable audit records."""
        return False

    def has_change_permission(self, request, obj=None):
        """Transactions cannot be edited."""
        return False


# Note: Don't register AuditLog here - it's registered in urls.py with custom admin site
# AuditLog is for engagement verification (did user actually engage?), NOT admin logging
class AuditLogAdmin(admin.ModelAdmin):
    """
    Engagement verification audits - READ-ONLY.

    NOT for admin action logging - that's handled by django-auditlog.
    This tracks random spot-checks to verify users actually liked/replied.
    Audit records are created by verification service, never manually.
    """
    list_display = ["id", "user", "result", "penalty_applied", "created_at"]
    list_filter = ["result"]
    search_fields = ["user__display_name"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "user", "engagement_id", "post_id", "result", "penalty_applied", "created_at"]

    # Efficient loading
    list_select_related = ['user']
    list_per_page = 50
    show_full_result_count = False

    def has_add_permission(self, request):
        """Audit logs are created by verification service only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit logs are immutable records."""
        return False

    def has_change_permission(self, request, obj=None):
        """Audit logs cannot be edited."""
        return False


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    """
    Admin for dynamic site settings.

    Settings can be edited inline from the list view for quick changes.
    """
    list_display = ["key", "value", "data_type", "description_short", "updated_at", "updated_by"]
    list_editable = ["value"]
    list_filter = ["data_type"]
    search_fields = ["key", "description"]
    ordering = ["key"]
    readonly_fields = ["updated_at", "updated_by"]

    # Efficient loading
    list_per_page = 50

    fieldsets = (
        (None, {"fields": ("key", "value", "data_type")}),
        ("Documentation", {"fields": ("description",)}),
        ("Audit", {"fields": ("updated_at", "updated_by")}),
    )

    def description_short(self, obj):
        """Truncated description for list display."""
        if len(obj.description) > 50:
            return obj.description[:50] + "..."
        return obj.description
    description_short.short_description = "Description"

    def save_model(self, request, obj, form, change):
        """Track who made the change and clear cache."""
        from django.core.cache import cache

        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

        # Clear cache for this setting so changes reflect immediately
        cache.delete(f'setting:{obj.key}')

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion - app will crash without settings."""
        return False

    def has_add_permission(self, request):
        """Prevent manual adds - use migrations instead."""
        return False


@admin.register(XProfile)
class XProfileAdmin(admin.ModelAdmin):
    """
    Admin for X/Twitter profile data.

    Shows TweetScout data for linked X accounts.
    XProfiles are auto-created when users link their X account via the app.
    """
    list_display = [
        "username", "user_link", "display_name", "score_display",
        "followers_count", "is_verified", "updated_at",
    ]
    list_filter = ["is_verified"]
    search_fields = ["username", "display_name", "user__display_name"]
    ordering = ["-score"]
    readonly_fields = [
        "user", "x_user_id", "username", "display_name", "bio",
        "followers_count", "following_count", "tweets_count", "score",
        "avatar_url", "banner_url", "is_verified", "can_dm",
        "x_created_at",
        "raw_tweetscout_data", "fetched_at", "updated_at",
    ]

    def has_add_permission(self, request):
        """
        Disable manual creation from admin.
        XProfiles are auto-created when users link their X account via the app API.
        """
        return False

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("X Profile", {"fields": ("x_user_id", "username", "display_name", "bio")}),
        ("Metrics", {"fields": ("score", "followers_count", "following_count", "tweets_count")}),
        ("Status", {"fields": ("is_verified", "can_dm")}),
        ("Assets", {"fields": ("avatar_url", "banner_url")}),
        ("Account Age", {"fields": ("x_created_at",)}),
        ("Raw Data", {"fields": ("raw_tweetscout_data",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("fetched_at", "updated_at")}),
    )

    # Efficient loading
    list_select_related = ['user']
    list_per_page = 50
    show_full_result_count = False

    def user_link(self, obj):
        """Clickable link to user admin page."""
        if obj.user:
            return format_html(
                '<a href="/loudrr-admin/core/user/{}/change/">{}</a>',
                obj.user.pk, obj.user.display_name or obj.user
            )
        return "-"
    user_link.short_description = "Linked User"

    def score_display(self, obj):
        """Display score with tier color coding."""
        score = obj.score or 0
        if score >= 800:
            color = "#FF6B00"  # Orange - Elite
            tier = "Elite"
        elif score >= 400:
            color = "#9b59b6"  # Purple
            tier = "Pro"
        elif score >= 200:
            color = "#3498db"  # Blue
            tier = "Rising"
        elif score >= 100:
            color = "#27ae60"  # Green
            tier = "Active"
        else:
            color = "rgba(255,255,255,0.5)"  # Muted
            tier = "Starter"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} ({})</span>',
            color, int(score), tier
        )
    score_display.short_description = "TweetScout Score"
    score_display.admin_order_field = "score"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(XPTransaction)
class XPTransactionAdmin(admin.ModelAdmin):
    """
    XP Transaction admin - READ-ONLY.

    XP Transactions are created by XPService, never manually.
    This is an audit trail for all XP changes.
    """
    list_display = [
        "id_short", "user_link", "type", "amount_display",
        "balance_after", "reference_type", "created_at"
    ]
    list_filter = ["type"]
    search_fields = ["user__display_name", "user__telegram_username", "description"]
    ordering = ["-created_at"]
    readonly_fields = [
        "id", "user", "type", "amount", "balance_after",
        "reference_id", "reference_type", "description", "created_at"
    ]

    # Efficient loading
    list_select_related = ['user']
    list_per_page = 50
    show_full_result_count = False

    fieldsets = (
        ("Transaction", {"fields": ("id", "user", "type", "amount", "balance_after")}),
        ("Reference", {"fields": ("reference_id", "reference_type", "description")}),
        ("Timestamp", {"fields": ("created_at",)}),
    )

    def has_add_permission(self, request):
        """XP Transactions are created by services only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """XP Transactions are immutable audit records."""
        return False

    def has_change_permission(self, request, obj=None):
        """XP Transactions cannot be edited."""
        return False

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def user_link(self, obj):
        """Clickable link to user admin page."""
        return format_html(
            '<a href="/loudrr-admin/core/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.display_name or str(obj.user)
        )
    user_link.short_description = "User"

    def amount_display(self, obj):
        """Display amount with color (green for positive, red for negative)."""
        if obj.amount >= 0:
            return format_html(
                '<span style="color: #27ae60; font-weight: bold;">+{} XP</span>',
                obj.amount
            )
        return format_html(
            '<span style="color: #e74c3c; font-weight: bold;">{} XP</span>',
            obj.amount
        )
    amount_display.short_description = "Amount"
    amount_display.admin_order_field = "amount"


# WaitlistEntry is registered in echo/urls.py with loudrr_admin
# Do NOT use @admin.register here to avoid duplicate registration
class WaitlistEntryAdmin(admin.ModelAdmin):
    """
    Admin for waitlist entries.

    Allows admins to approve/reject waitlist applications.
    """
    list_display = [
        "email", "x_username_display", "followers_display", "verified_display",
        "telegram_username_display", "status_display", "created_at",
    ]
    list_filter = ["status", "x_is_verified", "email_verified", "created_at"]
    search_fields = ["email", "x_username", "x_display_name", "telegram_username"]
    ordering = ["-x_followers_count", "-created_at"]  # High followers first by default
    readonly_fields = [
        "id", "join_token", "telegram_id", "telegram_username",
        "telegram_display_name", "email_verified",
        "x_display_name", "x_followers_count", "x_avatar_url", "x_is_verified", "x_fetched_at",
        "created_at", "updated_at", "approved_at", "created_user",
    ]
    actions = ["approve_entries", "reject_entries"]

    # Efficient loading
    list_per_page = 50
    show_full_result_count = False

    fieldsets = (
        ("Email", {"fields": ("email", "email_verified")}),
        ("Telegram", {"fields": ("telegram_id", "telegram_username", "telegram_display_name")}),
        ("X/Twitter", {"fields": (
            "x_username", "x_display_name", "x_followers_count",
            "x_is_verified", "x_avatar_url", "x_fetched_at"
        )}),
        ("Status", {"fields": ("status", "approved_at", "created_user")}),
        ("Internal", {"fields": ("id", "join_token"), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def x_username_display(self, obj):
        """Display X username with link."""
        if obj.x_username:
            return format_html(
                '<a href="https://x.com/{}" target="_blank" style="color: #FF6B00;">@{}</a>',
                obj.x_username, obj.x_username
            )
        return format_html('<span style="color: rgba(255,255,255,0.3);">-</span>')
    x_username_display.short_description = "X Account"
    x_username_display.admin_order_field = "x_username"

    def telegram_username_display(self, obj):
        """Display Telegram username."""
        if obj.telegram_username:
            return f"@{obj.telegram_username}"
        return format_html('<span style="color: rgba(255,255,255,0.3);">-</span>')
    telegram_username_display.short_description = "Telegram"
    telegram_username_display.admin_order_field = "telegram_username"

    def status_display(self, obj):
        """Display status with color coding."""
        status_colors = {
            WaitlistEntry.Status.PENDING: ("rgba(255,255,255,0.5)", "Pending"),
            WaitlistEntry.Status.SUBMITTED: ("#f39c12", "Submitted"),
            WaitlistEntry.Status.APPROVED: ("#27ae60", "Approved"),
            WaitlistEntry.Status.REJECTED: ("#e74c3c", "Rejected"),
        }
        color, label = status_colors.get(obj.status, ("white", obj.status))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, label
        )
    status_display.short_description = "Status"
    status_display.admin_order_field = "status"

    def email_verified_display(self, obj):
        """Display email verification status."""
        if obj.email_verified:
            return format_html('<span style="color: #27ae60;">✓</span>')
        return format_html('<span style="color: rgba(255,255,255,0.3);">-</span>')
    email_verified_display.short_description = "Email ✓"

    def followers_display(self, obj):
        """Display follower count with formatting (sortable)."""
        if obj.x_followers_count is None:
            return format_html('<span style="color: rgba(255,255,255,0.3);">-</span>')

        count = obj.x_followers_count
        if count >= 1_000_000:
            formatted = f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            formatted = f"{count / 1_000:.1f}K"
        else:
            formatted = str(count)

        # Color based on follower tier
        if count >= 100_000:
            color = "#f39c12"  # Gold for 100K+
        elif count >= 10_000:
            color = "#3498db"  # Blue for 10K+
        elif count >= 1_000:
            color = "#27ae60"  # Green for 1K+
        else:
            color = "rgba(255,255,255,0.7)"

        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, formatted
        )
    followers_display.short_description = "Followers"
    followers_display.admin_order_field = "x_followers_count"

    def verified_display(self, obj):
        """Display X verified (blue checkmark) status."""
        if obj.x_is_verified:
            return format_html('<span style="color: #1DA1F2;">✓</span>')
        return format_html('<span style="color: rgba(255,255,255,0.3);">-</span>')
    verified_display.short_description = "X ✓"
    verified_display.admin_order_field = "x_is_verified"

    @admin.action(description="✅ Approve selected entries")
    def approve_entries(self, request, queryset):
        """Approve selected waitlist entries and create users."""
        from django.utils import timezone
        from django.db import transaction as db_transaction

        approved = 0
        errors = []

        for entry in queryset.filter(status=WaitlistEntry.Status.SUBMITTED):
            try:
                with db_transaction.atomic():
                    # Validate entry has required data
                    if not entry.telegram_id:
                        errors.append(f"{entry.email}: No Telegram linked")
                        continue
                    if not entry.x_username:
                        errors.append(f"{entry.email}: No X username")
                        continue

                    # Check if user already exists with this telegram_id
                    if User.objects.filter(telegram_id=entry.telegram_id).exists():
                        errors.append(f"{entry.email}: Telegram ID already registered")
                        continue

                    # Check if x_username already used
                    if User.objects.filter(x_username__iexact=entry.x_username).exists():
                        errors.append(f"{entry.email}: X username already registered")
                        continue

                    # Create user
                    user = User.objects.create(
                        telegram_id=entry.telegram_id,
                        telegram_username=entry.telegram_username or "",
                        display_name=entry.telegram_display_name or "",
                        x_username=entry.x_username,
                        is_whitelisted=True,
                    )

                    # Update entry (notification sent automatically via post_save signal)
                    entry.status = WaitlistEntry.Status.APPROVED
                    entry.approved_at = timezone.now()
                    entry.created_user = user
                    entry.save(update_fields=['status', 'approved_at', 'created_user', 'updated_at'])

                    # Note: Telegram notification is sent automatically by post_save signal
                    # See core/signals.py:send_approval_notification_on_approve
                    # - Uses dispatch_uid to prevent duplicates
                    # - Uses transaction.on_commit for reliability
                    # - Delegates to Celery background task (non-blocking)

                    log_admin_action(request, entry, f"Approved and created user {user.id}")
                    approved += 1

            except Exception as e:
                errors.append(f"{entry.email}: {str(e)}")

        if approved:
            self.message_user(request, f"Approved {approved} entries.", messages.SUCCESS)
        if errors:
            for error in errors[:5]:  # Show first 5 errors
                self.message_user(request, error, messages.WARNING)

    @admin.action(description="❌ Reject selected entries")
    def reject_entries(self, request, queryset):
        """Reject selected waitlist entries."""
        count = queryset.filter(status=WaitlistEntry.Status.SUBMITTED).update(
            status=WaitlistEntry.Status.REJECTED
        )
        self.message_user(request, f"Rejected {count} entries.", messages.WARNING)
