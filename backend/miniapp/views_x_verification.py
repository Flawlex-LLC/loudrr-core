"""X (Twitter) OAuth verification views.

Flow:
1. User opens mini app post-approval, x_verified=False
   -> Mini app shows "Connect X" button
2. Button click -> POST /api/miniapp/x-oauth/start/
   -> returns {authorize_url}
3. Mini app opens authorize_url in external browser via Telegram WebApp.openLink
4. User authenticates with X
5. X redirects to /api/auth/x/callback/?code&state (in user's external browser)
6. Callback exchanges code, fetches users/me:
   - If username matches -> set user.x_verified=True
   - If mismatch -> store on user.pending_claimed_x_username, mini app
     prompts user to either confirm (creates XVerificationRequest) or retry
7. Mini app polls /api/miniapp/user/ and reacts to the new state
"""
import logging
from urllib.parse import quote_plus

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from rest_framework import status as drf_status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import User, XVerificationRequest
from core.services.x_oauth import (
    build_authorize_url,
    consume_state,
    exchange_code_for_token,
    fetch_me,
)
from .views import MiniAppAuthMixin

logger = logging.getLogger(__name__)


class XOAuthStartView(MiniAppAuthMixin, APIView):
    """Generate an X OAuth authorize URL for the current user.

    Only allowed when the user is approved and not yet verified.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response({"error": "Invalid authentication"},
                            status=drf_status.HTTP_401_UNAUTHORIZED)
        if user.is_banned:
            return Response({"error": "Account suspended"},
                            status=drf_status.HTTP_403_FORBIDDEN)
        if user.x_verified:
            return Response({"error": "Already verified"},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        try:
            url = build_authorize_url(user_id=str(user.id))
        except RuntimeError as e:
            logger.error("[X-OAUTH] start failed: %s", e)
            return Response({"error": "X OAuth not configured"},
                            status=drf_status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({"authorize_url": url})


class ConfirmMismatchView(MiniAppAuthMixin, APIView):
    """User confirms 'yes the X account I logged into is mine'. Create an
    XVerificationRequest for admin review and clear pending state."""
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response({"error": "Invalid authentication"},
                            status=drf_status.HTTP_401_UNAUTHORIZED)

        claimed_username = user.pending_claimed_x_username
        claimed_user_id = user.pending_claimed_x_user_id
        if not claimed_username:
            return Response({"error": "No pending mismatch to confirm"},
                            status=drf_status.HTTP_400_BAD_REQUEST)

        # Avoid duplicate pending requests
        existing = XVerificationRequest.objects.filter(
            user=user, status=XVerificationRequest.Status.PENDING
        ).first()
        if not existing:
            XVerificationRequest.objects.create(
                user=user,
                submitted_x_username=user.x_username or "",
                claimed_x_username=claimed_username,
                claimed_x_user_id=claimed_user_id,
            )

        # Clear the prompt state — the user has decided
        user.pending_claimed_x_username = ""
        user.pending_claimed_x_user_id = ""
        user.save(update_fields=["pending_claimed_x_username", "pending_claimed_x_user_id"])

        return Response({"status": "pending_review"})


class CancelMismatchView(MiniAppAuthMixin, APIView):
    """User says 'no, that wasn't my real account' — clear pending state so
    they're shown the Connect X screen again to retry."""
    permission_classes = [AllowAny]

    def post(self, request):
        user = self.get_user_from_request(request)
        if not user:
            return Response({"error": "Invalid authentication"},
                            status=drf_status.HTTP_401_UNAUTHORIZED)

        user.pending_claimed_x_username = ""
        user.pending_claimed_x_user_id = ""
        user.save(update_fields=["pending_claimed_x_username", "pending_claimed_x_user_id"])
        return Response({"status": "cleared"})


# === OAuth callback (public — receives X redirect in user's external browser) ===


def _callback_html(title: str, message: str, success: bool = True) -> str:
    color = "#22c55e" if success else "#ef4444"
    accent = "#f95400"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title} — Loudrr</title>
