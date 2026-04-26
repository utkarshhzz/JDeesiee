"""
Embedding service — generates JD embeddings with Redis caching.

Flow:
    Hash JD text (SHA-256) → cache key → check Redis
    Cache HIT → return immediately (< 5ms)
    Cache MISS → call OpenAI → store in Redis (TTL 24h) → return
"""

import hashlib
import json
import time
from typing import TYPE_CHECKING

import structlog
from openai import AsyncOpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = structlog.get_logger()

# ── Module-level async client (created once, reused) ────────────────
# Why AsyncOpenAI instead of sync OpenAI?
#   Sync OpenAI blocks the event loop in async FastAPI.
#   AsyncOpenAI uses aiohttp under the hood → non-blocking.
_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    """Lazy-initialize the async OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


async def get_embedding(
    text: str,
    redis: "aioredis.Redis",
) -> tuple[list[float], bool]:
    """
    Generate an embedding for the given text, with Redis caching.

    Args:
        text: The JD text to embed (already cleaned/truncated)
        redis: Async Redis client instance

    Returns:
        Tuple of (embedding_vector, cache_hit)
        - embedding_vector: list of 1536 floats
        - cache_hit: True if served from cache, False if called OpenAI
    """
    # Step 1: Hash the text → deterministic cache key
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cache_key = f"jd_embedding:{text_hash}"

    # Step 2: Check Redis cache
    try:
        cached = await redis.get(cache_key)
        if cached is not None:
            embedding = json.loads(cached)
            logger.info("embedding_cache_hit", hash=text_hash[:12])
            return embedding, True
    except Exception as e:
        logger.warning("redis_cache_read_failed", error=str(e)[:100])

    # Step 3: Cache MISS — call OpenAI with retry
    logger.info("embedding_cache_miss", hash=text_hash[:12])
    t0 = time.monotonic()
    client = _get_openai_client()

    embedding = None
    async for attempt in AsyncRetrying(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((Exception,)),
    ):
        with attempt:
            # Now truly async — doesn't block the event loop
            response = await client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=[text],
            )
            embedding = response.data[0].embedding

    latency_ms = int((time.monotonic() - t0) * 1000)
    logger.info("embedding_generated", latency_ms=latency_ms, dimensions=len(embedding))

    # Step 4: Store in Redis cache (TTL = 24 hours)
    try:
        await redis.set(
            cache_key,
            json.dumps(embedding),
            ex=settings.EMBEDDING_CACHE_TTL,
        )
        logger.debug("embedding_cached", hash=text_hash[:12])
    except Exception as e:
        logger.warning("redis_cache_write_failed", error=str(e)[:100])

    return embedding, False