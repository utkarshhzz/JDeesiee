"""
Search Pipeline -> orchestrates full2 stage candidate search
architecture stage1 retreicval:Embed JD -> hybid dearch-> top 100 candidates
then stage 2 reasoning top 20 via gpt 4o mini
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
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
    # complete result of a search pipeline run
    search_event_id:str #UUID of search event record
    candidates:list[ScoredCandidate]
    total_candidates_searched:int
    latency_stage1_ms:int
    latency_stage2_ms:int
    total_latency_ms:int
    embedding_cache_hit:bool

async def execute_search(
    jd_text:str,
    redis,
    db:AsyncSession,
    recruiter_id:str="system",
    filters:dict[str,Any]| None=None,
    top_k_retrieval:int =100,
    top_k_scoring:int =20,
) -> SearchResult:
    """
    Execute the full 2-stage search pipeline.
    Args:
        jd_text:          Raw job description text from the recruiter
        redis:            Async Redis client (for embedding cache)
        db:               SQLAlchemy async session (for saving search event)
        recruiter_id:     Who initiated the search (for audit trail)
        filters:          Optional: {"location_country": "India", "min_years": 5}
        top_k_retrieval:  How many candidates to retrieve from vector search (default 100)
        top_k_scoring:    How many of those to score with LLM (default 20)
    Returns:
        SearchResult with scored candidates and latency breakdown
    """

    pipeline_start=time.monotonic()
    # STAGE 1 retrieval
    stage1_start=time.monotonic()

    # Generate jd embedding or get from redis cache
    jd_embedding,cache_hit=await get_embedding(jd_text,redis)

    # now hybrid search bm25+vector+semantic reranking
    search_hits,search_latency_ms=await hybrid_search(
        query_text=jd_text,
        query_embedding=jd_embedding,
        top_k=top_k_retrieval,
        filters=filters,
    )
    stage1_ms=int((time.monotonic()-stage1_start)*1000)
    logger.info("stage1_complete",
    candidates_found=len(search_hits),
        embedding_cached=cache_hit,
        latency_ms=stage1_ms,
    )

    # stage 2 reasoning
    stage2_start = time.monotonic()
    # Only score the top N candidates (default 20) to control costs
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

    # SAVE SEARCH EVENT TO POSTGRESQL (non-blocking)
    # ═════════════════════════════════════════════════════════════
    search_event_id = str(uuid.uuid4())
    jd_hash = hashlib.sha256(jd_text.encode()).hexdigest()
    try:
        await db.execute(
            text("""
                INSERT INTO search_events (
                    id, recruiter_id, jd_text_hash, jd_raw_text,
                    candidates_searched,
                    latency_embedding_ms, latency_stage1_ms,
                    latency_stage2_ms, total_latency_ms,
                    embedding_cache_hit
                ) VALUES (
                    :id, :recruiter_id, :jd_hash, :jd_text,
                    :searched,
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
                "searched": len(search_hits),
                "embed_ms": 0 if cache_hit else stage1_ms,
                "stage1_ms": stage1_ms,
                "stage2_ms": stage2_ms,
                "total_ms": total_ms,
                "cache_hit": cache_hit,
            },
        )
        await db.commit()
    except Exception as e:
        logger.error("search_event_save_failed", error=str(e)[:200])
        # Don't fail the whole search just because logging failed
    return SearchResult(
        search_event_id=search_event_id,
        candidates=scored_candidates,
        total_candidates_searched=len(search_hits),
        latency_stage1_ms=stage1_ms,
        latency_stage2_ms=stage2_ms,
        total_latency_ms=total_ms,
        embedding_cache_hit=cache_hit,
    )


