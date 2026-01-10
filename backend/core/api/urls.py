from django.urls import path

from . import views

urlpatterns = [
    # User endpoints
    path("users/", views.CreateUserView.as_view(), name="create-user"),
    path("users/me/", views.CurrentUserView.as_view(), name="current-user"),
    path("users/me/balance/", views.BalanceView.as_view(), name="user-balance"),
    path("users/me/stats/", views.UserStatsView.as_view(), name="user-stats"),
    path("users/me/transactions/", views.TransactionHistoryView.as_view(), name="user-transactions"),
    path("users/me/link/", views.LinkAccountView.as_view(), name="link-account"),
    # Leaderboard
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
]
