from django.urls import path

from . import views

urlpatterns = [
    # Health check
    path("health/", views.HealthCheckView.as_view(), name="miniapp-health"),

    # App settings (for frontend)
    path("settings/", views.SettingsView.as_view(), name="miniapp-settings"),

    # Mini App API endpoints
    path("user/", views.UserInfoView.as_view(), name="miniapp-user"),
    path("user/stats/", views.UserStatsView.as_view(), name="miniapp-user-stats"),
    path("user/link-x/", views.LinkXAccountView.as_view(), name="miniapp-link-x"),
    path("post/submit/", views.SubmitPostView.as_view(), name="miniapp-submit-post"),
    path("session/start/", views.StartSessionView.as_view(), name="miniapp-start-session"),
    path("session/click/", views.RecordClickView.as_view(), name="miniapp-record-click"),
    path("session/verify-return/", views.VerifyReturnView.as_view(), name="miniapp-verify-return"),
    path("session/complete/", views.CompleteSessionView.as_view(), name="miniapp-complete-session"),

    # Queue-based verification (like spot trading)
    path("session/queue-claim/", views.QueueClaimView.as_view(), name="miniapp-queue-claim"),
    path("claims/history/", views.ClaimHistoryView.as_view(), name="miniapp-claim-history"),
]
