"""
Custom authentication backends for Loudrr admin.
"""
from django.contrib.auth.backends import BaseBackend
from core.models import User


class TelegramIDBackend(BaseBackend):
    """
    Authenticate users via telegram_id instead of UUID.

    This makes admin login much easier - just use telegram ID as username.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        try:
            # Try to parse as telegram_id (integer)
            telegram_id = int(username)
            user = User.objects.get(telegram_id=telegram_id)

            if user.check_password(password) and user.is_active:
                return user
        except (ValueError, User.DoesNotExist):
            return None

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
