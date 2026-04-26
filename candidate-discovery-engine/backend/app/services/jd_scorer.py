"""
JD Quality Scorer — evaluates job description quality before searching.

Scores the JD on three dimensions using GPT-4o-mini:
    1. Clarity (1-10): How clear and well-structured is the JD?
    2. Specificity (1-10): Are required skills concrete and measurable?
    3. Inclusivity (1-10): Does the language avoid unnecessary barriers?

CACHING: Results cached in Redis (same hash as embedding) for 24h.
On cache hit, JD quality is returned in <5ms instead of ~3s.

IMPORTANT: This runs IN PARALLEL with Stage 1 search, so it adds
ZERO additional latency to the total pipeline on first call too.
"""

from __future__ import annotations

import hashlib
import json
import time

import structlog
from openai import AsyncOpenAI

from app.config import settings

logger = structlog.get_logger()

_openai_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


JD_QUALITY_PROMPT = """You are an expert HR consultant. Analyze this job description and score it on three dimensions.

SCORING:
- clarity (1-10): Is the JD well-structured? Are responsibilities clear? Is the role well-defined?
- specificity (1-10): Are required skills concrete (e.g. "5+ years Python" vs "programming experience")? Are requirements measurable?
- inclusivity (1-10): Does the language avoid unnecessary barriers? Are there too many "nice-to-have" requirements that could discourage diverse candidates? Is gender-neutral language used?

Also provide 2-3 short, actionable improvement suggestions.

Respond with ONLY valid JSON:
{
    "clarity": <integer 1-10>,
    "specificity": <integer 1-10>,
    "inclusivity": <integer 1-10>,
    "suggestions": ["suggestion 1", "suggestion 2"]
}"""


async def score_jd_quality(jd_text: str, redis=None) -> dict | None:
    """
    Score a job description on clarity, specificity, and inclusivity.
    Results are cached in Redis for 24 hours.

    Returns:
        Dict with clarity, specificity, inclusivity scores (1-10),
        overall average, and list of suggestions.
        Returns None on failure (non-critical feature).
    """
    text_hash = hashlib.sha256(jd_text.encode("utf-8")).hexdigest()
    cache_key = f"jd_quality:{text_hash}"

    # Check Redis cache
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                logger.info("jd_quality_cache_hit", hash=text_hash[:12])
                return json.loads(cached)
        except Exception as e:
            logger.warning("jd_quality_cache_read_failed", error=str(e)[:100])

    t0 = time.monotonic()
    client = _get_client()

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": JD_QUALITY_PROMPT},
                {"role": "user", "content": jd_text[:3000]},
            ],
            temperature=0.0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        parsed = json.loads(content)

        clarity = max(1, min(10, int(parsed.get("clarity", 5))))
        specificity = max(1, min(10, int(parsed.get("specificity", 5))))
        inclusivity = max(1, min(10, int(parsed.get("inclusivity", 5))))
        suggestions = parsed.get("suggestions", [])

        latency_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "jd_quality_scored",
            clarity=clarity,
            specificity=specificity,
            inclusivity=inclusivity,
            latency_ms=latency_ms,
        )

        result = {
            "clarity": clarity,
            "specificity": specificity,
            "inclusivity": inclusivity,
            "overall": round((clarity + specificity + inclusivity) / 3, 1),
            "suggestions": suggestions[:5],
        }

        # Cache result for 24 hours
        if redis:
            try:
                await redis.set(cache_key, json.dumps(result), ex=settings.EMBEDDING_CACHE_TTL)
                logger.debug("jd_quality_cached", hash=text_hash[:12])
            except Exception as e:
                logger.warning("jd_quality_cache_write_failed", error=str(e)[:100])

        return result

    except Exception as e:
        logger.warning("jd_quality_scoring_failed", error=str(e)[:200])
        return None
