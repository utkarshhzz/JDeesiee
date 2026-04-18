from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.models.base import Base, UUIDPrimaryKeyMixin

class PromptVariant(Base,UUIDPrimaryKeyMixin):
    """
    A versioned prompt template for candidate scoring.
    Each variant represents a different approach to asking GPT-4o-mini
    to score candidates. The system routes traffic according to
    traffic_percentage, and results are tracked in PromptExperiment.
    """

    __tablename__="prompt_variants"

    # Identity
    name: Mapped[str]= mapped_column(
        String(128),
        nullable=False,
        unique=True,
        comment="Human Readable name like 'v2 concise scoring",
    )

    description: Mapped[str | None]= mapped_column(
        Text,
        nullable=True,
        comment="What this variant changes and why we are testing it",
    )
    # Prompt content
    system_prompt:Mapped[str]= mapped_column(
        Text,
        nullable=False,
        comment="The system prompt template for GPT-40-mini"
    )
    user_prompt_template:Mapped[str]=mapped_column(
        Text,
        nullable=False,
        comment="The user template with {jd_text},{skills},etc.placeholders",
    )
    temperature:Mapped[float]=mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="LLM temperature (0 deterministic 1 ceative )"
    )
    # ── Traffic Split ───────────────────────────────────────────────────
    traffic_percentage: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        comment="Percentage of traffic routed to this variant (0-100). All variants must sum to 100.",
    )
    is_production: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is the current production prompt",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this variant is active in experiments",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PromptVariant(name={self.name}, traffic={self.traffic_percentage}%, prod={self.is_production})>"

class PromptExperiment(Base,UUIDPrimaryKeyMixin):
    # records the result of using a specific prompt
    # variant on a specific candidate

    """
    raw data -> which variant was used what score did it produce 
    how long it took
    how many tokens it consumed 
    
    """
    __tablename__ = "prompt_experiments"
    # relationships
    variant_id:Mapped[uuid.UUID]= mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_variants.id",ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    search_event_id:Mapped[uuid.UUID]= mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_events.id",ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Results ─────────────────────────────────────────────────────────
    score_given: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Match score produced by this prompt variant",
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Time taken for LLM to respond (ms)",
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total tokens (prompt + completion) consumed",
    )

    # ── Timestamps ──────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    def __repr__(self) -> str:
        return f"<PromptExperiment(variant={self.variant_id}, score={self.score_given})>"
