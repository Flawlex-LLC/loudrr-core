"""
Django admin configuration for Loud feature.

Includes point adjustment functionality for moderation.
"""
import logging
from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from loud.models import (
    LoudProject, LoudSubmission, LoudLeaderboardEntry, LoudPointAdjustment
)

logger = logging.getLogger(__name__)


class PointAdjustmentForm(forms.Form):
    """Form for adjusting user points."""
    points = forms.IntegerField(
        min_value=1,
        help_text="Number of points to deduct"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Required: Explain why points are being removed"
    )


class VoidSubmissionForm(forms.Form):
    """Form for voiding a specific submission."""
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Required: Explain why this submission is being voided"
    )


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
        'x_username', 'submitted_at', 'void_action'
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
    actions = ['void_selected_submissions']

    def has_add_permission(self, request):
        return False  # No manual additions

    def has_change_permission(self, request, obj=None):
        return False  # Read-only

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superuser can delete (for spam)

    def void_action(self, obj):
        """Link to void this submission."""
        url = reverse('admin:loud_submission_void', args=[obj.pk])
        return format_html('<a href="{}" class="button">Void</a>', url)
    void_action.short_description = 'Action'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/void/',
                self.admin_site.admin_view(self.void_submission_view),
                name='loud_submission_void'
            ),
        ]
        return custom_urls + urls

    def void_submission_view(self, request, pk):
        """View to void a single submission."""
        submission = LoudSubmission.objects.select_related(
            'user', 'project'
        ).get(pk=pk)

        # Get leaderboard entry
        try:
            entry = LoudLeaderboardEntry.objects.get(
                project=submission.project,
                user=submission.user
            )
        except LoudLeaderboardEntry.DoesNotExist:
            messages.error(request, "Leaderboard entry not found")
            return redirect('admin:loud_loudsubmission_changelist')

        if request.method == 'POST':
            form = VoidSubmissionForm(request.POST)
            if form.is_valid():
                reason = form.cleaned_data['reason']
                points_to_remove = submission.points_awarded

                with transaction.atomic():
                    points_before = entry.total_points
                    points_after = max(0, points_before - points_to_remove)

                    # Update leaderboard
                    entry.total_points = points_after
                    entry.save(update_fields=['total_points'])

                    # Create audit record
                    LoudPointAdjustment.objects.create(
                        leaderboard_entry=entry,
                        submission=submission,
                        adjustment_type=LoudPointAdjustment.AdjustmentType.SUBMISSION_VOID,
                        points_change=-points_to_remove,
                        reason=reason,
                        points_before=points_before,
                        points_after=points_after,
                        admin_user=request.user,
                    )

                    logger.warning(
                        "LOUD submission voided by admin",
                        extra={
                            'admin_user': request.user.username,
                            'user_id': str(submission.user.id),
                            'project_id': str(submission.project.id),
                            'submission_id': str(submission.id),
                            'points_removed': points_to_remove,
                            'reason': reason,
                        }
                    )

                messages.success(
                    request,
                    f"Voided submission: -{points_to_remove} points from {submission.user.display_name}"
                )
                return redirect('admin:loud_loudsubmission_changelist')
        else:
            form = VoidSubmissionForm()

        context = {
            'title': f'Void Submission',
            'submission': submission,
            'entry': entry,
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/loud/void_submission.html', context)

    @admin.action(description="Void selected submissions")
    def void_selected_submissions(self, request, queryset):
        """Bulk void selected submissions."""
        if 'apply' in request.POST:
            reason = request.POST.get('reason', '')
            if not reason:
                messages.error(request, "Reason is required")
                return

            total_voided = 0
            with transaction.atomic():
                for submission in queryset.select_related('user', 'project'):
                    try:
                        entry = LoudLeaderboardEntry.objects.get(
                            project=submission.project,
                            user=submission.user
                        )
                    except LoudLeaderboardEntry.DoesNotExist:
                        continue

                    points_to_remove = submission.points_awarded
                    points_before = entry.total_points
                    points_after = max(0, points_before - points_to_remove)

                    entry.total_points = points_after
                    entry.save(update_fields=['total_points'])

                    LoudPointAdjustment.objects.create(
                        leaderboard_entry=entry,
                        submission=submission,
                        adjustment_type=LoudPointAdjustment.AdjustmentType.SUBMISSION_VOID,
                        points_change=-points_to_remove,
                        reason=reason,
                        points_before=points_before,
                        points_after=points_after,
                        admin_user=request.user,
                    )

                    logger.warning(
                        "LOUD submission voided by admin (bulk)",
                        extra={
                            'admin_user': request.user.username,
                            'user_id': str(submission.user.id),
                            'submission_id': str(submission.id),
                            'points_removed': points_to_remove,
                        }
                    )
                    total_voided += 1

            messages.success(request, f"Voided {total_voided} submissions")
            return redirect('admin:loud_loudsubmission_changelist')

        return render(request, 'admin/loud/bulk_void_confirmation.html', {
            'title': 'Void Selected Submissions',
            'submissions': queryset,
            'opts': self.model._meta,
        })


@admin.register(LoudLeaderboardEntry)
class LoudLeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'project', 'total_points',
        'submission_count', 'last_submission_at', 'adjust_action'
    ]
    list_filter = ['project']
    search_fields = ['user__display_name', 'user__x_username']
    readonly_fields = [
        'id', 'user', 'project', 'total_points',
        'submission_count', 'last_submission_at', 'adjustment_history'
    ]
    ordering = ['-total_points']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def adjust_action(self, obj):
        """Link to adjust points."""
        url = reverse('admin:loud_leaderboard_adjust', args=[obj.pk])
        return format_html('<a href="{}" class="button">Adjust Points</a>', url)
    adjust_action.short_description = 'Action'

    def adjustment_history(self, obj):
        """Show recent adjustments."""
        adjustments = obj.adjustments.order_by('-created_at')[:5]
        if not adjustments:
            return "No adjustments"

        lines = []
        for adj in adjustments:
            admin_name = adj.admin_user.username if adj.admin_user else 'Unknown'
            lines.append(
                f"{adj.created_at:%Y-%m-%d %H:%M} | {adj.points_change:+d} pts | "
                f"{adj.adjustment_type} | by {admin_name}"
            )
        return format_html('<pre style="margin:0">{}</pre>', '\n'.join(lines))
    adjustment_history.short_description = 'Recent Adjustments'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<uuid:pk>/adjust/',
                self.admin_site.admin_view(self.adjust_points_view),
                name='loud_leaderboard_adjust'
            ),
        ]
        return custom_urls + urls

    def adjust_points_view(self, request, pk):
        """View to adjust points for a leaderboard entry."""
        entry = LoudLeaderboardEntry.objects.select_related(
            'user', 'project'
        ).get(pk=pk)

        if request.method == 'POST':
            form = PointAdjustmentForm(request.POST)
            if form.is_valid():
                points = form.cleaned_data['points']
                reason = form.cleaned_data['reason']

                with transaction.atomic():
                    points_before = entry.total_points
                    points_after = max(0, points_before - points)

                    # Update leaderboard
                    entry.total_points = points_after
                    entry.save(update_fields=['total_points'])

                    # Create audit record
                    LoudPointAdjustment.objects.create(
                        leaderboard_entry=entry,
                        adjustment_type=LoudPointAdjustment.AdjustmentType.DEDUCTION,
                        points_change=-points,
                        reason=reason,
                        points_before=points_before,
                        points_after=points_after,
                        admin_user=request.user,
                    )

                    logger.warning(
                        "LOUD points adjusted by admin",
                        extra={
                            'admin_user': request.user.username,
                            'user_id': str(entry.user.id),
                            'project_id': str(entry.project.id),
                            'points_removed': points,
                            'points_before': points_before,
                            'points_after': points_after,
                            'reason': reason,
                        }
                    )

                messages.success(
                    request,
                    f"Adjusted points: {points_before} → {points_after} (-{points})"
                )
                return redirect('admin:loud_loudleaderboardentry_changelist')
        else:
            form = PointAdjustmentForm()

        # Get user's submissions for context
        submissions = LoudSubmission.objects.filter(
            user=entry.user,
            project=entry.project
        ).order_by('-submitted_at')

        context = {
            'title': f'Adjust Points: {entry.user.display_name}',
            'entry': entry,
            'form': form,
            'submissions': submissions,
            'opts': self.model._meta,
        }
        return render(request, 'admin/loud/adjust_points.html', context)


@admin.register(LoudPointAdjustment)
class LoudPointAdjustmentAdmin(admin.ModelAdmin):
    """Read-only audit log of all point adjustments."""
    list_display = [
        'created_at', 'user_display', 'project_display',
        'adjustment_type', 'points_change', 'admin_user', 'reason_preview'
    ]
    list_filter = ['adjustment_type', 'created_at']
    search_fields = [
        'leaderboard_entry__user__display_name',
        'leaderboard_entry__user__x_username',
        'reason'
    ]
    readonly_fields = [
        'id', 'leaderboard_entry', 'submission', 'adjustment_type',
        'points_change', 'reason', 'points_before', 'points_after',
        'admin_user', 'created_at'
    ]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # Audit logs should never be deleted

    def user_display(self, obj):
        return obj.leaderboard_entry.user.display_name
    user_display.short_description = 'User'

    def project_display(self, obj):
        return obj.leaderboard_entry.project.name
    project_display.short_description = 'Project'

    def reason_preview(self, obj):
        if len(obj.reason) > 50:
            return obj.reason[:50] + '...'
        return obj.reason
    reason_preview.short_description = 'Reason'
