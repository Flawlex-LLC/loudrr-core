from decimal import Decimal
from datetime import datetime
from sqlalchemy import select
from app.models.user import User
from app.models.transaction import Transaction, TransactionType
from app.services.site_settings import get_setting
import uuid

class InsufficientCreditsError(Exception):
    """the user doesn't have enough credits to spend."""


class DailyCapReachedError(Exception):
    """The user has hit the daily earning cap."""


class CreditService:
    def __init__(self, db, user: User):
        self.db = db
        self.user = user

    async def earn(
        self,
        amount: Decimal,
        idempotency_key: str,
        reference_id=None,
        description: str = "",
    ) -> Transaction:
        # strict: refuse empty
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        # the amount is always a decimal
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.user_id == self.user.id,
                Transaction.type == TransactionType.EARNED,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing  # retry - return the original, change nothing
        # defense 1 - lock user row before reading balance
        result = await self.db.execute(
            select(User).where(User.id == self.user.id).with_for_update()
        )
        user = result.scalar_one()
        # controlling the daily cap, reset if its new day
        now = datetime.utcnow()
        if user.daily_earned_reset_at.date() < now.date():
            user.daily_credits_earned = Decimal("0")
            user.daily_earned_reset_at = now

        # the cap comes from settings store we built.
        daily_cap = Decimal(str(await get_setting(self.db, "DAILY_EARN_CAP")))
        final_amount = amount
        if user.daily_credits_earned + final_amount > daily_cap:
            # trim to the remaining headroom:
            final_amount = daily_cap - user.daily_credits_earned
            if final_amount <= Decimal("0"):
                raise DailyCapReachedError("Daily earning cap reached!")

        # apply the earn to the locked to row
        user.credits += final_amount
        user.total_credits_earned += final_amount
        user.daily_credits_earned += final_amount

        # write immutable audit record
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.EARNED,
            amount=final_amount,
            balance_after=user.credits,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            description=description or f"Earned {final_amount} credits.",
        )
        self.db.add(txn)
        await self.db.commit()
        return txn

    async def spend(
        self,
        amount: Decimal,
        idempotency_key: str,
        reference_id=None,
        description: str = "",
    ) -> Transaction:
        # strict: refuse empty
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            raise ValueError("Amount must be positive!")
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.user_id == self.user.id,
                Transaction.type == TransactionType.SPENT,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        # defense 1 - lock the user row
        result = await self.db.execute(
            select(User).where(User.id == self.user.id).with_for_update()
        )
        user = result.scalar_one()
        # the spend-specific rule: must be able to afford  it!
        if user.credits < amount:
            raise InsufficientCreditsError(f"Have {user.credits}, need {amount}")
        # move the balances
        user.credits -= amount
        user.total_credits_spent += amount
        # txn log
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.SPENT,
            amount=-amount,
            balance_after=user.credits,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            description=description or f"Spent {amount} credits.",
        )
        self.db.add(txn)
        await self.db.commit()
        return txn

    async def refund(
        self,
        amount: Decimal,
        idempotency_key: str,
        reference_id=None,
        description: str = "",
    ) -> Transaction:
        # strict: refuse empty
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            raise ValueError("Amount must be positive!")

        result = await self.db.execute(
            select(Transaction).where(
                Transaction.user_id == self.user.id,
                Transaction.type == TransactionType.REFUND,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        # defense 1 - lock the user row
        result = await self.db.execute(
            select(User).where(User.id == self.user.id).with_for_update()
        )
        user = result.scalar_one()
        # refund dcredits back.
        user.credits += amount
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.REFUND,
            amount=amount,  # positive gain
            balance_after=user.credits,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            description=description or f"Refunded: {amount} credits.",
        )
        self.db.add(txn)
        await self.db.commit()
        return txn

    async def admin_grant(
        self,
        amount: Decimal,
        admin_id: uuid.UUID,
        idempotency_key: str,
        description: str = "",
    ) -> Transaction:
        # strict: refuse empty
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))

        if amount <= Decimal("0"):
            raise ValueError("Amount must be positive!")
        # defence 2 - idempotency:
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.user_id == self.user.id,
                Transaction.type == TransactionType.ADMIN_GRANT,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        # defence: lock row
        result = await self.db.execute(
            select(User).where(User.id == self.user.id).with_for_update()
        )

        user = result.scalar_one()
        # no daily cap - admin bypass it
        user.credits += amount
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.ADMIN_GRANT,
            amount=amount,
            balance_after=user.credits,
            idempotency_key=idempotency_key,
            description=description or f"Admin {admin_id} granted {amount}",
        )
        self.db.add(txn)
        await self.db.commit()
        return txn

    async def apply_penalty(
        self,
        amount: Decimal,
        admin_id: uuid.UUID,
        idempotency_key: str,
        reference_id=None,
        description: str = "",
    ) -> Transaction:
        # strict: refuse empty
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount))
        if amount <= Decimal("0"):
            raise ValueError("Amount must be positive!")
        # defense 2 - idempotency (for penalty)
        result = await self.db.execute(
            select(Transaction).where(
                Transaction.user_id == self.user.id,
                Transaction.type == TransactionType.APPLY_PENALTY,
                Transaction.idempotency_key == idempotency_key,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        # defense 1 - lock the user row
        result = await self.db.execute(
            select(User).where(User.id == self.user.id).with_for_update()
        )
        user = result.scalar_one()
        # move the balances
        user.credits -= amount
        # user.total_credits_spent += amount - this is  not applicable for penalty
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.APPLY_PENALTY,
            amount=-amount,
            balance_after=user.credits,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            description=description or f" penalty of {amount} by {admin_id}.",
        )
        self.db.add(txn)
        await self.db.commit()
        return txn
