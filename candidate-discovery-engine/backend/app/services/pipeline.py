"""
Search Pipeline — orchestrates the full 2-stage candidate search.

Stage 1 (Retrieval):  Embed JD → Hybrid Search → Top 100 candidates
Stage 1b (Parallel):  JD Quality Score (runs alongside Stage 1 — free latency)
Stage 2 (Reasoning):  Batch-score top 20 via GPT-4o-mini → Ranked results
Stage 3 (Analytics):  Compute DEI distribution stats from results
Stage 4 (Persist):    Save search_event + match_results to PostgreSQL (background)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedder import get_embedding
from app.services.vector_search import hybrid_search
from app.services.reasoner import score_candidates, ScoredCandidate
from app.services.jd_scorer import score_jd_quality

logger = structlog.get_logger()


@dataclass
class AnalyticsData:
    """Aggregated analytics from search results (Feature B: DEI Dashboard)."""
    country_distribution: dict[str, int] = field(default_factory=dict)
    experience_bands: dict[str, int] = field(default_factory=dict)
    education_distribution: dict[str, int] = field(default_factory=dict)
    avg_match_score: float = 0.0
    score_distribution: dict[str, int] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Complete result of a search pipeline run."""
    search_event_id: str
    candidates: list[ScoredCandidate]
    total_candidates_searched: int
    latency_stage1_ms: int
    latency_stage2_ms: int
    total_latency_ms: int
    embedding_cache_hit: bool
    jd_quality: dict | None = None
    analytics: AnalyticsData | None = None


def _compute_analytics(scored: list[ScoredCandidate]) -> AnalyticsData:
    """
    Compute aggregated analytics from scored candidates.
    Used for DEI dashboard — shows distribution, NOT individual data.
    """
    if not scored:
        return AnalyticsData()

    countries = Counter(
        c.location_country or "Unknown" for c in scored
    )
    education = Counter(
        c.education_level or "Unknown" for c in scored
    )

    # Experience bands: 0-2, 3-5, 6-10, 11-15, 16+
    exp_bands: dict[str, int] = {"0-2": 0, "3-5": 0, "6-10": 0, "11-15": 0, "16+": 0}
    for c in scored:
        y = c.years_of_experience or 0
        if y <= 2:
            exp_bands["0-2"] += 1
        elif y <= 5:
            exp_bands["3-5"] += 1
        elif y <= 10:
            exp_bands["6-10"] += 1
        elif y <= 15:
            exp_bands["11-15"] += 1
        else:
            exp_bands["16+"] += 1

    # Score distribution
    score_dist: dict[str, int] = {"90-100": 0, "80-89": 0, "70-79": 0, "60-69": 0, "<60": 0}
    for c in scored:
        s = c.match_score
        if s >= 90:
            score_dist["90-100"] += 1
        elif s >= 80:
            score_dist["80-89"] += 1
        elif s >= 70:
            score_dist["70-79"] += 1
        elif s >= 60:
            score_dist["60-69"] += 1
        else:
            score_dist["<60"] += 1

    avg_score = sum(c.match_score for c in scored) / len(scored)

    return AnalyticsData(
        country_distribution=dict(countries.most_common(10)),
        experience_bands=exp_bands,
        education_distribution=dict(education.most_common(10)),
        avg_match_score=round(avg_score, 1),
        score_distribution=score_dist,
    )


async def _persist_results(
    search_event_id: str,
    recruiter_id: str,
    jd_text: str,
    jd_hash: str,
    search_hits_count: int,
    scored_candidates: list[ScoredCandidate],
    stage1_ms: int,
    stage2_ms: int,
    total_ms: int,
    cache_hit: bool,
) -> None:
    """
    Save search_event + all match_results to PostgreSQL.
    Creates its OWN session — runs as background task.
    """
    from app.db.session import async_session_factory

    try:
        async with async_session_factory() as db:
            top_ids = [c.candidate_postgres_id for c in scored_candidates[:20]]

            await db.execute(
                text("""
                    INSERT INTO search_events (
                        id, recruiter_id, jd_text_hash, jd_raw_text,
                        top_candidates_ids, candidates_searched,
                        latency_embedding_ms, latency_stage1_ms,
                        latency_stage2_ms, total_latency_ms,
                        embedding_cache_hit
                    ) VALUES (
                        :id, :recruiter_id, :jd_hash, :jd_text,
                        :top_ids, :searched,
                        :embed_ms, :stage1_ms,
                        :stage2_ms, :total_ms,
                        :cache_hit
                    )
                """),
                {
                    "id": search_event_id,
                    "recruiter_id": recruiter_id,
                    "jd_hash": jd_hash,
                    "jd_text": jd_text[:10000],
                    "top_ids": json.dumps(top_ids),
                    "searched": search_hits_count,
                    "embed_ms": 0 if cache_hit else stage1_ms,
                    "stage1_ms": stage1_ms,
                    "stage2_ms": stage2_ms,
                    "total_ms": total_ms,
                    "cache_hit": cache_hit,
                },
            )

            for rank, candidate in enumerate(scored_candidates, start=1):
                match_id = str(uuid.uuid4())
                await db.execute(
                    text("""
                        INSERT INTO match_results (
                            id, search_event_id, candidate_id,
                            match_score, justification_bullet_1,
                            justification_bullet_2,
                            vector_similarity, rank
                        ) VALUES (
                            :id, :search_event_id, :candidate_id,
                            :score, :j1, :j2,
                            :vs, :rank
                        )
                    """),
                    {
                        "id": match_id,
                        "search_event_id": search_event_id,
                        "candidate_id": candidate.candidate_postgres_id,
                        "score": candidate.match_score,
                        "j1": candidate.justification_1,
                        "j2": candidate.justification_2,
                        "vs": round(candidate.vector_similarity, 6),
                        "rank": rank,
                    },
                )

            await db.commit()
            logger.info(
                "results_persisted",
                search_event_id=search_event_id,
                match_results_count=len(scored_candidates),
            )
    except Exception as e:
        logger.error("persist_results_failed", error=str(e)[:300])


