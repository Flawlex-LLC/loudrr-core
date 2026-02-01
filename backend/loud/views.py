"""
API views for Loud feature.
"""
import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import status, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.services.settings import get_setting
from loud.models import LoudProject
from loud.services import LoudService, calculate_loud_points
from miniapp.views import MiniAppAuthMixin

logger = logging.getLogger(__name__)


# Schema serializers for documentation
class LoudProjectSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.SlugField()
    logo_url = serializers.URLField()
    description = serializers.CharField()
    ends_at = serializers.DateTimeField()
    time_remaining_hours = serializers.IntegerField()
    reward_pool = serializers.CharField()
    min_tweetscout_score = serializers.FloatField()
    max_submissions = serializers.IntegerField()
    user_submissions = serializers.IntegerField()
    can_submit = serializers.BooleanField()
    cannot_submit_reason = serializers.CharField(allow_null=True)
    total_participants = serializers.IntegerField()
    your_rank = serializers.IntegerField(allow_null=True)
    your_points = serializers.IntegerField()


class LoudProjectsResponseSerializer(serializers.Serializer):
    projects = LoudProjectSerializer(many=True)
    daily_submissions_remaining = serializers.IntegerField()
    daily_limit = serializers.IntegerField()
    expected_points = serializers.IntegerField()
    user_tweetscout_score = serializers.FloatField()


class LoudSubmitRequestSerializer(serializers.Serializer):
    project_id = serializers.UUIDField(help_text="Project ID to submit to")
    x_link = serializers.URLField(help_text="X/Twitter post link")


class LoudSubmitResponseSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    submission_id = serializers.UUIDField()
    points_awarded = serializers.IntegerField()
    new_total_points = serializers.IntegerField()
    new_rank = serializers.IntegerField()
    daily_submissions_remaining = serializers.IntegerField()
    project_submissions_remaining = serializers.IntegerField()


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    user_id = serializers.UUIDField()
    display_name = serializers.CharField()
    x_username = serializers.CharField()
    total_points = serializers.IntegerField()
    submission_count = serializers.IntegerField()


class LoudLeaderboardResponseSerializer(serializers.Serializer):
    project = serializers.DictField()
    leaderboard = LeaderboardEntrySerializer(many=True)
    user_entry = serializers.DictField(allow_null=True)
    total_participants = serializers.IntegerField()


class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class LoudSubmitThrottle(UserRateThrottle):
    """Rate limit LOUD submissions to 10 per minute per user."""
    rate = '10/minute'


