"""
Vector Search Service — hybrid search against Azure AI Search.

Combines three search signals:
1. BM25 keyword search on section_text + skills_str
2. HNSW vector search on resume_embedding
3. Semantic reranking via Microsoft's cross-encoder

Results merged via RRF (Reciprocal Rank Fusion):
    score = sum(1 / (k + rank_i)) for each ranking system
Deduplication keeps only the highest-scoring hit per candidate.

SCALABILITY NOTE:
    HNSW is O(log N) average. At 10M vectors with ef_search=128,
    expected P99 latency < 80ms on Azure AI Search Standard S1.
    At 110M vectors, ~120ms. The bottleneck is NEVER here.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import structlog
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from app.config import settings

logger = structlog.get_logger()

# ── Module-level client (reused across requests) ────────────────────
_search_client: SearchClient | None = None


def _get_search_client() -> SearchClient:
    """Lazy-initialize the Azure AI Search client."""
    global _search_client
    if _search_client is None:
        _search_client = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(settings.AZURE_SEARCH_API_KEY),
        )
    return _search_client


@dataclass
class SearchHit:
    """A single candidate result from hybrid search."""
    candidate_postgres_id: str
    section_type: str
    section_text: str
    skills_str: str
    location_country: str
    location_city: str
    years_of_experience: int
    education_level: str
    search_score: float
    reranker_score: float | None = None


def _execute_search_sync(
    query_text: str,
    vector_query: VectorizedQuery,
    filter_str: str | None,
    top_k: int,
) -> list[dict]:
    """
    Run the actual Azure search call synchronously.
    Called via asyncio.to_thread() to prevent blocking the event loop.
    """
    client = _get_search_client()

    results = client.search(
        search_text=query_text,
        vector_queries=[vector_query],
        query_type="semantic",
        semantic_configuration_name="semantic-config",
        select=[
            "candidate_postgres_id",
            "section_type",
            "section_text",
            "skills_str",
            "location_country",
            "location_city",
            "years_of_experience",
            "education_level",
        ],
        filter=filter_str,
        top=top_k * 3,
    )

    # Materialize results in the thread (iteration is also sync)
    return [
        {
            "candidate_postgres_id": r["candidate_postgres_id"],
            "section_type": r.get("section_type", ""),
            "section_text": r.get("section_text", ""),
            "skills_str": r.get("skills_str", ""),
            "location_country": r.get("location_country", ""),
            "location_city": r.get("location_city", ""),
            "years_of_experience": r.get("years_of_experience", 0),
            "education_level": r.get("education_level", ""),
            "score": r.get("@search.score", 0.0),
            "reranker_score": r.get("@search.reranker_score", None),
        }
        for r in results
    ]


async def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    top_k: int = 100,
    filters: dict[str, Any] | None = None,
) -> tuple[list[SearchHit], int]:
    """
    Execute hybrid search against Azure AI Search.

    Uses asyncio.to_thread() to run the blocking Azure SDK call
    off the event loop — prevents blocking other concurrent requests.
    """
    t0 = time.monotonic()

    # ── Build OData filter string ────────────────────────────────
    filter_parts: list[str] = []
    if filters:
        if filters.get("location_country"):
            filter_parts.append(f"location_country eq '{filters['location_country']}'")
        if filters.get("location_city"):
            filter_parts.append(f"location_city eq '{filters['location_city']}'")
        if filters.get("min_years"):
            filter_parts.append(f"years_of_experience ge {filters['min_years']}")
        if filters.get("education_level"):
            filter_parts.append(f"education_level eq '{filters['education_level']}'")

    filter_str = " and ".join(filter_parts) if filter_parts else None

    # ── Build Vector Query ───────────────────────────────────────
    vector_query = VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k * 3,
        fields="resume_embedding",
        exhaustive=False,
    )

    # ── Execute in thread pool (non-blocking) ────────────────────
    raw_results = await asyncio.to_thread(
        _execute_search_sync,
        query_text,
        vector_query,
        filter_str,
        top_k,
    )

    # ── Deduplicate by candidate ─────────────────────────────────
    best_per_candidate: dict[str, SearchHit] = {}

    for r in raw_results:
        cid = r["candidate_postgres_id"]
        score = r["score"]
        reranker_score = r["reranker_score"]

        hit = SearchHit(
            candidate_postgres_id=cid,
            section_type=r["section_type"],
            section_text=r["section_text"],
            skills_str=r["skills_str"],
            location_country=r["location_country"],
            location_city=r["location_city"],
            years_of_experience=r["years_of_experience"],
            education_level=r["education_level"],
            search_score=score,
            reranker_score=reranker_score,
        )

        effective_score = reranker_score if reranker_score is not None else score
        existing = best_per_candidate.get(cid)
        if existing is None:
            best_per_candidate[cid] = hit
        else:
            existing_score = (
                existing.reranker_score
                if existing.reranker_score is not None
                else existing.search_score
            )
            if effective_score > existing_score:
                best_per_candidate[cid] = hit

    # ── Sort by score and take top_k ─────────────────────────────
    hits = sorted(
        best_per_candidate.values(),
        key=lambda h: h.reranker_score if h.reranker_score is not None else h.search_score,
        reverse=True,
    )[:top_k]

    latency_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "hybrid_search_complete",
        total_raw_hits=len(best_per_candidate),
        returned=len(hits),
        latency_ms=latency_ms,
        filter=filter_str,
    )

    return hits, latency_ms