"""
Business invariant checks for Loudrr.

Invariants are conditions that must ALWAYS be true in a correct system.
When an invariant is violated, it indicates a bug in the code, not user error.

Usage:
    from core.invariants import check_invariant, check_precondition, check_postcondition

    # In service methods
    def earn(self, amount):
        check_precondition(amount > 0, "Amount must be positive")

        balance_before = self.user.credits
        # ... business logic ...

        check_postcondition(
            self.user.credits >= 0,
            f"Credits went negative: {self.user.credits}"
        )
"""
import structlog
from typing import Any, Optional

logger = structlog.get_logger(__name__)


class InvariantViolation(Exception):
    """
    Business invariant was violated.

    This indicates a bug in the code, not user error.
    When this exception is raised, it should be logged and investigated.
    """

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message)
        self.context = context or {}


def check_invariant(
    condition: bool,
    message: str,
    context: Optional[dict[str, Any]] = None
) -> None:
    """
    Assert a business invariant.

    Raises InvariantViolation if condition is False.
    Use for conditions that should NEVER be false in correct code.

    Args:
        condition: The invariant condition that must be True
        message: Human-readable description of what went wrong
        context: Optional dict of context data for debugging

    Raises:
        InvariantViolation: If condition is False

    Example:
        check_invariant(
            user.credits >= 0,
            "User credits went negative",
            {"user_id": str(user.id), "credits": str(user.credits)}
        )
    """
    if not condition:
        logger.error(
            "invariant_violation",
            message=message,
            context=context or {},
        )
        raise InvariantViolation(message, context)


def check_precondition(
    condition: bool,
    message: str,
    context: Optional[dict[str, Any]] = None
) -> None:
    """
    Check precondition before an operation.

    Use at the start of service methods to validate inputs
    and state before performing operations.

    Args:
        condition: The precondition that must be True
        message: Description of the required precondition
        context: Optional context data

    Raises:
        InvariantViolation: If precondition is not met

    Example:
        def earn(self, amount):
            check_precondition(amount > 0, "Amount must be positive")
            check_precondition(not self.user.is_banned, "User is banned")
    """
    check_invariant(condition, f"Precondition failed: {message}", context)


def check_postcondition(
    condition: bool,
    message: str,
    context: Optional[dict[str, Any]] = None
) -> None:
    """
    Check postcondition after an operation.

    Use at the end of service methods to verify the operation
    left the system in a valid state.

    Args:
        condition: The postcondition that must be True
        message: Description of what should be true after the operation
        context: Optional context data

    Raises:
        InvariantViolation: If postcondition is not met

    Example:
        def earn(self, amount):
            balance_before = self.user.credits
            # ... business logic ...
            check_postcondition(
                self.user.credits == balance_before + amount,
                "Balance mismatch after earn"
            )
    """
    check_invariant(condition, f"Postcondition failed: {message}", context)


def check_balance_integrity(user) -> None:
    """
    Check that a user's credit balance is consistent.

    This checks:
    - Credits are non-negative
    - Total earned >= total spent (approximately, accounting for adjustments)
    - Daily earned is within reasonable bounds

    Args:
        user: User model instance

    Raises:
        InvariantViolation: If balance integrity is compromised
    """
    from decimal import Decimal

    context = {
        "user_id": str(user.id),
        "credits": str(user.credits),
        "total_earned": str(user.total_credits_earned),
        "total_spent": str(user.total_credits_spent),
        "daily_earned": str(user.daily_credits_earned),
    }

    check_invariant(
        user.credits >= Decimal('0'),
        "User credits are negative",
        context
    )

    check_invariant(
        user.daily_credits_earned >= Decimal('0'),
        "Daily earned credits are negative",
        context
    )

    # Allow some tolerance for admin adjustments and refunds
    if user.total_credits_spent > user.total_credits_earned + Decimal('1000'):
        logger.warning(
            "suspicious_balance",
            message="User spent more than earned (possible admin adjustment)",
            **context
        )


def check_escrow_integrity(post) -> None:
    """
    Check that a post's escrow balance is consistent.

    This checks:
    - Escrow is non-negative
    - Escrow does not exceed initial escrow
    - Completed posts have zero escrow

    Args:
        post: Post model instance

    Raises:
        InvariantViolation: If escrow integrity is compromised
    """
    from decimal import Decimal
    from posts.models import Post

    context = {
        "post_id": str(post.id),
        "escrow": str(post.escrow),
        "initial_escrow": str(post.initial_escrow),
        "status": post.status,
    }

    check_invariant(
        post.escrow >= Decimal('0'),
        "Post escrow is negative",
        context
    )

    check_invariant(
        post.escrow <= post.initial_escrow,
        "Post escrow exceeds initial escrow",
        context
    )

    if post.status == Post.Status.COMPLETED:
        check_invariant(
            post.escrow == Decimal('0'),
            "Completed post has non-zero escrow",
            context
        )
