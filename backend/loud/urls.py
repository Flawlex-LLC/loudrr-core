"""
URL routing for Loud API.
"""
from django.urls import path

from loud.views import LoudProjectsView, LoudSubmitView, LoudLeaderboardView

urlpatterns = [
    path('projects/', LoudProjectsView.as_view(), name='loud-projects'),
    path('submit/', LoudSubmitView.as_view(), name='loud-submit'),
    path('leaderboard/<slug:project_slug>/', LoudLeaderboardView.as_view(), name='loud-leaderboard'),
]
