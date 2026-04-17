from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import DateTime, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.models.base import Base, UUIDPrimaryKeyMixin

class WebhookEvent(Base,UUIDPrimaryKeyMixin):

    # One MatchResult can trigger multiple WebhookEvents if the delivery fails
    # and is retried (max 3 attempts per the webhook dispatcher spec).

    __tablename__='webhook_events'

    # ── Relationship ────────────────────────────────────────────────────
    match_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("match_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The high-scoring match that triggered this webhook",
    )
    # ── Delivery Details ────────────────────────────────────────────────
    webhook_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        comment="The URL that received (or should have received) the webhook",
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="The JSON payload that was sent",
    )
    # ── Response from receiver ──────────────────────────────────────────
    http_status: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="HTTP status code from the webhook receiver (null if request failed)",
    )
    response_body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Response body from the webhook receiver (for debugging)",
    )
    # ── Retry tracking ──────────────────────────────────────────────────
    attempt_number: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        comment="Which delivery attempt this is (1, 2, or 3)",
    )
    # ── Timestamps ──────────────────────────────────────────────────────
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this delivery attempt was initiated",
    )

    succeeded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When delivery was confirmed (null if failed)",
    )
    def __repr__(self) -> str:
        return f"<WebhookEvent(id={self.id}, status={self.http_status}, attempt={self.attempt_number})>"