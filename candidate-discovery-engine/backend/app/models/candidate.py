from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

from pydantic import BaseModel,ConfigDict,Field

class candidate(Base,UUIDPrimaryKeyMixin,TimestampMixin):
    __tablename__="candidates"

    external_id:Mapped[str | None]= mapped_column(
        String(128),
        unique=True,
        nullable=True,
        comment="External ID from the Applicant Tracking System"
     )
    full_name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Candidate's full name",
    )
    email: Mapped[str | None] = mapped_column(
        String(320),  # RFC 5321 max email length is 320 chars
        unique=True,
        nullable=True,
        comment="Candidate's email address",
    )
    phone: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="Phone number with country code",
    )
    location_city: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    location_country: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,  # Indexed because recruiters filter by country
        comment="ISO country name for search filtering",
    )
    # ── Professional Profile ────────────────────────────────────────────
    years_of_experience: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
        index=True,  # Indexed because recruiters filter by experience
    )
    current_title: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
    )
    current_company: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
    )
    education_level: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Bachelors, Masters, PhD, etc.",
    )
    skills: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='JSON array of skills, e.g. ["Python", "AWS", "FastAPI"]',
    )
    resume_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Plain text resume content (max ~8000 chars), used for LLM reasoning",
    )
    resume_blob_url: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="Azure Blob Storage URL to the original resume file",
    )
    vector_id: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        index=True,  # Indexed for fast lookup when mapping search results back
        comment="ID of this candidate's vector in Azure AI Search index",
    )
    # ── Soft Delete ─────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
        comment="Soft-delete flag. False = candidate opted out or was removed.",
    )

     # ── Table-level indexes (multi-column) ──────────────────────────────
    __table_args__ = (
        # Composite index for the most common search filter combination.
        # When a recruiter searches with both country + experience filters,
        # PostgreSQL can use this single index instead of two separate ones.
        Index("ix_candidates_country_experience", "location_country", "years_of_experience"),
    )

    def __repr__(self) -> str:
        return f"<Candidate(id={self.id}, name={self.full_name})>"


class CandidateBase(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=256, examples=["Priya Sharma"])
    email: str | None = Field(None, max_length=320, examples=["priya.sharma@example.com"])
    phone: str | None = Field(None, max_length=32, examples=["+91-9876543210"])
    location_city: str | None = Field(None, max_length=128, examples=["Mumbai"])
    location_country: str | None = Field(None, max_length=64, examples=["India"])
    years_of_experience: int | None = Field(None, ge=0, le=50, examples=[7])
    current_title: str | None = Field(None, max_length=256, examples=["Senior Backend Engineer"])
    current_company: str | None = Field(None, max_length=256, examples=["Infosys"])
    education_level: str | None = Field(None, max_length=64, examples=["Masters"])
    skills: list[str] | None = Field(None, examples=[["Python", "FastAPI", "PostgreSQL", "Azure"]])


class CandidateCreate(CandidateBase):
    """Schema for creating a new candidate via API."""
    external_id: str | None = Field(None, max_length=128)
    resume_text: str | None = Field(None, max_length=8000)


class CandidateResponse(CandidateBase):
    """
    Schema returned in API responses.
    model_config with from_attributes=True tells Pydantic:
    "You can read attributes from an ORM object, not just a dict."
    So we can do: CandidateResponse.model_validate(orm_candidate)
    and it reads orm_candidate.full_name, orm_candidate.email, etc.
    """
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
class CandidateMatchResponse(CandidateResponse):
    """
    Extended response that includes match scoring information.
    Returned by the search pipeline (includes LLM-generated scores).
    """
    match_score: float = Field(..., ge=0, le=100, examples=[87.5])
    justification_bullet_1: str = Field(..., examples=["Strong Python + FastAPI expertise matches core requirements"])
    justification_bullet_2: str = Field(..., examples=["Limited cloud experience — 2 years AWS vs 5 years required"])
    vector_similarity: float = Field(..., ge=0, le=1, examples=[0.892345])
    rank: int = Field(..., ge=1, examples=[3])