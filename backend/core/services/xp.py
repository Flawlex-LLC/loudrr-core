"""
XP (Experience Points) service.

Handles all XP operations for sponsored post engagements.
XP is a non-spendable reputation score used for giveaway eligibility.

ROBUSTNESS GUARANTEES:
- All operations use select_for_update() for row-level locking
- Every XP change creates an XPTransaction record (audit trail)
- No success returned until DB commit completes
"""
import logging
from django.db import transaction

from core.models import User, XPTransaction
from core.services.settings import get_setting

logger = logging.getLogger(__name__)


class XPService:
    """
    Service for managing user XP (experience points).

    XP is separate from credits:
    - Non-spendable (cannot be used to pay for posts)
    - Earned only from sponsored post engagements
    - Used for giveaway/campaign eligibility

    ROBUSTNESS: All XP operations are atomic with proper locking.
    """

    def __init__(self, user: User):
        self.user = user

    def get_balance(self) -> int:
        """Get current XP balance."""
        return self.user.sponsored_xp

    def get_total_earned(self) -> int:
        """Get lifetime XP earned."""
        return self.user.total_sponsored_xp_earned

    def get_sponsored_engagements(self) -> int:
        """Get count of sponsored post engagements."""
        return self.user.sponsored_engagements

    @transaction.atomic
    def earn_from_sponsored(
        self,
        amount: int,
        post_id,
        description: str = "",
    ) -> XPTransaction:
        """
        Award XP for sponsored post engagement.

        Called when a user engages with a sponsored post (is_sponsored=True).

        Args:
            amount: XP to award (typically from SPONSORED_XP_PER_ENGAGEMENT)
            post_id: ID of the sponsored post
            description: Description of the transaction

        Returns:
            XPTransaction record
        """
        # Lock user row for atomic update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update XP fields
        user.sponsored_xp += amount
        user.total_sponsored_xp_earned += amount
        user.sponsored_engagements += 1
        user.save(update_fields=[
            'sponsored_xp',
            'total_sponsored_xp_earned',
            'sponsored_engagements',
            'updated_at'
        ])

        # Refresh our reference
        self.user.refresh_from_db()

        # Create audit trail
        xp_transaction = XPTransaction.objects.create(
            user=user,
            type=XPTransaction.Type.EARNED,
            amount=amount,
            balance_after=user.sponsored_xp,
            reference_id=post_id,
            reference_type='sponsored_post',
            description=description or f"Earned {amount} XP from sponsored post",
        )

        logger.info(
            f"XP earned: user={user.pk}, amount={amount}, "
            f"new_balance={user.sponsored_xp}, post={post_id}"
        )

        return xp_transaction

    @transaction.atomic
    def admin_grant(
        self,
        amount: int,
        admin_user,
        description: str = "",
    ) -> XPTransaction:
        """
        Admin grants XP to user.

        Args:
            amount: XP to grant (must be positive)
            admin_user: Admin user performing the action
            description: Reason for grant

        Returns:
            XPTransaction record
        """
        if amount <= 0:
            raise ValueError("Grant amount must be positive")

        # Lock user row
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update XP
        user.sponsored_xp += amount
        user.total_sponsored_xp_earned += amount
        user.save(update_fields=[
            'sponsored_xp',
            'total_sponsored_xp_earned',
            'updated_at'
        ])

        # Refresh our reference
        self.user.refresh_from_db()

        # Create audit trail
        admin_name = getattr(admin_user, 'display_name', str(admin_user))
        xp_transaction = XPTransaction.objects.create(
            user=user,
            type=XPTransaction.Type.ADMIN_GRANT,
            amount=amount,
            balance_after=user.sponsored_xp,
            reference_id=getattr(admin_user, 'pk', None),
            reference_type='admin_grant',
            description=description or f"Admin grant by {admin_name}",
        )

        logger.info(
            f"XP admin grant: user={user.pk}, amount={amount}, "
            f"admin={admin_name}, new_balance={user.sponsored_xp}"
        )

        return xp_transaction

    @transaction.atomic
    def admin_revoke(
        self,
        amount: int,
        admin_user,
        description: str = "",
    ) -> XPTransaction:
        """
        Admin revokes XP from user.

        XP cannot go below 0.

        Args:
            amount: XP to revoke (must be positive, will be stored as negative)
            admin_user: Admin user performing the action
            description: Reason for revoke

        Returns:
            XPTransaction record
        """
        if amount <= 0:
            raise ValueError("Revoke amount must be positive")

        # Lock user row
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Calculate actual amount to revoke (don't go below 0)
        actual_amount = min(amount, user.sponsored_xp)
        if actual_amount == 0:
            logger.warning(f"XP revoke skipped: user={user.pk} already has 0 XP")
            # Still create a record for audit purposes
            actual_amount = 0

        # Update XP
        user.sponsored_xp = max(0, user.sponsored_xp - amount)
        user.save(update_fields=['sponsored_xp', 'updated_at'])

        # Refresh our reference
        self.user.refresh_from_db()

        # Create audit trail (negative amount for revoke)
        admin_name = getattr(admin_user, 'display_name', str(admin_user))
        xp_transaction = XPTransaction.objects.create(
            user=user,
            type=XPTransaction.Type.ADMIN_REVOKE,
            amount=-actual_amount,  # Negative for revoke
            balance_after=user.sponsored_xp,
            reference_id=getattr(admin_user, 'pk', None),
            reference_type='admin_revoke',
            description=description or f"Admin revoke by {admin_name}",
        )

        logger.info(
            f"XP admin revoke: user={user.pk}, amount=-{actual_amount}, "
            f"admin={admin_name}, new_balance={user.sponsored_xp}"
        )

        return xp_transaction

    @transaction.atomic
    def award_bonus(
        self,
        amount: int,
        reason: str,
        reference_id=None,
        reference_type: str = "bonus",
    ) -> XPTransaction:
        """
        Award bonus XP (for promotions, achievements, etc.).

        Args:
            amount: Bonus XP to award
            reason: Description of why bonus was awarded
            reference_id: Optional reference to related object
            reference_type: Type of bonus

        Returns:
            XPTransaction record
        """
        if amount <= 0:
            raise ValueError("Bonus amount must be positive")

        # Lock user row
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update XP
        user.sponsored_xp += amount
        user.total_sponsored_xp_earned += amount
        user.save(update_fields=[
            'sponsored_xp',
            'total_sponsored_xp_earned',
            'updated_at'
        ])

        # Refresh our reference
        self.user.refresh_from_db()

        # Create audit trail
        xp_transaction = XPTransaction.objects.create(
            user=user,
            type=XPTransaction.Type.BONUS,
            amount=amount,
            balance_after=user.sponsored_xp,
            reference_id=reference_id,
            reference_type=reference_type,
            description=reason,
        )

        logger.info(
            f"XP bonus: user={user.pk}, amount={amount}, "
            f"reason={reason}, new_balance={user.sponsored_xp}"
        )

        return xp_transaction


def get_xp_for_sponsored_engagement() -> int:
    """Get XP amount awarded per sponsored engagement from settings."""
    return get_setting('SPONSORED_XP_PER_ENGAGEMENT')
