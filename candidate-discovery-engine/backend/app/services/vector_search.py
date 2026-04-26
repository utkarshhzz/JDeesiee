"""
vector search service- hybrid search against azure ai search
we do 3 search signals
1-> BM25 keyword search on selection text + skills str
2-> hnsw vector dearch on resume_embedding
3-> semantic reranking via microsoft's cross-encoder

results merged via RRF(reciprocal rank fuusion)
 score = sum(1 / (k + rank_i)) for each ranking system
    This ensures a candidate who ranks #1 in vector AND #3 in BM25
    beats a candidate who ranks #2 in vector but #50 in BM25.
to rpevent duplication we keep highest scoring hit per candidate
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
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
    # Lazy initialsie the azure ai search client
    global _search_client
    if _search_client is None:
        _search_client=SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX_NAME,
            credential=AzureKeyCredential(settings.AZURE_SEARCH_API_KEY,)
        )
    return _search_client

@dataclass
class SearchHit:
    # A single candidate result from hybrid search
    candidate_postgres_id: str
    section_type: str
    section_text: str
    skills_str: str
    location_country: str
    location_city: str
    years_of_experience: int
    education_level: str
    search_score: float        # RRF combined score from Azure
    reranker_score: float | None = None  # Semantic reranker score (if available)

async def hybrid_search(
    query_text:str,
    query_embedding:list[float],
    top_k:int=100,
    filters:dict[str,Any] | None=None,
) -> tuple[list[SearchHit],int]:
    """
    execute hybrid search against azure ai search
    Args:
        query_text:      The raw JD text (used for BM25 keyword matching)
        query_embedding: The JD embedding vector (used for HNSW vector search)
        top_k:           Number of unique candidates to return (default 100)
        filters:         Optional filters like {"location_country": "India", "min_years": 5}
    Returns:
        Tuple of (list of SearchHit, latency_ms)
    How it works internally:
        1. Azure receives both the text AND the vector
        2. BM25 runs on section_text + skills_str (keyword matching)
        3. HNSW runs on resume_embedding (vector similarity)
        4. RRF merges both rankings into a single score
        5. Semantic reranker re-orders the top results
        6. We deduplicate by candidate_postgres_id (keep best section)
    """
    client=_get_search_client()
    t0=time.monotonic()

    # build odata filter string 
    # Azure ai search uses OData filter synax:
    # location country eq india and years of experience ge 5
    filter_parts:list[str]=[]
    if filters:
        if filters.get("location_country"):
            filter_parts.append(f"location_country eq '{filters['location_country']}'")
        if filters.get("location_city"):
            filter_parts.append(f"location_city eq '{filters['location_city']}'")
        if filters.get("min_years"):
            filter_parts.append(f"years_of_experience ge {filters['min_years']}")
        if filters.get("education_level"):
            filter_parts.append(f"education_level eq '{filters['education_level']}'")
        
    filter_str=" and ".join(filter_parts) if filter_parts else None

    # Buld vector Query
    vector_query=VectorizedQuery(
        vector=query_embedding,
        k_nearest_neighbors=top_k * 3, #we fetch 3x more to account for dedup
        fields="resume embedding",
        exhaustive=False #Use hnsw index(fast) not brute force
    )
    # execute hybrid search 
    #search text -> BM25 keyword search
    #vector_queries-> hnsw vector search
    # query_type="semantic" -> adds semantic rerankinig on top
    results=client.search(
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
        top=top_k*3,
    )

    # deduplicate by candidate a candidate withh 5 section
    # may appear 5 times
    best_per_candidate:dict[str,SearchHit]={}
    for result in results:
        cid=result["candidate_postgres_id"]
        score=result.get("@search.score",0.0)
        reranker_score=result.get("@search.reranker_score",None)

        hit=SearchHit(
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
        # keep the hit with highest reranker score(or search score as fallbacl)
        effective_score=reranker_score if reranker_score is not None else score
        existing=best_per_candidate.get(cid)
        if existing is None:
            best_per_candidatepcid=hit

        else:
            existing_score=(
                existing.reranker_score
                if existing.reranker_score is not None
                else existing.search_score
            )
            if effective_score > existing_score:
                best_per_candidate[cid]= hit

        # sort by score and take top_k
        hits=sorted(
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