"""
Mini App models.

Note: EngagementSession and SessionClick models were removed.
The engagement flow now uses the Engagement model from posts.models directly,
with user-level progress tracking (verified=False) instead of session-based tracking.
This is more robust for Telegram Mini Apps where frontend state can be lost.
"""
import secrets


def generate_session_token():
    """
    Stub function kept for migration compatibility.
    Referenced by 0001_initial.py but no longer used.
    """
    return secrets.token_urlsafe(32)


# No models needed - engagement tracking uses posts.Engagement directly
