from sqlalchemy import false
from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin

class MatchResult(Base,UUIDPrimaryKeyMixin):

    __tablename__="Match_results"

    # foreign keys
    search_event_id: Mapped[uuid.UUID]= mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_events.id",ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The search that produced this match"

    )
    candidate_id: Mapped[uuid.UUID]= mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id",ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="The candidate who was scored"

    )
     # ── Scoring ─────────────────────────────────────────────────────────
    match_score: Mapped[float] = mapped_column(
        Numeric(5, 2),  # Up to 100.00 — 5 digits total, 2 after decimal
        nullable=False,
        comment="GPT-4o-mini's match score (0.00 - 100.00)",
    )
    vector_similarity: Mapped[float] = mapped_column(
        Numeric(8, 6),  # e.g., 0.892345 — 8 digits total, 6 after decimal
        nullable=False,
        comment="Raw cosine similarity from Azure AI Search HNSW",
    )
    # ── LLM Justification ──────────────────────────────────────────────
    justification_bullet_1: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="LLM's top reason for the match score",
    )
    justification_bullet_2: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="LLM's secondary reason or identified gap",
    )
    # ── Ranking ─────────────────────────────────────────────────────────
    rank: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        comment="Rank within the search result (1 = best match, 20 = last)",
    )
    # ── Timestamps ──────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    def __repr__(self) -> str:
        return f"<MatchResult(search={self.search_event_id}, candidate={self.candidate_id}, score={self.match_score})>"