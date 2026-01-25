"""
Credit system service.

Handles all credit operations: earning, spending, refunds, penalties.
All operations are atomic and create transaction records.

ROBUSTNESS GUARANTEES:
- All operations use select_for_update() for row-level locking
- Daily reset checks happen INSIDE the locked section
- Every credit change creates a Transaction record (audit trail)
- No success returned until DB commit completes

NOTE: TweetScout multipliers are applied in calculate_engagement_karma()
before calling earn(). This service receives pre-calculated amounts.

DECIMAL KARMA SYSTEM:
- All amounts are Decimal with 4 decimal places
- Use Decimal('0') instead of 0 for comparisons
- Daily cap comparison works with Decimal
"""
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Transaction, User
from core.services.settings import get_setting


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits."""
    pass


class DailyCapReachedError(Exception):
    """Raised when user has reached daily earning cap."""
    pass


class CreditService:
    """
    Service for managing user credits.

    ROBUSTNESS: All credit operations are atomic with proper locking.

    Uses dynamic settings from database (with fallback to ECHO_CONFIG).
    """

    def __init__(self, user: User):
        self.user = user

    def get_balance(self) -> Decimal:
        """Get current credit balance."""
        return self.user.credits

    def get_daily_remaining(self) -> Decimal:
        """Get remaining credits that can be earned today."""
        self._check_daily_reset()
        daily_cap = Decimal(str(get_setting('DAILY_EARN_CAP')))
        return max(Decimal('0'), daily_cap - self.user.daily_credits_earned)

    def can_earn(self, amount: Decimal = Decimal('1')) -> bool:
        """Check if user can earn more credits today."""
        self._check_daily_reset()
        daily_cap = Decimal(str(get_setting('DAILY_EARN_CAP')))
        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        return self.user.daily_credits_earned + amount <= daily_cap

    def can_spend(self, amount: Decimal) -> bool:
        """Check if user has enough credits to spend."""
        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        return self.user.credits >= amount

    @transaction.atomic
    def earn(
        self,
        amount: Decimal,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
        idempotency_key: str = "",
    ) -> Transaction:
        """
        Grant credits to user for engagement.

        ROBUSTNESS:
        - Locks user row FIRST, then checks daily reset
        - Prevents race condition where two requests both reset counter
        - Idempotency key prevents duplicate transactions from retries

        NOTE: TweetScout multipliers are applied in calculate_engagement_karma()
        BEFORE calling this method. This method receives the final amount.

        Args:
            amount: Amount of credits to earn (Decimal, already multiplied if applicable)
            reference_id: ID of related object (engagement, post, etc.)
            reference_type: Type of reference object
            description: Description of transaction
            idempotency_key: Unique key for deduplication (use engagement_id for engagements)

        Returns:
            Transaction record (existing if idempotent retry, new otherwise)

        Raises:
            DailyCapReachedError: If daily cap would be exceeded
        """
        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        # Generate idempotency key from reference_id if not provided
        if not idempotency_key and reference_id:
            idempotency_key = str(reference_id)

        # Check for existing transaction with same idempotency key (prevents duplicates)
        if idempotency_key:
            existing = Transaction.objects.filter(
                user=self.user,
                type=Transaction.Type.EARNED,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                # Idempotent retry - return existing transaction
                return existing

        # LOCK USER ROW FIRST - critical for preventing race conditions
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Check daily reset INSIDE the lock
        now = timezone.now()
        if user.daily_earned_reset_at.date() < now.date():
            user.daily_credits_earned = Decimal('0')
            user.daily_earned_reset_at = now

        # Use amount directly - multipliers already applied by caller
        final_amount = amount

        # Get daily cap from dynamic settings
        daily_cap = Decimal(str(get_setting('DAILY_EARN_CAP')))

        # Check daily cap (on locked user data)
        if user.daily_credits_earned + final_amount > daily_cap:
            # Cap at remaining daily limit
            final_amount = daily_cap - user.daily_credits_earned
            if final_amount <= Decimal('0'):
                raise DailyCapReachedError("Daily earning cap reached")

        # Update user credits
        user.credits += final_amount
        user.total_credits_earned += final_amount
        user.daily_credits_earned += final_amount
        user.save(update_fields=[
            "credits", "total_credits_earned", "daily_credits_earned",
            "daily_earned_reset_at", "updated_at"
        ])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record (audit trail) with idempotency key
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.EARNED,
            amount=final_amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            idempotency_key=idempotency_key,
            description=description or f"Earned {float(final_amount):.2f} credits",
        )

    @transaction.atomic
    def spend(
        self,
        amount: Decimal,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
        idempotency_key: str = "",
    ) -> Transaction:
        """
        Deduct credits from user for posting.

        Args:
            amount: Amount of credits to spend (Decimal)
            reference_id: ID of related object (post)
            reference_type: Type of reference object
            description: Description of transaction
            idempotency_key: Unique key for deduplication (use post_id for posts)

        Returns:
            Transaction record (existing if idempotent retry, new otherwise)

        Raises:
            InsufficientCreditsError: If user doesn't have enough credits
        """
        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if amount <= Decimal('0'):
            raise ValueError("Amount must be positive")

        # Generate idempotency key from reference_id if not provided
        if not idempotency_key and reference_id:
            idempotency_key = str(reference_id)

        # Check for existing transaction with same idempotency key (prevents duplicates)
        if idempotency_key:
            existing = Transaction.objects.filter(
                user=self.user,
                type=Transaction.Type.SPENT,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                # Idempotent retry - return existing transaction
                return existing

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        if user.credits < amount:
            raise InsufficientCreditsError(
                f"Insufficient credits. Have {float(user.credits):.2f}, need {float(amount):.2f}"
            )

        # Update user credits
        user.credits -= amount
        user.total_credits_spent += amount
        user.save(update_fields=["credits", "total_credits_spent", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record (audit trail) with idempotency key
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.SPENT,
            amount=-amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            idempotency_key=idempotency_key,
            description=description or f"Spent {float(amount):.2f} credits",
        )

    @transaction.atomic
    def refund(
        self,
        amount: Decimal,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
        idempotency_key: str = "",
    ) -> Transaction:
        """
        Refund credits to user (e.g., cancelled post).

        Args:
            amount: Amount of credits to refund (Decimal)
            reference_id: ID of related object
            reference_type: Type of reference object
            description: Description of refund
            idempotency_key: Unique key for deduplication

        Returns:
            Transaction record (existing if idempotent retry, new otherwise)
        """
        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if amount <= Decimal('0'):
            raise ValueError("Amount must be positive")

        # Generate idempotency key from reference_id if not provided
        if not idempotency_key and reference_id:
            idempotency_key = f"refund_{reference_id}"

        # Check for existing transaction with same idempotency key (prevents duplicates)
        if idempotency_key:
            existing = Transaction.objects.filter(
                user=self.user,
                type=Transaction.Type.REFUND,
                idempotency_key=idempotency_key,
            ).first()
            if existing:
                # Idempotent retry - return existing transaction
                return existing

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update user credits
        user.credits += amount
        # Don't update total_credits_spent - refund doesn't undo the original spend
        user.save(update_fields=["credits", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record (audit trail) with idempotency key
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.REFUND,
            amount=amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            idempotency_key=idempotency_key,
            description=description or f"Refunded {float(amount):.2f} credits",
        )

    @transaction.atomic
    def apply_penalty(
        self,
        amount: Decimal,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
    ) -> Transaction:
        """
        Apply penalty to user (e.g., failed audit).

        Args:
            amount: Amount of credits to deduct as penalty (Decimal)
            reference_id: ID of related object (audit)
            reference_type: Type of reference object
            description: Description of penalty

        Returns:
            Transaction record
        """
        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if amount <= Decimal('0'):
            raise ValueError("Amount must be positive")

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Deduct credits (can go negative as penalty)
        user.credits -= amount
        user.save(update_fields=["credits", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record (audit trail)
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.PENALTY,
            amount=-amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description or f"Penalty of {float(amount):.2f} credits",
        )

    @transaction.atomic
    def admin_grant(
        self,
        amount: Decimal,
        admin_id: int,
        description: str = "",
    ) -> Transaction:
        """
        Admin grants credits to user (bypasses daily cap).

        Args:
            amount: Amount of credits to grant (Decimal)
            admin_id: Telegram ID of admin granting credits
            description: Description of grant

        Returns:
            Transaction record
        """
        # Ensure amount is Decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if amount <= Decimal('0'):
            raise ValueError("Amount must be positive")

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update user credits
        user.credits += amount
        user.save(update_fields=["credits", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record (audit trail)
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.ADMIN_GRANT,
            amount=amount,
            balance_after=user.credits,
            reference_type="admin_grant",
            description=description or f"Admin {admin_id} granted {float(amount):.2f} credits",
        )

    def _check_daily_reset(self):
        """
        Reset daily counter if it's a new day.

        NOTE: This is for read-only checks (can_earn, get_daily_remaining).
        For actual earn operations, the reset happens inside the locked section.
        """
        now = timezone.now()
        if self.user.daily_earned_reset_at.date() < now.date():
            self.user.daily_credits_earned = Decimal('0')
            self.user.daily_earned_reset_at = now
            self.user.save(update_fields=["daily_credits_earned", "daily_earned_reset_at"])
