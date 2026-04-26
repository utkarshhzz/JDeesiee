"""
LLM Reasoner — batch GPT-4o-mini scoring of candidates.

PERFORMANCE OPTIMIZATION:
    Instead of 20 individual API calls (~14s), we batch 10 candidates
    per prompt and run 2 prompts in parallel → total ~3-4s.

    Old approach: 20 calls × ~700ms each = 14s (even with asyncio.gather)
    New approach: 2 calls × ~2s each (in parallel) = ~3s

COST:
    GPT-4o-mini: $0.15/1M input tokens, $0.60/1M output tokens.
    Per search: ~2 calls × ~2500 tokens each = ~5K tokens = $0.001/search.
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


BATCH_SYSTEM_PROMPT = """You are an expert, unbiased technical recruiter AI. Your task is to evaluate how well MULTIPLE candidates match a job description.

SCORING RUBRIC:
- 90-100: Near-perfect match. ALL required skills, matching experience level, relevant domain.
- 75-89:  Strong match. Most required skills, close experience level. Minor gaps easily bridgeable.
- 60-74:  Moderate match. Some required skills but missing key requirements. Worth considering.
- 40-59:  Weak match. Significant skill gaps. Would need substantial training.
- 0-39:   Poor match. Fundamentally different skill set or experience level.

STRICT RULES:
1. Evaluate ONLY: technical skills, years of experience, domain expertise.
2. COMPLETELY IGNORE: name, gender, age, nationality, ethnicity, institution prestige, demographics.
3. Consider transferable skills (e.g. Django → FastAPI).
4. Weigh recent experience more heavily.

Respond with ONLY valid JSON — a JSON array of objects, one per candidate, in the SAME ORDER as presented:
[
    {
        "index": 0,
        "score": <integer 0-100>,
        "bullet_1": "<strongest match reason>",
        "bullet_2": "<biggest gap or secondary strength>"
    },
    ...
]"""


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
    """Build a single prompt containing all candidate profiles for batch scoring."""
    parts = [f"## Job Description\n{jd_text[:3000]}\n\n## Candidates to Evaluate\n"]

    for i, c in enumerate(candidates):
        parts.append(f"""### Candidate {i}
Section ({c.section_type}): {c.section_text[:800]}
Skills: {c.skills_str}
Experience: {c.years_of_experience} years | Education: {c.education_level}
Location: {c.location_city}, {c.location_country}
""")

    parts.append(f"\nScore all {len(candidates)} candidates. Return a JSON array with {len(candidates)} objects.")
    return "\n".join(parts)


async def _batch_score(
    jd_text: str,
    candidates: list[SearchHit],
    client: AsyncOpenAI,
) -> tuple[list[ScoredCandidate], int, int]:
    """
    Score a batch of candidates in a single LLM call.

    Returns:
        Tuple of (scored_candidates, latency_ms, tokens_used)
    """
    t0 = time.monotonic()
    prompt = _build_batch_prompt(jd_text, candidates)

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
                    {"role": "system", "content": BATCH_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

    content = response.choices[0].message.content
    tokens_used = response.usage.total_tokens if response.usage else 0
    latency_ms = int((time.monotonic() - t0) * 1000)

    # Parse the batch response
    scored: list[ScoredCandidate] = []
    try:
        parsed = json.loads(content)
        # Handle both {"candidates": [...]} and [...] formats
        if isinstance(parsed, dict):
            items = parsed.get("candidates", parsed.get("results", []))
            if not items:
                # Try to find any list value in the dict
                for v in parsed.values():
                    if isinstance(v, list):
                        items = v
                        break
        else:
            items = parsed

        for item in items:
            idx = item.get("index", len(scored))
            if idx < len(candidates):
                c = candidates[idx]
                scored.append(ScoredCandidate(
                    candidate_postgres_id=c.candidate_postgres_id,
                    match_score=max(0, min(100, int(item.get("score", 0)))),
                    vector_similarity=c.search_score,
                    justification_1=item.get("bullet_1", ""),
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
        logger.error("batch_parse_failed", error=str(e)[:200], content=content[:200])
        # Fallback: assign score 0 for unparseable candidates
        for c in candidates:
            if not any(s.candidate_postgres_id == c.candidate_postgres_id for s in scored):
                scored.append(ScoredCandidate(
                    candidate_postgres_id=c.candidate_postgres_id,
                    match_score=0,
                    vector_similarity=c.search_score,
                    justification_1="LLM response could not be parsed.",
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
    Score candidates using batch GPT-4o-mini calls.

    Splits candidates into batches of 10 and runs them in parallel.
    This reduces 20 individual API calls (~14s) to 2 parallel calls (~3s).
    """
    client = _get_openai_client()
    t0 = time.monotonic()

    # Take at most max_concurrent candidates
    to_score = candidates[:max_concurrent]

    # Split into batches of 10
    batch_size = 10
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

    # Run all batches in parallel
    tasks = [_batch_score(jd_text, batch, client) for batch in batches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect all scored candidates
    all_scored: list[ScoredCandidate] = []
    total_tokens = 0

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "batch_scoring_failed",
                batch_index=i,
                error=str(result)[:200],
            )
            # Fallback: assign score based on vector similarity
            for c in batches[i]:
                all_scored.append(ScoredCandidate(
                    candidate_postgres_id=c.candidate_postgres_id,
                    match_score=int(c.search_score * 100),
                    vector_similarity=c.search_score,
                    justification_1="Scoring failed — using vector similarity as fallback.",
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

    # Sort by match_score descending
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