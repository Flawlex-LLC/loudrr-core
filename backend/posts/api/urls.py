from django.urls import path

from . import views

urlpatterns = [
    # Posts
    path("", views.PostListCreateView.as_view(), name="post-list-create"),
    path("<uuid:pk>/", views.PostDetailView.as_view(), name="post-detail"),
    path("<uuid:pk>/engagements/", views.PostEngagementsView.as_view(), name="post-engagements"),
    # Feed
    path("feed/", views.FeedView.as_view(), name="feed"),
    # User's engagements
    path("engagements/", views.UserEngagementsView.as_view(), name="user-engagements"),
]
