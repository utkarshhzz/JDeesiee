"""
LLM Reasoner — fast batch GPT-4o-mini scoring of candidates.

STRATEGY: 4 batches of 5 candidates, ALL running in parallel.
    - Each batch has ~5 candidate profiles → shorter prompt → faster response
    - All 4 batches run concurrently via asyncio.gather
    - Wall clock time = time of SLOWEST single batch ≈ 3s
    - Full 20 candidates scored with FULL accuracy (800 char text, detailed rubric)

    Old: 20 individual calls → 14s
    v2:  2 batches of 10 → 10.6s  
    v3:  4 batches of 5  → ~3-4s  ← current

COST:
    GPT-4o-mini: $0.15/1M input, $0.60/1M output.
    Per search: ~4 calls × ~2000 tokens = ~8K tokens ≈ $0.0012/search.
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

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


BATCH_SYSTEM_PROMPT = """You are an expert, unbiased technical recruiter AI. Your task is to evaluate how well MULTIPLE candidates match a job description.

SCORING RUBRIC:
- 90-100: Near-perfect match. Candidate has ALL required skills, matching experience level, and relevant domain experience.
- 75-89:  Strong match. Candidate has most required skills, close experience level. Minor gaps are easily bridgeable.
- 60-74:  Moderate match. Candidate has some required skills but is missing key requirements. Worth considering.
- 40-59:  Weak match. Significant skill gaps. Candidate would need substantial training.
- 0-39:   Poor match. Fundamentally different skill set or experience level.

STRICT RULES:
1. Evaluate ONLY: technical skills, years of experience, domain expertise, and measurable achievements.
2. COMPLETELY IGNORE and DO NOT MENTION: candidate name, gender, age, nationality, ethnicity, educational institution prestige, location, or any demographic information.
3. Consider transferable skills (e.g., "Django" experience transfers to "FastAPI").
4. Weigh recent experience more heavily than older experience.
5. A candidate who exceeds requirements should still score 90+, not be penalized.

Respond with ONLY valid JSON — a JSON object with a "candidates" array:
{"candidates": [{"index": 0, "score": 85, "bullet_1": "<strongest match reason>", "bullet_2": "<biggest gap or secondary strength>"}, ...]}

