"""
LLM Reasoner — concurrent GPT-4o-mini scoring of candidates.

Takes top N candidates from vector search and scores each against the JD.
Uses AsyncOpenAI for true async concurrency — 20 parallel calls in ~800ms
instead of 20 sequential calls taking ~8 seconds.

COST:
    GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens.
    Per search: ~20 calls × ~500 tokens each = ~10K tokens = $0.0015/search.
    At 1000 searches/day = $1.50/day.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass

import structlog
from openai import AsyncOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.services.vector_search import SearchHit

logger = structlog.get_logger()

# ── Module-level async client ────────────────────────────────────────
_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


SYSTEM_PROMPT = """You are an expert technical recruiter AI. Your job is to evaluate how well a candidate matches a job description.

SCORING RUBRIC:
- 90-100: Near-perfect match. Candidate has ALL required skills, matching experience level, and relevant domain experience.
- 75-89:  Strong match. Candidate has most required skills, close experience level. Minor gaps are easily bridgeable.
- 60-74:  Moderate match. Candidate has some required skills but is missing key requirements. Worth considering.
- 40-59:  Weak match. Significant skill gaps. Candidate would need substantial training.
- 0-39:   Poor match. Fundamentally different skill set or experience level.

IMPORTANT RULES:
1. Score based on SKILLS and EXPERIENCE alignment, not demographics.
2. Consider transferable skills (e.g., "Django" experience transfers to "FastAPI").
3. Weigh recent experience more heavily than older experience.
4. A candidate who exceeds requirements should still score 90+, not be penalized.

Respond ONLY with valid JSON in this exact format:
{
    "score": <integer 0-100>,
    "justification_1": "<one sentence: strongest match reason>",
    "justification_2": "<one sentence: second strongest match reason>",
    "justification_3": "<one sentence: biggest gap or concern>"
}"""


@dataclass
class ScoredCandidate:
    """A candidate after LLM scoring."""
    candidate_postgres_id: str
    match_score: float
    vector_similarity: float
    justification_1: str
    justification_2: str
    justification_3: str
    section_type: str
    section_text: str
    skills_str: str
    location_country: str
    location_city: str
    years_of_experience: int
    education_level: str
    latency_ms: int
    tokens_used: int


async def _score_single_candidate(
    jd_text: str,
    candidate: SearchHit,
    client: AsyncOpenAI,
) -> ScoredCandidate:
    """
    Score a single candidate against the JD using GPT-4o-mini.

    Now fully async — uses AsyncOpenAI so it doesn't block the event loop.
    No need for asyncio.to_thread anymore.
    """
    t0 = time.monotonic()

    user_prompt = f"""## Job Description
{jd_text[:3000]}

## Candidate Resume Section ({candidate.section_type})
{candidate.section_text[:3000]}

## Candidate Skills
{candidate.skills_str}

## Candidate Info
- Location: {candidate.location_city}, {candidate.location_country}
- Experience: {candidate.years_of_experience} years
- Education: {candidate.education_level}

Score this candidate against the job description. Respond with JSON only."""

    # Retry with exponential backoff on any error
    response = None
    async for attempt in AsyncRetrying(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((Exception,)),
    ):
        with attempt:
            response = await client.chat.completions.create(
                model=settings.OPENAI_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=200,
                response_format={"type": "json_object"},
            )

    content = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0
    latency_ms = int((time.monotonic() - t0) * 1000)

    try:
        parsed = json.loads(content)
        score = max(0, min(100, int(parsed.get("score", 0))))
        j1 = parsed.get("justification_1", "No justification provided.")
        j2 = parsed.get("justification_2", "")
        j3 = parsed.get("justification_3", "")
    except (json.JSONDecodeError, ValueError):
        logger.warning("llm_parse_failed", content=content[:100])
        score = 0
        j1 = "Failed to parse LLM response."
        j2 = ""
        j3 = ""

    return ScoredCandidate(
        candidate_postgres_id=candidate.candidate_postgres_id,
        match_score=score,
        vector_similarity=candidate.search_score,
        justification_1=j1,
        justification_2=j2,
        justification_3=j3,
        section_type=candidate.section_type,
        section_text=candidate.section_text,
        skills_str=candidate.skills_str,
        location_country=candidate.location_country,
        location_city=candidate.location_city,
        years_of_experience=candidate.years_of_experience,
        education_level=candidate.education_level,
        latency_ms=latency_ms,
        tokens_used=tokens_used,
    )


async def score_candidates(
    jd_text: str,
    candidates: list[SearchHit],
    max_concurrent: int = 20,
) -> tuple[list[ScoredCandidate], int]:
    """
    Score multiple candidates concurrently using GPT-4o-mini.

    Uses asyncio.gather with true async calls — no thread pool needed.
    All 20 calls run concurrently on the event loop without blocking.
    """
    client = _get_openai_client()
    t0 = time.monotonic()

    # Create async tasks (true async, not thread-based)
    tasks = [
        _score_single_candidate(jd_text, candidate, client)
        for candidate in candidates[:max_concurrent]
    ]

    # Wait for ALL tasks to complete concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out errors and collect successful scores
    scored: list[ScoredCandidate] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "scoring_failed",
                candidate_id=candidates[i].candidate_postgres_id,
                error=str(result)[:100],
            )
        else:
            scored.append(result)

    # Sort by match_score descending (best candidate first)
    scored.sort(key=lambda s: s.match_score, reverse=True)

    total_latency_ms = int((time.monotonic() - t0) * 1000)
    total_tokens = sum(s.tokens_used for s in scored)

    logger.info(
        "scoring_complete",
        candidates_scored=len(scored),
        total_latency_ms=total_latency_ms,
        total_tokens=total_tokens,
        top_score=scored[0].match_score if scored else 0,
    )

    return scored, total_latency_ms