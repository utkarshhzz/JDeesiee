"""
Search Pipeline — orchestrates the full 2-stage candidate search.

Stage 1 (Retrieval): Embed JD → Hybrid Search → Top 100 candidates
Stage 2 (Reasoning): Score top 20 via GPT-4o-mini → Ranked results
Stage 3 (Persist):   Save search_event + match_results to PostgreSQL
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedder import get_embedding
from app.services.vector_search import hybrid_search, SearchHit
from app.services.reasoner import score_candidates, ScoredCandidate

logger = structlog.get_logger()


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


async def _persist_results(
    db: AsyncSession,
    search_event_id: str,
    recruiter_id: str,
    jd_text: str,
    jd_hash: str,
    search_hits: list[SearchHit],
    scored_candidates: list[ScoredCandidate],
    stage1_ms: int,
    stage2_ms: int,
    total_ms: int,
    cache_hit: bool,
) -> None:
    """
    Save search_event + all match_results to PostgreSQL in a background task.

    WHY a separate function?
        - Keeps execute_search() focused on search logic
        - If DB write fails, we log and move on — the search result is already
          returned to the user
        - In future, this could be moved to a message queue (Service Bus)

    WHAT it saves:
        - search_events: one row per search (who searched, when, latency breakdown)
        - match_results: one row per scored candidate (score, justifications, rank)
          This lets you answer: "Show me all candidates who scored > 90 last week"
    """
    try:
        # ── Save search event (the "header" row) ─────────────────
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
                "searched": len(search_hits),
                "embed_ms": 0 if cache_hit else stage1_ms,
                "stage1_ms": stage1_ms,
                "stage2_ms": stage2_ms,
                "total_ms": total_ms,
                "cache_hit": cache_hit,
            },
        )

        # ── Save match results (one row per scored candidate) ────
        # Each row: score, justifications, rank, vector similarity
        for rank, candidate in enumerate(scored_candidates, start=1):
            match_id = str(uuid.uuid4())
            await db.execute(
                text("""
                    INSERT INTO match_results (
                        id, search_event_id, candidate_id,
                        match_score, justification_bullet_1, justification_bullet_2,
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
        logger.error("persist_results_failed", error=str(e)[:200])


async def execute_search(
    jd_text: str,
    redis,
    db: AsyncSession,
    recruiter_id: str = "system",
    filters: dict[str, Any] | None = None,
    top_k_retrieval: int = 100,
    top_k_scoring: int = 20,
) -> SearchResult:
    """
    Execute the full 2-stage search pipeline.

    Args:
        jd_text:          Raw job description text from the recruiter
        redis:            Async Redis client (for embedding cache)
        db:               SQLAlchemy async session (for saving search event)
        recruiter_id:     Who initiated the search (for audit trail)
        filters:          Optional: {"location_country": "India", "min_years": 5}
        top_k_retrieval:  How many candidates to retrieve from vector search
        top_k_scoring:    How many of those to score with LLM

    Returns:
        SearchResult with scored candidates and latency breakdown
    """
    pipeline_start = time.monotonic()

    # ═══════════════════════════════════════════════════════════════
    # STAGE 1: RETRIEVAL (target < 500ms)
    # ═══════════════════════════════════════════════════════════════
    stage1_start = time.monotonic()

    # Step 1a: Generate JD embedding (or retrieve from Redis cache)
    jd_embedding, cache_hit = await get_embedding(jd_text, redis)

    # Step 1b: Hybrid search (BM25 + vector + semantic reranking)
    search_hits, search_latency_ms = await hybrid_search(
        query_text=jd_text,
        query_embedding=jd_embedding,
        top_k=top_k_retrieval,
        filters=filters,
    )

    stage1_ms = int((time.monotonic() - stage1_start) * 1000)
    logger.info(
        "stage1_complete",
        candidates_found=len(search_hits),
        embedding_cached=cache_hit,
        latency_ms=stage1_ms,
    )

    # ═══════════════════════════════════════════════════════════════
    # STAGE 2: REASONING (target < 2000ms)
    # ═══════════════════════════════════════════════════════════════
    stage2_start = time.monotonic()

    candidates_to_score = search_hits[:top_k_scoring]
    scored_candidates, scoring_latency_ms = await score_candidates(
        jd_text=jd_text,
        candidates=candidates_to_score,
        max_concurrent=top_k_scoring,
    )

    stage2_ms = int((time.monotonic() - stage2_start) * 1000)
    total_ms = int((time.monotonic() - pipeline_start) * 1000)

    logger.info(
        "pipeline_complete",
        candidates_scored=len(scored_candidates),
        stage1_ms=stage1_ms,
        stage2_ms=stage2_ms,
        total_ms=total_ms,
        top_score=scored_candidates[0].match_score if scored_candidates else 0,
    )

    # ═══════════════════════════════════════════════════════════════
    # STAGE 3: PERSIST (fire-and-forget background task)
    # ═══════════════════════════════════════════════════════════════
    # asyncio.create_task runs the DB write in the background.
    # The API response is returned BEFORE the write finishes,
    # keeping total latency within the 2.5s budget.
    search_event_id = str(uuid.uuid4())
    jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()

    asyncio.create_task(
        _persist_results(
            db=db,
            search_event_id=search_event_id,
            recruiter_id=recruiter_id,
            jd_text=jd_text,
            jd_hash=jd_hash,
            search_hits=search_hits,
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
    )