@extend_schema_view(
    get=extend_schema(
        tags=["LOUD"],
        summary="List active LOUD projects",
        description="Returns live projects with user's submission counts and eligibility.",
        responses={
            200: LoudProjectsResponseSerializer,
            401: ErrorSerializer,
        },
    )
)
class LoudProjectsView(MiniAppAuthMixin, APIView):
    """
    GET /api/loud/projects/

    Returns live projects with user's submission counts and eligibility.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        service = LoudService(user)

        projects = service.get_live_projects()
        daily_limit = get_setting('LOUD_DAILY_LIMIT', 6)

        # Calculate expected points for this user
        score = user.tweetscout_score or 0
        expected_points = calculate_loud_points(score)

        projects_data = []
        for project in projects:
            can_submit, cannot_submit_reason = service.can_submit(project)
            user_entry = service.get_user_entry(project)
            stats = service.get_project_stats(project)

            # Calculate time remaining
            time_remaining = project.ends_at - timezone.now()
            time_remaining_hours = max(0, int(time_remaining.total_seconds() / 3600))

            projects_data.append({
                'id': str(project.id),
                'name': project.name,
                'slug': project.slug,
                'logo_url': project.logo_url,
                'description': project.description,
                'ends_at': project.ends_at.isoformat(),
                'time_remaining_hours': time_remaining_hours,
                'reward_pool': project.reward_pool,
                'min_tweetscout_score': project.min_tweetscout_score,
                'max_submissions': project.max_submissions_per_user,
                'user_submissions': user_entry['submission_count'] if user_entry else 0,
                'can_submit': can_submit,
                'cannot_submit_reason': cannot_submit_reason if not can_submit else None,
                'total_participants': stats['total_participants'],
                'your_rank': user_entry['rank'] if user_entry else None,
                'your_points': user_entry['total_points'] if user_entry else 0,
            })

        return Response({
            'projects': projects_data,
            'daily_submissions_remaining': service.get_daily_submissions_remaining(),
            'daily_limit': daily_limit,
            'expected_points': expected_points,
            'user_tweetscout_score': score,
        })


@extend_schema_view(
    post=extend_schema(
        tags=["LOUD"],
        summary="Submit content to LOUD project",
        description="Submit X/Twitter content to a LOUD project. Rate limited to 10/minute.",
        request=LoudSubmitRequestSerializer,
        responses={
            200: LoudSubmitResponseSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
            409: ErrorSerializer,
        },
    )
)
class LoudSubmitView(MiniAppAuthMixin, APIView):
    """
    POST /api/loud/submit/

    Submit content to a project.
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoudSubmitThrottle]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        service = LoudService(user)

        project_id = request.data.get('project_id')
        x_link = request.data.get('x_link')

        if not project_id:
            return Response(
                {'success': False, 'error': 'project_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not x_link:
            return Response(
                {'success': False, 'error': 'x_link is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get project
        try:
            project = LoudProject.objects.get(id=project_id, is_active=True)
        except LoudProject.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if project is still accepting submissions
        now = timezone.now()
        if project.ends_at <= now:
            return Response(
                {'success': False, 'error': 'This project has ended'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if project.starts_at > now:
            return Response(
                {'success': False, 'error': 'This project has not started yet'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            submission = service.submit(project, x_link)

            # Get updated stats
            user_entry = service.get_user_entry(project)

            return Response({
                'success': True,
                'submission_id': str(submission.id),
                'points_awarded': submission.points_awarded,
                'new_total_points': user_entry['total_points'] if user_entry else submission.points_awarded,
                'new_rank': user_entry['rank'] if user_entry else 1,
                'daily_submissions_remaining': service.get_daily_submissions_remaining(),
                'project_submissions_remaining': service.get_project_submissions_remaining(project),
            })

        except ValidationError as e:
            return Response(
                {'success': False, 'error': str(e.message if hasattr(e, 'message') else e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except IntegrityError:
            return Response(
                {'success': False, 'error': 'This post has already been submitted'},
                status=status.HTTP_409_CONFLICT
            )

        except Exception as e:
            logger.exception(
                "LOUD submit unexpected error",
                extra={
                    'user_id': str(user.id) if user else None,
                    'project_id': project_id,
                    'error_type': type(e).__name__,
                }
            )
            return Response(
                {'success': False, 'error': 'Something went wrong. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    get=extend_schema(
        tags=["LOUD"],
        summary="Get project leaderboard",
        description="Get leaderboard for a LOUD project with user's rank and stats.",
        parameters=[
            OpenApiParameter(name="project_slug", type=str, location="path", description="Project slug"),
        ],
        responses={
            200: LoudLeaderboardResponseSerializer,
            401: ErrorSerializer,
            404: ErrorSerializer,
        },
    )
)
class LoudLeaderboardView(MiniAppAuthMixin, APIView):
    """
    GET /api/loud/leaderboard/{project_slug}/

    Get project leaderboard.
    """
    permission_classes = [AllowAny]

    def get(self, request, project_slug):
        user = self.get_user_from_request(request)
        if not user:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        service = LoudService(user)

        # Get project
        try:
            project = LoudProject.objects.get(slug=project_slug)
        except LoudProject.DoesNotExist:
            return Response(
                {'error': 'Project not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        leaderboard = service.get_leaderboard(project, limit=50)
        user_entry = service.get_user_entry(project)
        stats = service.get_project_stats(project)

        return Response({
            'project': {
                'name': project.name,
                'slug': project.slug,
                'ends_at': project.ends_at.isoformat(),
                'reward_pool': project.reward_pool,
            },
            'leaderboard': leaderboard,
            'user_entry': user_entry,
            'total_participants': stats['total_participants'],
        })
