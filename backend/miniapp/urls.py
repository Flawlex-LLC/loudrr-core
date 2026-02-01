from django.urls import path

from . import views

urlpatterns = [
    # Health check
    path("health/", views.HealthCheckView.as_view(), name="miniapp-health"),

    # App settings (for frontend)
    path("settings/", views.SettingsView.as_view(), name="miniapp-settings"),

    # Waitlist (public, no auth)
    path("waitlist/submit/", views.WaitlistSubmitView.as_view(), name="waitlist-submit"),
    path("waitlist/register/", views.WaitlistRegisterView.as_view(), name="waitlist-register"),
    path("waitlist/complete/", views.WaitlistCompleteView.as_view(), name="waitlist-complete"),
    path("waitlist/status/", views.WaitlistStatusView.as_view(), name="waitlist-status"),
    path("waitlist/entry/", views.WaitlistEntryView.as_view(), name="waitlist-entry"),

    # Onboarding
    path("onboarding/complete/", views.CompleteOnboardingView.as_view(), name="onboarding-complete"),

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

    # Feature interest registration
    path("feature-interest/", views.FeatureInterestView.as_view(), name="miniapp-feature-interest"),

    # Referral system
    path("referral/", views.ReferralInfoView.as_view(), name="referral-info"),
]
