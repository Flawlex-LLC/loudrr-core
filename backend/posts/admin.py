import re

from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import Post, Engagement, SponsoredPost, Campaign, CampaignEntry
from core.models import User
from core.services.credits import CreditService
from core.services.campaigns import CampaignService


def extract_tweet_id(url: str) -> str:
    """Extract tweet ID from X/Twitter URL."""
    pattern = r"status/(\d+)"
    match = re.search(pattern, url)
    return match.group(1) if match else ""


class AdminPostForm(forms.ModelForm):
    """
    Custom form for creating posts from admin.

    Credits are ALWAYS deducted from the user's balance.
    For sponsors: create user, grant credits via admin action, then create post.

    IMPORTANT: User must have X account linked (XProfile) to create posts.
    Use "Fetch X Profile from TweetScout" action on User admin to auto-populate.
    """
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).select_related('x_profile').order_by('-credits'),
        label='Post Owner',
        help_text='Select user to create post for. User MUST have X account linked and enough credits!'
    )
    x_link = forms.URLField(
        label='X/Twitter URL',
        help_text='Paste the tweet URL (e.g., https://x.com/user/status/123456)'
    )
    is_sponsored = forms.BooleanField(
        required=False,
        initial=False,
        label='Mark as +XP Post',
        help_text='Shows "+XP" badge in feed. Awards XP to engagers. Credits still deducted from user balance.'
    )
    escrow_amount = forms.IntegerField(
        initial=80,
        min_value=1,
        required=False,  # Optional - defaults to POST_COST (80)
        label='Escrow Amount',
        help_text='Credits to allocate (default: 80). Will be deducted from user balance.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize user display to show X account status
        self.fields['user'].label_from_instance = self._user_label

    def _user_label(self, user):
        """Display user with X account status and credits."""
        has_x = hasattr(user, 'x_profile') and user.x_profile is not None
        x_status = f"@{user.x_profile.username}" if has_x else "⚠️ NO X LINKED"
        return f"{user.display_name or user.telegram_username} ({x_status}) - {user.credits} credits"

    class Meta:
        model = Post
        fields = ['user', 'x_link', 'is_sponsored']  # escrow_amount is form-only, not a model field

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        x_link = cleaned_data.get('x_link', '')
        is_sponsored = cleaned_data.get('is_sponsored', False)
        post_cost = settings.ECHO_CONFIG.get('POST_COST', 80)

        # CRITICAL: User must have X account linked with XProfile
        if user:
            has_x_profile = hasattr(user, 'x_profile') and user.x_profile is not None
            has_x_username = bool(user.x_username)

            if not has_x_profile and not has_x_username:
                raise ValidationError(
                    f"User '{user.display_name or user.telegram_username}' has NO X account! "
                    f"Set their x_username field, then use 'Fetch X Profile from TweetScout' action in User admin."
                )
            elif not has_x_profile:
                # Has x_username but no XProfile - use fetch action
                raise ValidationError(
                    f"User '{user.display_name or user.telegram_username}' has x_username but no XProfile. "
                    f"Go to User admin and use 'Fetch X Profile from TweetScout' action to create their profile."
                )

        # Validate X/Twitter URL format
        if x_link:
            # Must be from x.com or twitter.com
            if not re.match(r'^https?://(www\.)?(x\.com|twitter\.com)/', x_link):
                raise ValidationError(
                    "URL must be from x.com or twitter.com. "
                    "Example: https://x.com/username/status/123456789"
                )
            # Must contain /status/ with tweet ID
            if not re.search(r'/status/\d+', x_link):
                raise ValidationError(
                    "Invalid tweet URL format. Must contain /status/ followed by tweet ID. "
                    "Example: https://x.com/username/status/123456789"
                )
            # Reject /i/status/ format - require proper username in URL
            if '/i/status/' in x_link:
                raise ValidationError(
                    "Please use the full tweet URL with username. "
                    "Example: https://x.com/username/status/123456789 (not x.com/i/status/...)"
                )

        # Always check credits - no free posts
        escrow_amount = self.cleaned_data.get('escrow_amount') or post_cost
        if user and user.credits < escrow_amount:
            raise ValidationError(
                f"User '{user.display_name or user}' has only {user.credits} credits. "
                f"Needs {escrow_amount} to post. "
                f"Grant credits to the user first via User admin action."
            )

        return cleaned_data


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    """
    Enhanced Post admin with efficient loading and admin post creation.

    All posts deduct credits from user's balance (including sponsors).
    For sponsors: create User, grant credits, fetch X profile, then create post.
    """
    list_display = [
        "id", "user_link", "status", "escrow", "initial_escrow", "engagement_count_display",
        "is_sponsored", "platform", "created_at",
    ]
    list_filter = ["status", "platform", "is_sponsored"]
    search_fields = ["user__display_name", "user__telegram_username", "x_link", "tweet_id"]
    ordering = ["-created_at"]
    readonly_fields = [
        "id", "redirect_token", "tweet_id",
        "created_at", "updated_at", "completed_at",
    ]

    # Efficient loading - avoid N+1 queries
    list_select_related = ['user']
    list_per_page = 50
    show_full_result_count = False  # Avoid COUNT(*) on large tables

    fieldsets = (
        (None, {"fields": ("user", "x_link", "tweet_id")}),
        ("Credits", {"fields": ("escrow", "initial_escrow")}),
        ("Status", {"fields": ("status", "is_sponsored", "platform")}),
        ("Tracking", {"fields": ("redirect_token", "channel_id", "message_id")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "completed_at")}),
    )

    def user_link(self, obj):
        """Clickable link to user admin page."""
        return format_html(
            '<a href="/loudrr-admin/core/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.display_name or obj.user
        )
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__display_name'

    def engagement_count_display(self, obj):
        """Display engagement count with color coding."""
        count = obj.engagement_count
        if count >= obj.initial_escrow:
            color = "green"
        elif count > 0:
            color = "orange"
        else:
            color = "gray"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/{}</span>',
            color, count, obj.initial_escrow
        )
    engagement_count_display.short_description = 'Engagements'

    def get_queryset(self, request):
        """Optimize query with select_related."""
        return super().get_queryset(request).select_related('user')

    def get_form(self, request, obj=None, **kwargs):
        """Use custom form for adding new posts."""
        if obj is None:  # Adding new post
            kwargs['form'] = AdminPostForm
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Handle admin post creation.

        Credits are ALWAYS deducted from user's balance.
        is_sponsored flag just shows a badge in the UI.
        """
        if not change:  # New post from admin
            selected_user = form.cleaned_data['user']
            is_sponsored = form.cleaned_data.get('is_sponsored', False)
            escrow_amount = form.cleaned_data.get('escrow_amount') or settings.ECHO_CONFIG.get('POST_COST', 80)

            # Always deduct credits from user
            credit_service = CreditService(selected_user)
            credit_service.spend(
                amount=escrow_amount,
                reference_type="post",
                description=f"Post created by admin ({request.user}){' [+XP]' if is_sponsored else ''}",
            )

            obj.escrow = escrow_amount
            obj.initial_escrow = escrow_amount
            obj.is_sponsored = is_sponsored  # Just a UI badge
            obj.user = selected_user
            obj.platform = "web"
            obj.tweet_id = extract_tweet_id(obj.x_link)

        super().save_model(request, obj, form, change)


@admin.register(Engagement)
class EngagementAdmin(admin.ModelAdmin):
    """Engagement admin with efficient loading."""
    list_display = ["id", "user_link", "post_link", "credit_granted", "verified", "clicked_at", "created_at"]
    list_filter = ["credit_granted", "verified"]
    search_fields = ["user__display_name", "user__telegram_username", "post__tweet_id"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "user", "post", "clicked_at", "created_at"]

    # Efficient loading
    list_select_related = ['user', 'post']
    list_per_page = 50
    show_full_result_count = False

    def user_link(self, obj):
        """Clickable link to user."""
        return format_html(
            '<a href="/loudrr-admin/core/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.display_name or obj.user
        )
    user_link.short_description = 'User'

    def post_link(self, obj):
        """Clickable link to post."""
        return format_html(
            '<a href="/loudrr-admin/posts/post/{}/change/">Post {}</a>',
            obj.post.pk, str(obj.post.pk)[:8]
        )
    post_link.short_description = 'Post'

    def get_queryset(self, request):
        """Optimize query with select_related."""
        return super().get_queryset(request).select_related('user', 'post', 'post__user')


@admin.register(SponsoredPost)
class SponsoredPostAdmin(admin.ModelAdmin):
    """Sponsored post admin."""
    list_display = [
        "id", "post", "sponsor_name", "credit_reward",
        "remaining_budget", "total_budget", "is_active", "created_at",
    ]
    list_filter = ["credit_reward"]
    search_fields = ["sponsor_name", "sponsor_contact"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]

    # Efficient loading
    list_select_related = ['post', 'post__user']
    list_per_page = 50

    def is_active(self, obj):
        """Display active status with color."""
        if obj.is_active:
            return format_html('<span style="color: green;">Active</span>')
        return format_html('<span style="color: red;">Inactive</span>')
    is_active.short_description = 'Status'


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """
    Campaign/Giveaway admin.

    Admins can:
    - Create campaigns with eligibility requirements
    - Set min XP to 0 for open giveaways
    - Select winners when campaign ends
    """
    list_display = [
        "name", "type", "status_display", "entries_count",
        "budget_display", "requirements_display", "starts_at", "ends_at",
    ]
    list_filter = ["type", "status", "require_x_linked"]
    search_fields = ["name", "description"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "winners_announced_at", "created_at", "updated_at"]
    actions = ["activate_campaigns", "select_winners_action"]

    list_per_page = 50

    fieldsets = (
        ("Basic Info", {
            "fields": ("name", "description", "type", "status")
        }),
        ("Budget & Prizes", {
            "fields": (
                "budget", "remaining_budget", "prize_description",
                "prize_value", "max_winners", "winner_selection_method"
            )
        }),
        ("Timing", {
            "fields": ("starts_at", "ends_at", "entry_deadline")
        }),
        ("Eligibility Requirements", {
            "fields": (
                "min_sponsored_xp", "min_engagements", "min_posts",
                "min_streak", "min_tweetscout_score", "require_x_linked"
            ),
            "description": "Set to 0 or unchecked for no requirement (open to all)."
        }),
        ("Entry Limits", {
            "fields": ("max_entries",)
        }),
        ("Results", {
            "fields": ("winners_announced_at",),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def status_display(self, obj):
        """Display status with color."""
        colors = {
            "draft": "#95a5a6",
            "active": "#27ae60",
            "completed": "#3498db",
            "cancelled": "#e74c3c",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = "Status"
    status_display.admin_order_field = "status"

    def entries_count(self, obj):
        """Display entry counts."""
        eligible = obj.entries.filter(status="eligible").count()
        total = obj.entries.count()
        winners = obj.entries.filter(is_winner=True).count()
        if winners > 0:
            return format_html(
                '<span style="color: #9b59b6; font-weight: bold;">{} winners</span> / {} eligible / {} total',
                winners, eligible, total
            )
        return f"{eligible} eligible / {total} total"
    entries_count.short_description = "Entries"

    def budget_display(self, obj):
        """Display budget with remaining."""
        return f"${obj.remaining_budget} / ${obj.budget}"
    budget_display.short_description = "Budget"

    def requirements_display(self, obj):
        """Display eligibility requirements summary."""
        reqs = obj.get_eligibility_requirements()
        if reqs == ["Open to all"]:
            return format_html('<span style="color: #27ae60;">Open to all</span>')
        return ", ".join(reqs[:2]) + ("..." if len(reqs) > 2 else "")
    requirements_display.short_description = "Requirements"

    @admin.action(description="Activate selected campaigns")
    def activate_campaigns(self, request, queryset):
        updated = queryset.filter(status=Campaign.Status.DRAFT).update(
            status=Campaign.Status.ACTIVE
        )
        self.message_user(request, f"Activated {updated} campaign(s).")

    @admin.action(description="Select winners for selected campaigns")
    def select_winners_action(self, request, queryset):
        service = CampaignService()
        for campaign in queryset.filter(status=Campaign.Status.ACTIVE):
            winners = service.select_winners(campaign)
            self.message_user(
                request,
                f"Selected {len(winners)} winner(s) for '{campaign.name}'"
            )


@admin.register(CampaignEntry)
class CampaignEntryAdmin(admin.ModelAdmin):
    """
    Campaign entry admin.

    View entries with eligibility status and winner info.
    """
    list_display = [
        "id_short", "campaign_link", "user_link", "status_display",
        "xp_at_entry_display", "is_winner_display", "created_at",
    ]
    list_filter = ["status", "is_winner", "entry_source", "campaign"]
    search_fields = [
        "user__display_name", "user__telegram_username",
        "campaign__name"
    ]
    ordering = ["-created_at"]
    readonly_fields = [
        "id", "campaign", "user", "status", "eligibility_snapshot",
        "ineligibility_reason", "is_winner", "prize_claimed",
        "prize_claimed_at", "created_at"
    ]
    actions = ["mark_as_winner", "mark_prize_claimed"]

    list_select_related = ["campaign", "user"]
    list_per_page = 50

    fieldsets = (
        ("Entry Info", {
            "fields": ("id", "campaign", "user", "entry_source")
        }),
        ("Status", {
            "fields": ("status", "ineligibility_reason")
        }),
        ("Winner Info", {
            "fields": ("is_winner", "prize_claimed", "prize_claimed_at")
        }),
        ("Payout", {
            "fields": ("payout_amount", "payout_status")
        }),
        ("Tweet (if required)", {
            "fields": ("tweet_url", "tweet_id", "verified"),
            "classes": ("collapse",)
        }),
        ("Eligibility Snapshot", {
            "fields": ("eligibility_snapshot",),
            "classes": ("collapse",),
            "description": "User stats captured at time of entry."
        }),
        ("Timestamps", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )

    def id_short(self, obj):
        return str(obj.id)[:8]
    id_short.short_description = "ID"

    def campaign_link(self, obj):
        return format_html(
            '<a href="/loudrr-admin/posts/campaign/{}/change/">{}</a>',
            obj.campaign.pk, obj.campaign.name[:30]
        )
    campaign_link.short_description = "Campaign"

    def user_link(self, obj):
        return format_html(
            '<a href="/loudrr-admin/core/user/{}/change/">{}</a>',
            obj.user.pk, obj.user.display_name or str(obj.user)
        )
    user_link.short_description = "User"

    def status_display(self, obj):
        colors = {
            "pending": "#f39c12",
            "eligible": "#27ae60",
            "ineligible": "#e74c3c",
            "winner": "#9b59b6",
            "claimed": "#3498db",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = "Status"
    status_display.admin_order_field = "status"

    def xp_at_entry_display(self, obj):
        xp = obj.eligibility_snapshot.get('sponsored_xp', 0)
        return format_html(
            '<span style="color: #9b59b6;">{} XP</span>', xp
        )
    xp_at_entry_display.short_description = "XP at Entry"

    def is_winner_display(self, obj):
        if obj.is_winner:
            if obj.prize_claimed:
                return format_html('<span style="color: #3498db;">Claimed</span>')
            return format_html('<span style="color: #9b59b6;">Winner</span>')
        return "-"
    is_winner_display.short_description = "Winner"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("campaign", "user")

    @admin.action(description="Mark selected as winners")
    def mark_as_winner(self, request, queryset):
        updated = queryset.filter(status="eligible").update(
            status="winner",
            is_winner=True
        )
        self.message_user(request, f"Marked {updated} entry(ies) as winners.")

    @admin.action(description="Mark prizes as claimed")
    def mark_prize_claimed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(is_winner=True, prize_claimed=False).update(
            status="claimed",
            prize_claimed=True,
            prize_claimed_at=timezone.now()
        )
        self.message_user(request, f"Marked {updated} prize(s) as claimed.")
