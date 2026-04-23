"""X (Twitter) OAuth 2.0 service.

Implements the Authorization Code flow with PKCE for verifying that a user
controls the X account they submitted on the waitlist. We don't keep the
access token long-term; we only need the username + user_id from /users/me
once to confirm ownership.

References:
- https://developer.x.com/en/docs/authentication/oauth-2-0/authorization-code
- https://datatracker.ietf.org/doc/html/rfc7636 (PKCE)
"""
import base64
import hashlib
import logging
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
USERS_ME_URL = "https://api.twitter.com/2/users/me"

# Scopes we need: read user info to confirm identity.
SCOPES = "users.read tweet.read"

# How long the authorize state stays valid (10 min).
STATE_TTL_SECONDS = 600


def _b64url_no_pad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _make_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge)."""
    verifier = _b64url_no_pad(secrets.token_bytes(48))
    challenge = _b64url_no_pad(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _state_cache_key(state: str) -> str:
    return f"x_oauth:state:{state}"


def build_authorize_url(user_id: str) -> str:
    """Generate an X OAuth authorize URL for the given Loudrr user.

    Stores the state + PKCE verifier in cache, keyed by state. Callback uses
    state to look back up the user_id and exchange the code.

    Returns the URL the user should be redirected to.
    """
    if not settings.X_OAUTH_CLIENT_ID:
        raise RuntimeError("X_OAUTH_CLIENT_ID not configured")

    state = secrets.token_urlsafe(32)
    verifier, challenge = _make_pkce()

    cache.set(
        _state_cache_key(state),
        {"user_id": str(user_id), "code_verifier": verifier},
        timeout=STATE_TTL_SECONDS,
    )

    params = {
        "response_type": "code",
        "client_id": settings.X_OAUTH_CLIENT_ID,
        "redirect_uri": settings.X_OAUTH_CALLBACK_URL,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def consume_state(state: str) -> Optional[dict]:
    """Look up and delete the state record. Returns dict with user_id+code_verifier
    or None if state is missing/expired."""
    key = _state_cache_key(state)
    record = cache.get(key)
    if record is None:
        return None
    cache.delete(key)
    return record


def exchange_code_for_token(code: str, code_verifier: str) -> Optional[str]:
    """Exchange an authorization code for an access token. Returns the token
    string on success, None on failure (logged)."""
    auth_header = base64.b64encode(
        f"{settings.X_OAUTH_CLIENT_ID}:{settings.X_OAUTH_CLIENT_SECRET}".encode()
    ).decode("ascii")

    body = {
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.X_OAUTH_CALLBACK_URL,
        "code_verifier": code_verifier,
        "client_id": settings.X_OAUTH_CLIENT_ID,
    }
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        with httpx.Client(timeout=20) as client:
            r = client.post(TOKEN_URL, data=body, headers=headers)
        if r.status_code != 200:
            logger.warning(
                "[X-OAUTH] token exchange failed: %s %s", r.status_code, r.text[:300]
            )
            return None
        return r.json().get("access_token")
    except Exception:
        logger.exception("[X-OAUTH] token exchange exception")
        return None


def fetch_me(access_token: str) -> Optional[dict]:
    """Fetch the authenticated user's profile from X. Returns dict with
    {'id': str, 'username': str, 'name': str} or None on failure."""
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(USERS_ME_URL, headers=headers)
        if r.status_code != 200:
            logger.warning(
                "[X-OAUTH] users/me failed: %s %s", r.status_code, r.text[:300]
            )
            return None
        return r.json().get("data") or None
    except Exception:
        logger.exception("[X-OAUTH] users/me exception")
        return None
