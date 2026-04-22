from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Integer,String,Text
from sqlalchemy.dialects.postgresql import JSONB,UUID
from sqlalchemy.orm import Mapped,mapped_column

from app.models.base import Base,UUIDPrimaryKeyMixin

class SearchEvent(Base,UUIDPrimaryKeyMixin):
    __tablename__= "search_events"
    
    recruiter_id:Mapped[str]=mapped_column(
        String(256),
        nullable=False,
        index=True,
        comment="Recruiter identifier from JWT claims"

    )
    jd_text_hash: Mapped[str]=mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hex hash of the 3d test"
    )

    jd_raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full archived JD text for audit replay",
    )
    jd_file_name: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Original filename if uploaded as PDF/DOCX (null if pasted as text)",
    )
    # ── What was found ──────────────────────────────────────────────────
    top_candidates_ids: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Ordered list of top 20 candidate UUIDs returned by the pipeline",
    )

    # Storing latency to track performance degradation over time
    # to identidy slow searches
    # validation that we do fast quick searching

    latency_embedding_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="time to generate /retrieve 3D embedding (ms)"
    )
    latency_stage1_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="stage 1 ANN vecor search latency (ms)"
    )
    latency_stage2_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Stage  2 LLm reasoning latency"
    )
    total_latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Total end to end pipeline latency"
    )

    # metadata
    candidates_searched: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=110_000_000,

    )
    embedding_cache_hit: Mapped[bool | None] = mapped_column(
        nullable=True,
        comment="Whether the embedding was served from Redis cache",
    )
    # ── Timestamps ──────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default="now()",
    )
    def __repr__(self) -> str:
        return f"<SearchEvent(id={self.id}, recruiter={self.recruiter_id})>"