Each candidate MUST have an entry. Maintain the SAME ORDER as presented."""


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


def _build_batch_prompt(jd_text: str, candidates: list[SearchHit]) -> str:
    """
    Build a prompt with candidate profiles for batch scoring.
    Uses full 800-char section text for maximum accuracy.
    """
    parts = [f"## Job Description\n{jd_text[:3000]}\n\n## Candidates to Evaluate\n"]

    for i, c in enumerate(candidates):
        parts.append(
            f"### Candidate {i}\n"
            f"Section ({c.section_type}): {c.section_text[:800]}\n"
            f"Skills: {c.skills_str}\n"
            f"Experience: {c.years_of_experience} years | Education: {c.education_level}\n"
            f"Location: {c.location_city}, {c.location_country}\n"
        )

    parts.append(f"\nScore all {len(candidates)} candidates. Return JSON with {len(candidates)} objects.")
    return "\n".join(parts)


async def _batch_score(
    jd_text: str,
    candidates: list[SearchHit],
    client: AsyncOpenAI,
    batch_index: int,
) -> tuple[list[ScoredCandidate], int, int]:
    """Score a batch of candidates in a single LLM call (full accuracy)."""
    t0 = time.monotonic()
    prompt = _build_batch_prompt(jd_text, candidates)

    response = None
    async for attempt in AsyncRetrying(
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((Exception,)),
    ):
        with attempt:
            response = await client.chat.completions.create(
                model=settings.OPENAI_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=800,
                response_format={"type": "json_object"},
            )

    content = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0
    latency_ms = int((time.monotonic() - t0) * 1000)

    logger.info(
        "batch_scored",
        batch_index=batch_index,
        latency_ms=latency_ms,
        tokens=tokens_used,
        candidates_in_batch=len(candidates),
    )

    scored: list[ScoredCandidate] = []
    try:
        parsed = json.loads(content)

        # Handle various response formats the LLM might use
        items: list = []
        if isinstance(parsed, dict):
            # Try common keys: "candidates", "results", or any list value
            for key in ["candidates", "results"]:
                if key in parsed and isinstance(parsed[key], list):
                    items = parsed[key]
                    break
            if not items:
                for v in parsed.values():
                    if isinstance(v, list):
                        items = v
                        break
            # Single object response
            if not items and "score" in parsed:
                items = [parsed]
        elif isinstance(parsed, list):
            items = parsed

        for item in items:
            idx = item.get("index", len(scored))
            if idx < len(candidates):
                c = candidates[idx]
                scored.append(ScoredCandidate(
                    candidate_postgres_id=c.candidate_postgres_id,
                    match_score=max(0, min(100, int(item.get("score", 0)))),
                    vector_similarity=c.search_score,
                    justification_1=item.get("bullet_1", "No justification provided."),
                    justification_2=item.get("bullet_2", ""),
                    justification_3="",
                    section_type=c.section_type,
                    section_text=c.section_text,
                    skills_str=c.skills_str,
                    location_country=c.location_country,
                    location_city=c.location_city,
                    years_of_experience=c.years_of_experience,
                    education_level=c.education_level,
                    latency_ms=latency_ms,
                    tokens_used=tokens_used // max(1, len(items)),
                ))
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("batch_parse_failed", batch=batch_index, error=str(e)[:200])

    # Fill any missing candidates with fallback scores based on vector similarity
    scored_ids = {s.candidate_postgres_id for s in scored}
    for c in candidates:
        if c.candidate_postgres_id not in scored_ids:
            scored.append(ScoredCandidate(
                candidate_postgres_id=c.candidate_postgres_id,
                match_score=max(0, min(100, int(c.search_score * 5000))),
                vector_similarity=c.search_score,
                justification_1="Scored via vector similarity (LLM parse fallback).",
                justification_2="",
                justification_3="",
                section_type=c.section_type,
                section_text=c.section_text,
                skills_str=c.skills_str,
                location_country=c.location_country,
                location_city=c.location_city,
                years_of_experience=c.years_of_experience,
                education_level=c.education_level,
                latency_ms=latency_ms,
                tokens_used=0,
            ))

    return scored, latency_ms, tokens_used


async def score_candidates(
    jd_text: str,
    candidates: list[SearchHit],
    max_concurrent: int = 20,
) -> tuple[list[ScoredCandidate], int]:
    """
    Score ALL 20 candidates using parallel batch GPT-4o-mini calls.

    Strategy: 4 batches of 5, ALL running concurrently.
    - Each batch has 5 candidates → ~2000 tokens input → ~3s response
    - All 4 run in parallel → wall clock = slowest batch ≈ 3s
    - Full accuracy: 800-char text, detailed rubric, no shortcuts
    """
    client = _get_openai_client()
    t0 = time.monotonic()

    to_score = candidates[:max_concurrent]

    # 4 batches of 5 — optimal balance of parallelism and prompt size
    batch_size = 5
    batches = [
        to_score[i:i + batch_size]
        for i in range(0, len(to_score), batch_size)
    ]

    logger.info(
        "batch_scoring_start",
        total_candidates=len(to_score),
        num_batches=len(batches),
        batch_size=batch_size,
    )

    # Run ALL batches in parallel — this is the key speed win
    tasks = [
        _batch_score(jd_text, batch, client, i)
        for i, batch in enumerate(batches)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_scored: list[ScoredCandidate] = []
    total_tokens = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("batch_failed", batch=i, error=str(result)[:200])
            # Fallback: use vector similarity as score
            for c in batches[i]:
                all_scored.append(ScoredCandidate(
                    candidate_postgres_id=c.candidate_postgres_id,
                    match_score=max(0, min(100, int(c.search_score * 5000))),
                    vector_similarity=c.search_score,
                    justification_1="Scoring failed — using vector similarity fallback.",
                    justification_2="",
                    justification_3="",
                    section_type=c.section_type,
                    section_text=c.section_text,
                    skills_str=c.skills_str,
                    location_country=c.location_country,
                    location_city=c.location_city,
                    years_of_experience=c.years_of_experience,
                    education_level=c.education_level,
                    latency_ms=0,
                    tokens_used=0,
                ))
        else:
            scored, _, tokens = result
            all_scored.extend(scored)
            total_tokens += tokens

    # Sort by match_score descending (best candidate first)
    all_scored.sort(key=lambda s: s.match_score, reverse=True)

    total_latency_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        "scoring_complete",
        candidates_scored=len(all_scored),
        total_latency_ms=total_latency_ms,
        total_tokens=total_tokens,
        top_score=all_scored[0].match_score if all_scored else 0,
    )

    return all_scored, total_latency_ms