"""
Credit system service.

Handles all credit operations: earning, spending, purchasing.
All operations are atomic and create transaction records.
"""
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Transaction, User


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits."""
    pass


class DailyCapReachedError(Exception):
    """Raised when user has reached daily earning cap."""
    pass


class WeeklyPurchaseCapReachedError(Exception):
    """Raised when user has reached weekly purchase cap."""
    pass


class CreditService:
    """Service for managing user credits."""

    def __init__(self, user: User):
        self.user = user
        self.config = settings.ECHO_CONFIG

    def get_balance(self) -> int:
        """Get current credit balance."""
        return self.user.credits

    def get_daily_remaining(self) -> int:
        """Get remaining credits that can be earned today."""
        self._check_daily_reset()
        return max(0, self.config["DAILY_EARN_CAP"] - self.user.daily_credits_earned)

    def get_weekly_purchase_remaining(self) -> int:
        """Get remaining credits that can be purchased this week."""
        self._check_weekly_reset()
        return max(0, self.config["WEEKLY_PURCHASE_CAP"] - self.user.weekly_credits_purchased)

    def can_earn(self, amount: int = 1) -> bool:
        """Check if user can earn more credits today."""
        self._check_daily_reset()
        return self.user.daily_credits_earned + amount <= self.config["DAILY_EARN_CAP"]

    def can_spend(self, amount: int) -> bool:
        """Check if user has enough credits to spend."""
        return self.user.credits >= amount

    @transaction.atomic
    def earn(
        self,
        amount: int,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
        apply_multipliers: bool = True,
    ) -> Transaction:
        """
        Grant credits to user for engagement.

        Args:
            amount: Base amount of credits to earn
            reference_id: ID of related object (engagement, post, etc.)
            reference_type: Type of reference object
            description: Description of transaction
            apply_multipliers: Whether to apply tier/streak multipliers

        Returns:
            Transaction record

        Raises:
            DailyCapReachedError: If daily cap would be exceeded
        """
        self._check_daily_reset()

        # Calculate final amount with multipliers
        final_amount = amount
        if apply_multipliers:
            multiplier = self.user.get_tier_multiplier() * self.user.get_streak_multiplier()
            final_amount = int(amount * multiplier)

        # Check daily cap
        if self.user.daily_credits_earned + final_amount > self.config["DAILY_EARN_CAP"]:
            # Cap at remaining daily limit
            final_amount = self.config["DAILY_EARN_CAP"] - self.user.daily_credits_earned
            if final_amount <= 0:
                raise DailyCapReachedError("Daily earning cap reached")

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update user credits
        user.credits += final_amount
        user.total_credits_earned += final_amount
        user.daily_credits_earned += final_amount
        user.save(update_fields=[
            "credits", "total_credits_earned", "daily_credits_earned", "updated_at"
        ])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.EARNED,
            amount=final_amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description or f"Earned {final_amount} credits",
        )

    @transaction.atomic
    def spend(
        self,
        amount: int,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
    ) -> Transaction:
        """
        Deduct credits from user for posting.

        Args:
            amount: Amount of credits to spend
            reference_id: ID of related object (post)
            reference_type: Type of reference object
            description: Description of transaction

        Returns:
            Transaction record

        Raises:
            InsufficientCreditsError: If user doesn't have enough credits
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        if user.credits < amount:
            raise InsufficientCreditsError(
                f"Insufficient credits. Have {user.credits}, need {amount}"
            )

        # Update user credits
        user.credits -= amount
        user.total_credits_spent += amount
        user.save(update_fields=["credits", "total_credits_spent", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.SPENT,
            amount=-amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description or f"Spent {amount} credits",
        )

    @transaction.atomic
    def purchase(
        self,
        amount: int,
        description: str = "",
    ) -> Transaction:
        """
        Add purchased credits to user.

        Args:
            amount: Amount of credits purchased
            description: Description of purchase

        Returns:
            Transaction record

        Raises:
            WeeklyPurchaseCapReachedError: If weekly purchase cap would be exceeded
        """
        self._check_weekly_reset()

        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Check weekly cap
        if self.user.weekly_credits_purchased + amount > self.config["WEEKLY_PURCHASE_CAP"]:
            remaining = self.config["WEEKLY_PURCHASE_CAP"] - self.user.weekly_credits_purchased
            raise WeeklyPurchaseCapReachedError(
                f"Weekly purchase cap reached. Can only purchase {remaining} more credits."
            )

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update user credits
        user.credits += amount
        user.weekly_credits_purchased += amount
        user.save(update_fields=["credits", "weekly_credits_purchased", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.PURCHASED,
            amount=amount,
            balance_after=user.credits,
            description=description or f"Purchased {amount} credits",
        )

    @transaction.atomic
    def refund(
        self,
        amount: int,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
    ) -> Transaction:
        """
        Refund credits to user (e.g., cancelled post).

        Args:
            amount: Amount of credits to refund
            reference_id: ID of related object
            reference_type: Type of reference object
            description: Description of refund

        Returns:
            Transaction record
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Update user credits
        user.credits += amount
        # Don't update total_credits_spent - refund doesn't undo the original spend
        user.save(update_fields=["credits", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.REFUND,
            amount=amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description or f"Refunded {amount} credits",
        )

    @transaction.atomic
    def apply_penalty(
        self,
        amount: int,
        reference_id=None,
        reference_type: str = "",
        description: str = "",
    ) -> Transaction:
        """
        Apply penalty to user (e.g., failed audit).

        Args:
            amount: Amount of credits to deduct as penalty
            reference_id: ID of related object (audit)
            reference_type: Type of reference object
            description: Description of penalty

        Returns:
            Transaction record
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Lock user row for update
        user = User.objects.select_for_update().get(pk=self.user.pk)

        # Deduct credits (can go negative as penalty)
        user.credits -= amount
        user.save(update_fields=["credits", "updated_at"])

        # Refresh our instance
        self.user.refresh_from_db()

        # Create transaction record
        return Transaction.objects.create(
            user=user,
            type=Transaction.Type.PENALTY,
            amount=-amount,
            balance_after=user.credits,
            reference_id=reference_id,
            reference_type=reference_type,
            description=description or f"Penalty of {amount} credits",
        )

    def _check_daily_reset(self):
        """Reset daily counter if it's a new day."""
        now = timezone.now()
        if self.user.daily_earned_reset_at.date() < now.date():
            self.user.daily_credits_earned = 0
            self.user.daily_earned_reset_at = now
            self.user.save(update_fields=["daily_credits_earned", "daily_earned_reset_at"])

    def _check_weekly_reset(self):
        """Reset weekly counter if it's a new week."""
        now = timezone.now()
        days_since_reset = (now - self.user.weekly_purchased_reset_at).days
        if days_since_reset >= 7:
            self.user.weekly_credits_purchased = 0
            self.user.weekly_purchased_reset_at = now
            self.user.save(update_fields=["weekly_credits_purchased", "weekly_purchased_reset_at"])
