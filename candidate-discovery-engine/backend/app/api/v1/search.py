"""
Search API — POST /api/v1/search + GET /api/v1/search/history + Export

The main search endpoint triggers the full pipeline:
    Stage 1: Embed JD → Hybrid Search → Top 100
    Stage 1b: JD Quality Score (parallel, free latency)
    Stage 2: Batch LLM Score Top 20 → Ranked Results
    Stage 3: Compute DEI analytics
"""

from __future__ import annotations

import csv
import io
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db.session import async_session_factory
from app.services.pipeline import execute_search
from sqlalchemy import text

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


class JDQualityScore(BaseModel):
    clarity: int
    specificity: int
    inclusivity: int
    overall: float
    suggestions: list[str]


class AnalyticsResponse(BaseModel):
    country_distribution: dict[str, int]
    experience_bands: dict[str, int]
    education_distribution: dict[str, int]
    avg_match_score: float
    score_distribution: dict[str, int]


class SearchResponse(BaseModel):
    search_event_id: str
    candidates: list[CandidateResponse]
    total_candidates_searched: int
    latency: LatencyBreakdown
    jd_quality: JDQualityScore | None = None
    analytics: AnalyticsResponse | None = None


# ── Main Search Route ────────────────────────────────────────────────
@router.post("/search", response_model=SearchResponse)
async def search_candidates(body: SearchRequest, request: Request):
    """
    Search for candidates matching a job description.
    Triggers the full 2-stage pipeline with JD quality scoring and DEI analytics.
    """
    logger.info("search_request", jd_length=len(body.jd_text), filters=body.filters)

    redis = request.app.state.redis

    async with async_session_factory() as db:
        filter_dict = None
        if body.filters:
            filter_dict = body.filters.model_dump(exclude_none=True)

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

    # JD Quality
    jd_quality_resp = None
    if result.jd_quality:
        jd_quality_resp = JDQualityScore(**result.jd_quality)

    # Analytics
    analytics_resp = None
    if result.analytics:
        analytics_resp = AnalyticsResponse(
            country_distribution=result.analytics.country_distribution,
            experience_bands=result.analytics.experience_bands,
            education_distribution=result.analytics.education_distribution,
            avg_match_score=result.analytics.avg_match_score,
            score_distribution=result.analytics.score_distribution,
        )

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
        jd_quality=jd_quality_resp,
        analytics=analytics_resp,
    )


# ── Search History ───────────────────────────────────────────────────
class SearchHistoryItem(BaseModel):
    search_event_id: str
    jd_snippet: str
    candidates_searched: int | None
    total_latency_ms: int | None
    embedding_cached: bool | None
    searched_at: str


class SearchHistoryResponse(BaseModel):
    history: list[SearchHistoryItem]


@router.get("/search/history", response_model=SearchHistoryResponse)
async def get_search_history(request: Request, limit: int = 20):
    """Get the last N searches for the sidebar."""
    async with async_session_factory() as db:
        result = await db.execute(
            text("""
                SELECT id, jd_raw_text, candidates_searched,
                       total_latency_ms, embedding_cache_hit, created_at
                FROM search_events
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        )

        history = []
        for row in result.fetchall():
            jd_text = row[1] or ""
            history.append(SearchHistoryItem(
                search_event_id=str(row[0]),
                jd_snippet=jd_text[:200],
                candidates_searched=row[2],
                total_latency_ms=row[3],
                embedding_cached=row[4],
                searched_at=row[5].isoformat() if row[5] else "",
            ))

    return SearchHistoryResponse(history=history)


# ── CSV Export ───────────────────────────────────────────────────────
@router.get("/search/{event_id}/export")
async def export_search_results(event_id: str):
    """Export search results as CSV for sharing with hiring managers."""
    async with async_session_factory() as db:
        result = await db.execute(
            text("""
                SELECT
                    mr.rank,
                    c.full_name,
                    c.email,
                    c.current_title,
                    c.current_company,
                    c.location_city,
                    c.location_country,
                    c.years_of_experience,
                    c.education_level,
                    mr.match_score,
                    mr.justification_bullet_1,
                    mr.justification_bullet_2,
                    mr.vector_similarity
                FROM match_results mr
                JOIN candidates c ON c.id = mr.candidate_id
                WHERE mr.search_event_id = :event_id
                ORDER BY mr.rank ASC
            """),
            {"event_id": event_id},
        )
        rows = result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank", "Name", "Email", "Title", "Company",
        "City", "Country", "Experience (years)", "Education",
        "Match Score", "Strength", "Gap/Note", "Vector Similarity",
    ])

    for row in rows:
        writer.writerow(list(row))

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=search_{event_id[:8]}_results.csv",
        },
    )
