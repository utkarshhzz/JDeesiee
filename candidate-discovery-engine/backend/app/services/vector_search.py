"""
Vector Search Service — hybrid search against Azure AI Search.

Combines three search signals:
1. BM25 keyword search on section_text + skills_str
2. HNSW vector search on resume_embedding
3. Semantic reranking via Microsoft's cross-encoder

Results merged via RRF (Reciprocal Rank Fusion):
    score = sum(1 / (k + rank_i)) for each ranking system
Deduplication keeps only the highest-scoring hit per candidate.
"""

from __future__ import annotations

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


async def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    top_k: int = 100,
    filters: dict[str, Any] | None = None,
) -> tuple[list[SearchHit], int]:
    """
    Execute hybrid search against Azure AI Search.

    Args:
        query_text:      The raw JD text (used for BM25 keyword matching)
        query_embedding: The JD embedding vector (used for HNSW vector search)
        top_k:           Number of unique candidates to return (default 100)
        filters:         Optional filters like {"location_country": "India", "min_years": 5}

    Returns:
        Tuple of (list of SearchHit, latency_ms)
    """
    client = _get_search_client()
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
        fields="resume_embedding",   # Must match index field name exactly
        exhaustive=False,
    )

    # ── Execute Hybrid Search ────────────────────────────────────
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

    # ── Deduplicate by candidate ─────────────────────────────────
    best_per_candidate: dict[str, SearchHit] = {}

    for result in results:
        cid = result["candidate_postgres_id"]
        score = result.get("@search.score", 0.0)
        reranker_score = result.get("@search.reranker_score", None)

        hit = SearchHit(
            candidate_postgres_id=cid,
            section_type=result.get("section_type", ""),
            section_text=result.get("section_text", ""),
            skills_str=result.get("skills_str", ""),
            location_country=result.get("location_country", ""),
            location_city=result.get("location_city", ""),
            years_of_experience=result.get("years_of_experience", 0),
            education_level=result.get("education_level", ""),
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

    # ── Sort by score and take top_k (OUTSIDE the for loop) ──────
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