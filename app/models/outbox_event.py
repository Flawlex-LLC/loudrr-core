import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Text, CheckConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base


class OutboxEventType(str, enum.Enum):
    TELEGRAM_NOTIFY = "telegram_notify"
    WAITLIST_APPROVED = "waitlist_approved"
    WAITLIST_SUBMITTED = "waitlist_submitted"
    CREDITS_EARNED = "credits_earned"
    POST_COMPLETED = "post_completed"
    CAMPAIGN_WINNER = "campaign_winner"
    TWEETSCOUT_FETCH = "tweetscout_fetch"
    EXTERNAL_API = "external_api"


class OutboxStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


class OutboxEvent(Base):
    """The transactional outbox (spec §2.7, §5.5).

    A side-effect (Telegram message, external call) is never done inline. The
    business write inserts a `pending` row here in the SAME transaction; a
    worker later drains it. If the business txn rolls back, so does the event —
    guaranteed consistency, no half-applied side-effects.
    """

    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(
        String(20), default=OutboxStatus.PENDING.value,
        server_default=OutboxStatus.PENDING.value,
    )
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    retry_count: Mapped[int] = mapped_column(default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(default=3, server_default="3")
    error_message: Mapped[str] = mapped_column(Text, default="", server_default="")
    processed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed')",
            name="outbox_status_valid",
        ),
        Index("ix_outbox_status_created", "status", "created_at"),
        Index("ix_outbox_type_status", "event_type", "status"),
    )