<style>
  *{{box-sizing:border-box}}
  body{{margin:0;background:#08080a;color:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;}}
  .card{{max-width:420px;width:100%;background:linear-gradient(180deg,#0e0e10,#08080a);
        border:1px solid rgba(255,255,255,0.1);border-radius:24px;padding:40px 28px;text-align:center;}}
  .badge{{width:64px;height:64px;border-radius:50%;background:{color}22;color:{color};
         display:inline-flex;align-items:center;justify-content:center;font-size:32px;margin-bottom:18px;font-weight:700;}}
  h1{{margin:0 0 10px;font-size:22px;letter-spacing:-0.5px;}}
  p{{margin:0;color:rgba(255,255,255,0.7);font-size:15px;line-height:1.5;}}
  .brand{{margin-top:22px;font-weight:700;color:{accent};letter-spacing:1px;font-size:14px;}}
</style></head>
<body><div class="card">
  <div class="badge">{"✓" if success else "!"}</div>
  <h1>{title}</h1>
  <p>{message}</p>
  <div class="brand">Return to Loudrr in Telegram</div>
</div></body></html>"""


@csrf_exempt
@require_GET
def x_oauth_callback(request):
    """X redirects here after user authorizes (or denies). Runs in user's
    external browser, not the Telegram mini app."""
    # User denied or X errored
    err = request.GET.get("error")
    if err:
        return HttpResponse(_callback_html(
            "Authorization Cancelled",
            "You cancelled the connection. Open Loudrr again to retry.",
            success=False,
        ), status=400)

    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code or not state:
        return HttpResponse(_callback_html(
            "Invalid Request",
            "Missing authorization code. Try connecting again from Loudrr.",
            success=False,
        ), status=400)

    record = consume_state(state)
    if record is None:
        return HttpResponse(_callback_html(
            "Session Expired",
            "Your verification link expired. Open Loudrr again to retry.",
            success=False,
        ), status=400)

    try:
        user = User.objects.get(id=record["user_id"])
    except User.DoesNotExist:
        return HttpResponse(_callback_html(
            "Account Not Found",
            "Something went wrong. Open Loudrr again.",
            success=False,
        ), status=404)

    # Exchange code -> token -> /users/me
    token = exchange_code_for_token(code, record["code_verifier"])
    if not token:
        return HttpResponse(_callback_html(
            "Connection Failed",
            "Couldn't connect to X. Try again from Loudrr.",
            success=False,
        ), status=502)

    me = fetch_me(token)
    if not me or not me.get("username") or not me.get("id"):
        return HttpResponse(_callback_html(
            "Couldn't Read Profile",
            "X didn't return your profile info. Try again from Loudrr.",
            success=False,
        ), status=502)

    claimed_username = me["username"]
    claimed_id = str(me["id"])
    submitted_username = (user.x_username or "").lstrip("@")

    if submitted_username and claimed_username.lower() == submitted_username.lower():
        # Match — mark verified
        user.x_username = claimed_username  # canonical case
        user.x_verified = True
        user.x_verified_at = timezone.now()
        user.pending_claimed_x_username = ""
        user.pending_claimed_x_user_id = ""
        user.save(update_fields=[
            "x_username", "x_verified", "x_verified_at",
            "pending_claimed_x_username", "pending_claimed_x_user_id",
        ])
        logger.info("[X-OAUTH] user %s verified as @%s", user.id, claimed_username)
        return HttpResponse(_callback_html(
            "Connected!",
            f"@{claimed_username} is verified. Return to Loudrr in Telegram to continue.",
            success=True,
        ))

    # Mismatch — store pending claim, mini app will prompt the user
    user.pending_claimed_x_username = claimed_username
    user.pending_claimed_x_user_id = claimed_id
    user.save(update_fields=["pending_claimed_x_username", "pending_claimed_x_user_id"])
    logger.info(
        "[X-OAUTH] mismatch for user %s: submitted=@%s claimed=@%s",
        user.id, submitted_username, claimed_username,
    )
    return HttpResponse(_callback_html(
        "Different Account Detected",
        f"You signed up with @{submitted_username} but logged into @{claimed_username}. "
        "Return to Loudrr in Telegram — we'll ask you what to do next.",
        success=True,
    ))
