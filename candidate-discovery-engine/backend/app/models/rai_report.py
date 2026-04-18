"""
Responsible AI Report ORM model (Enhancement G).

Stores transparency reports generated for EVERY search:
    1. Bias detection: Were certain demographic groups under-represented?
    2. JD language analysis: Does the JD use exclusionary language?
    3. Filter impact: How much did filters narrow the candidate pool?
    4. Fairness metrics: Statistical measures of result fairness.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, Text, func, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class RAIReport(Base, UUIDPrimaryKeyMixin):
    """
    Responsible AI Transparency Report for a single search.
    One RAIReport per SearchEvent (1-to-1 relationship).
    """

    __tablename__ = "rai_reports"

    # ── Relationship ────────────────────────────────────────────────────
    search_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("search_events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="The search that this report analyses",
    )

    # ── Bias Detection ──────────────────────────────────────────────────
    demographic_distribution: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Aggregate stats: {"country": {"India": 12, "USA": 5}}',
    )
    score_variance_by_group: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Mean/stddev of match_score grouped by country, experience, education",
    )
    bias_flags: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Potential bias warnings: ["95% of top results from single country"]',
    )

    # ── JD Language Analysis ────────────────────────────────────────────
    jd_inclusivity_score: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        comment="LLM-rated JD inclusivity (1-10)",
    )
    exclusionary_phrases: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='Flagged phrases: [{"phrase": "rockstar", "suggestion": "top performer"}]',
    )

    # ── Filter Impact Analysis ──────────────────────────────────────────
    filter_impact: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="How filters affected diversity",
    )

    # ── Recommendations ─────────────────────────────────────────────────
    recommendations: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Actionable suggestions to improve JD inclusivity and search breadth",
    )

    # ── Timestamps ──────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<RAIReport(search_event={self.search_event_id}, inclusivity_score={self.jd_inclusivity_score})>"