async def execute_search(
    jd_text: str,
    redis: Any,
    db: AsyncSession,
    recruiter_id: str = "system",
    filters: dict[str, Any] | None = None,
    top_k_retrieval: int = 100,
    top_k_scoring: int = 20,
) -> SearchResult:
    """
    Execute the full search pipeline with parallel JD quality scoring.
    """
    pipeline_start = time.monotonic()

    # ═══════════════════════════════════════════════════════════════
    # STAGE 1 + STAGE 1b (PARALLEL)
    # Stage 1:  Embed JD → Hybrid Search
    # Stage 1b: JD Quality Score (runs alongside — free latency)
    # ═══════════════════════════════════════════════════════════════
    stage1_start = time.monotonic()

    # Run embedding + JD quality in parallel
    jd_embedding, cache_hit = await get_embedding(jd_text, redis)

    # Now run hybrid search + JD quality in parallel
    search_task = hybrid_search(
        query_text=jd_text,
        query_embedding=jd_embedding,
        top_k=top_k_retrieval,
        filters=filters,
    )
    quality_task = score_jd_quality(jd_text)

    (search_hits, search_latency_ms), jd_quality = await asyncio.gather(
        search_task, quality_task
    )

    stage1_ms = int((time.monotonic() - stage1_start) * 1000)
    logger.info(
        "stage1_complete",
        candidates_found=len(search_hits),
        embedding_cached=cache_hit,
        latency_ms=stage1_ms,
    )

    # ═══════════════════════════════════════════════════════════════
    # STAGE 2: REASONING (batch scoring — 2 parallel LLM calls)
    # ═══════════════════════════════════════════════════════════════
    stage2_start = time.monotonic()

    candidates_to_score = search_hits[:top_k_scoring]
    scored_candidates, scoring_latency_ms = await score_candidates(
        jd_text=jd_text,
        candidates=candidates_to_score,
        max_concurrent=top_k_scoring,
    )

    stage2_ms = int((time.monotonic() - stage2_start) * 1000)

    # ═══════════════════════════════════════════════════════════════
    # STAGE 3: ANALYTICS (in-memory, microseconds)
    # ═══════════════════════════════════════════════════════════════
    analytics = _compute_analytics(scored_candidates)

    total_ms = int((time.monotonic() - pipeline_start) * 1000)

    logger.info(
        "pipeline_complete",
        candidates_scored=len(scored_candidates),
        stage1_ms=stage1_ms,
        stage2_ms=stage2_ms,
        total_ms=total_ms,
        top_score=scored_candidates[0].match_score if scored_candidates else 0,
        jd_quality_available=jd_quality is not None,
    )

    # ═══════════════════════════════════════════════════════════════
    # STAGE 4: PERSIST (fire-and-forget background task)
    # ═══════════════════════════════════════════════════════════════
    search_event_id = str(uuid.uuid4())
    jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()

    asyncio.create_task(
        _persist_results(
            search_event_id=search_event_id,
            recruiter_id=recruiter_id,
            jd_text=jd_text,
            jd_hash=jd_hash,
            search_hits_count=len(search_hits),
            scored_candidates=scored_candidates,
            stage1_ms=stage1_ms,
            stage2_ms=stage2_ms,
            total_ms=total_ms,
            cache_hit=cache_hit,
        )
    )

    return SearchResult(
        search_event_id=search_event_id,
        candidates=scored_candidates,
        total_candidates_searched=len(search_hits),
        latency_stage1_ms=stage1_ms,
        latency_stage2_ms=stage2_ms,
        total_latency_ms=total_ms,
        embedding_cache_hit=cache_hit,
        jd_quality=jd_quality,
        analytics=analytics,
    )
