import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, CheckConstraint, text
from sqlalchemy.orm import mapped_column, Mapped
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    # identity
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    telegram_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(50), index=True)
    x_username: Mapped[str | None] = mapped_column(String(50), index=True)
    display_name: Mapped[str | None] = mapped_column(String(50))

    # the money — Decimal, never float; precision 12, scale 4 means up to 99999999.9999
    credits: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0"
    )
    total_credits_earned: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0"
    )
    total_credits_spent: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0"
    )

    # daily caps
    daily_credits_earned: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0"), server_default="0"
    )
    daily_earned_reset_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )

    # engagement & streak
    total_engagements: Mapped[int] = mapped_column(default=0, server_default="0")
    current_streak: Mapped[int] = mapped_column(default=0, server_default="0", index=True)

    # tier & X verification
    tweetscout_score: Mapped[float] = mapped_column(default=0.0, server_default="0")
    x_verified: Mapped[bool] = mapped_column(default=False, server_default="false", index=True)

    # access flags
    is_whitelisted: Mapped[bool] = mapped_column(default=False, server_default="false", index=True)
    is_banned: Mapped[bool] = mapped_column(default=False, server_default="false")

    # referral
    referral_code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "total_credits_earned >= total_credits_spent", name="earned_ge_spent"
        ),
        CheckConstraint(
            "NOT (is_whitelisted AND is_banned)", name="ban_xor_whitelist"
        ),
    )
