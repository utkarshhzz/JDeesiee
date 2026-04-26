"""
Search API — POST /api/v1/search

REQUEST:
    {
        "jd_text": "We're looking for a senior Python developer with AWS...",
        "filters": {
            "location_country": "India",
            "min_years": 5,
            "education_level": "Masters"
        },
        "top_k": 20
    }

RESPONSE:
    {
        "search_event_id": "abc123-...",
        "candidates": [
            {
                "candidate_id": "def456-...",
                "match_score": 92,
                "justifications": ["Strong Python...", "AWS certified...", "No K8s..."],
                "skills": "Python, AWS, Docker",
                "location": "Bengaluru, India",
                "years_of_experience": 8,
                "education_level": "Masters"
            },
            ...
        ],
        "latency": { "stage1_ms": 320, "stage2_ms": 780, "total_ms": 1100 }
    }
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.db.session import async_session_factory
from app.services.pipeline import execute_search

logger = structlog.get_logger()
router = APIRouter(tags=["search"])


# ── Request Schema ───────────────────────────────────────────────────
class SearchFilters(BaseModel):
    """Optional filters to narrow the candidate pool."""
    location_country: str | None = None
    location_city: str | None = None
    min_years: int | None = None
    education_level: str | None = None


class SearchRequest(BaseModel):
    """The request body for POST /api/v1/search."""
    jd_text: str = Field(
        ...,
        min_length=50,
        max_length=10000,
        description="The job description text to search against",
    )
    filters: SearchFilters | None = None
    top_k: int = Field(default=20, ge=1, le=50, description="Number of candidates to return")


# ── Response Schema ──────────────────────────────────────────────────
class CandidateResponse(BaseModel):
    candidate_id: str
    match_score: float
    justifications: list[str]
    matched_section: str
    skills: str
    location: str
    years_of_experience: int
    education_level: str


class LatencyBreakdown(BaseModel):
    stage1_ms: int
    stage2_ms: int
    total_ms: int
    embedding_cached: bool


class SearchResponse(BaseModel):
    search_event_id: str
    candidates: list[CandidateResponse]
    total_candidates_searched: int
    latency: LatencyBreakdown


# ── Route ────────────────────────────────────────────────────────────
@router.post("/search", response_model=SearchResponse)
async def search_candidates(body: SearchRequest, request: Request):
    """
    Search for candidates matching a job description.

    This is the MAIN endpoint of the entire application.
    It triggers the full 2-stage pipeline:
        Stage 1: Embed JD → Hybrid Search → Top 100
        Stage 2: LLM Score Top 20 → Ranked Results
    """
    logger.info("search_request", jd_length=len(body.jd_text), filters=body.filters)

    # Get Redis from app state (set up during lifespan)
    redis = request.app.state.redis

    # Get DB session
    async with async_session_factory() as db:
        # Build filter dict for the pipeline
        filter_dict = None
        if body.filters:
            filter_dict = body.filters.model_dump(exclude_none=True)

        # Execute the full pipeline
        result = await execute_search(
            jd_text=body.jd_text,
            redis=redis,
            db=db,
            filters=filter_dict,
            top_k_scoring=body.top_k,
        )

    # Transform internal results → API response
    candidate_responses = []
    for c in result.candidates:
        location_parts = [c.location_city, c.location_country]
        location = ", ".join(p for p in location_parts if p)

        candidate_responses.append(CandidateResponse(
            candidate_id=c.candidate_postgres_id,
            match_score=c.match_score,
            justifications=[c.justification_1, c.justification_2, c.justification_3],
            matched_section=c.section_type,
            skills=c.skills_str,
            location=location or "Unknown",
            years_of_experience=c.years_of_experience,
            education_level=c.education_level or "Unknown",
        ))

    return SearchResponse(
        search_event_id=result.search_event_id,
        candidates=candidate_responses,
        total_candidates_searched=result.total_candidates_searched,
        latency=LatencyBreakdown(
            stage1_ms=result.latency_stage1_ms,
            stage2_ms=result.latency_stage2_ms,
            total_ms=result.total_latency_ms,
            embedding_cached=result.embedding_cache_hit,
        ),
    )
