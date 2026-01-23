"""
Django admin configuration for Loud feature.
"""
from django.contrib import admin
from django.utils import timezone

from loud.models import LoudProject, LoudSubmission, LoudLeaderboardEntry


@admin.register(LoudProject)
class LoudProjectAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'is_active', 'starts_at', 'ends_at',
        'min_tweetscout_score', 'max_submissions_per_user',
        'participant_count', 'time_remaining'
    ]
    list_filter = ['is_active', 'starts_at', 'ends_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    fieldsets = (
        ('Project Info', {
            'fields': ('name', 'slug', 'description', 'logo_url')
        }),
        ('Timing', {
            'fields': ('starts_at', 'ends_at'),
            'description': 'Project will be visible between these dates'
        }),
        ('Eligibility & Limits', {
            'fields': ('min_tweetscout_score', 'max_submissions_per_user', 'is_active'),
            'description': 'Set minimum TweetScout score (0 = no minimum)'
        }),
        ('Rewards (Display Only)', {
            'fields': ('reward_pool', 'reward_description'),
            'classes': ('collapse',),
            'description': 'These are for display only - actual rewards distributed off-platform'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def participant_count(self, obj):
        return LoudLeaderboardEntry.objects.filter(project=obj).count()
    participant_count.short_description = 'Participants'

    def time_remaining(self, obj):
        if obj.ends_at < timezone.now():
            return "Ended"
        delta = obj.ends_at - timezone.now()
        return f"{delta.days}d {delta.seconds // 3600}h"
    time_remaining.short_description = 'Time Left'


@admin.register(LoudSubmission)
class LoudSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'project', 'points_awarded',
        'x_username', 'submitted_at'
    ]
    list_filter = ['project', 'submitted_at']
    search_fields = [
        'user__display_name', 'user__x_username',
        'x_link', 'tweet_id'
    ]
    readonly_fields = [
        'id', 'user', 'project', 'x_link', 'tweet_id', 'x_username',
        'points_awarded', 'tweetscout_score_at_submission', 'submitted_at'
    ]
    ordering = ['-submitted_at']

    def has_add_permission(self, request):
        return False  # No manual additions

    def has_change_permission(self, request, obj=None):
        return False  # Read-only

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete (for spam)


@admin.register(LoudLeaderboardEntry)
class LoudLeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'project', 'total_points',
        'submission_count', 'last_submission_at'
    ]
    list_filter = ['project']
    search_fields = ['user__display_name', 'user__x_username']
    readonly_fields = [
        'id', 'user', 'project', 'total_points',
        'submission_count', 'last_submission_at'
    ]
    ordering = ['-total_points']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
