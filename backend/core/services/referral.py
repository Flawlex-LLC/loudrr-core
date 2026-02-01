"""
Referral Service for Loudrr.

Handles all referral-related business logic:
- Code validation
- Referrer linking
- Referral count tracking

Usage:
    from core.services.referral import ReferralService

    # Validate and link referrer to waitlist entry
    ReferralService.link_referrer_to_entry(entry, "ABC123")

    # Increment count when referee is approved
    ReferralService.increment_referral_count(entry)

    # Get referral links
    links = ReferralService.get_referral_links(user)
"""
import logging
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.db.models import F

from core.invariants import check_precondition, check_postcondition
from core.models import User, WaitlistEntry

logger = logging.getLogger(__name__)


class ReferralService:
    """Service layer for referral operations."""

    @staticmethod
    def validate_referral_code(code: str) -> Optional[User]:
        """
        Validate a referral code and return the referrer.

        Args:
            code: The referral code to validate

        Returns:
            User if valid, None otherwise
        """
        if not code or not code.strip():
            return None

        code = code.strip().upper()

        try:
            referrer = User.objects.get(
                referral_code=code,
                is_whitelisted=True,
                is_banned=False
            )
            logger.info(
                "referral_code_validated",
                extra={"code": code, "referrer_id": str(referrer.id)}
            )
            return referrer
        except User.DoesNotExist:
            logger.info(
                "referral_code_invalid",
                extra={"code": code}
            )
            return None

    @staticmethod
    def link_referrer_to_entry(
        entry: WaitlistEntry,
        referral_code: str
    ) -> bool:
        """
        Link a referrer to a waitlist entry.

        Called during waitlist registration. Does NOT increment count yet
        (that happens on approval via signal).

        Args:
            entry: The WaitlistEntry to link
            referral_code: The referral code used

        Returns:
            True if linked successfully, False otherwise
        """
        check_precondition(entry is not None, "Entry cannot be None")

        if not referral_code:
            return False

        code = referral_code.strip().upper()

        # Can't use your own referral code
        if entry.telegram_id:
            try:
                existing_user = User.objects.get(telegram_id=entry.telegram_id)
                if existing_user.referral_code == code:
                    logger.warning(
                        "self_referral_attempt",
                        extra={
                            "entry_id": str(entry.id),
                            "code": code
                        }
                    )
                    return False
            except User.DoesNotExist:
                pass

        # Validate referrer
        referrer = ReferralService.validate_referral_code(code)
        if not referrer:
            return False

        # Link referrer
        entry.referrer = referrer
        entry.referral_code_used = code
        entry.save(update_fields=['referrer', 'referral_code_used', 'updated_at'])

        logger.info(
            "referrer_linked",
            extra={
                "entry_id": str(entry.id),
                "referrer_id": str(referrer.id),
                "code": code
            }
        )
        return True

    @staticmethod
    @transaction.atomic
    def increment_referral_count(entry: WaitlistEntry) -> bool:
        """
        Increment referrer's total_referrals when referee is approved.

        Uses select_for_update() to prevent race conditions.
        Also links the created_user to the referrer.

        Args:
            entry: The approved WaitlistEntry

        Returns:
            True if incremented, False if no referrer
        """
        check_precondition(entry is not None, "Entry cannot be None")
        check_precondition(
            entry.status == WaitlistEntry.Status.APPROVED,
            "Entry must be approved"
        )

        if not entry.referrer_id:
            return False

        # Lock referrer row to prevent concurrent updates
        referrer = User.objects.select_for_update().get(id=entry.referrer_id)
        count_before = referrer.total_referrals

        # Link created user to referrer
        if entry.created_user:
            entry.created_user.referred_by = referrer
            entry.created_user.save(update_fields=['referred_by', 'updated_at'])

        # Atomic increment using F()
        User.objects.filter(id=referrer.id).update(
            total_referrals=F('total_referrals') + 1
        )

        # Verify postcondition
        referrer.refresh_from_db()
        check_postcondition(
            referrer.total_referrals == count_before + 1,
            f"Referral count mismatch: expected {count_before + 1}, got {referrer.total_referrals}",
            {"referrer_id": str(referrer.id)}
        )

        logger.info(
            "referral_count_incremented",
            extra={
                "referrer_id": str(referrer.id),
                "referee_entry_id": str(entry.id),
                "new_count": referrer.total_referrals
            }
        )
        return True

    @staticmethod
    def get_referral_links(user: User) -> dict:
        """
        Get shareable referral links for a user.

        Args:
            user: The user to get links for

        Returns:
            Dict with web and telegram links
        """
        check_precondition(user is not None, "User cannot be None")

        code = user.referral_code
        landing_url = getattr(settings, 'LANDING_URL', 'https://loudrr.com')
        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'loudrr_bot')

        return {
            'code': code,
            'web': f"{landing_url}?ref={code}",
            'telegram': f"https://t.me/{bot_username}?start=ref_{code}",
        }

    @staticmethod
    def get_referral_stats(user: User) -> dict:
        """
        Get referral statistics for a user.

        Args:
            user: The user to get stats for

        Returns:
            Dict with code, counts, and links
        """
        check_precondition(user is not None, "User cannot be None")

        links = ReferralService.get_referral_links(user)

        return {
            'referral_code': user.referral_code,
            'total_referrals': user.total_referrals,
            'was_referred': user.referred_by_id is not None,
            'links': links,
        }
