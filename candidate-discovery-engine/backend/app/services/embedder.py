"""
embedding service- generate 3d embedding with redis caching
flow
hash jd text sha 256-> cache key
check redis for cache embedding
cache hit return immediately
cache miss so call openai store in redis and return
"""

import hashlib
import json
import time
from typing import TYPE_CHECKING

import structlog
from openai import OpenAI
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from app.config import settings
if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger=structlog.get_logger()

_openai_client:OpenAI | None=None

def _get_openai_client() -> OpenAI:
    # lazy initialising th eopenai client
    global _openai_client
    if _openai_client is None:
        _openai_client=OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client

async def get_embedding(
    text:str,
    redis: aioredis.Redis,
)-> tuple[list[float],bool]:
    """
    generate embedding for the given text ,with redis caching
    args is the jd text to embed and redis async redisc lient isance
    returns tuple of embedding vector and cache hit
    returns tuple of embedding vector list of 1536 vectors and cache hit true/false
    latency: <5ms if hit else 300 ms

    """

    # 1-> hash the text
    text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()
    cache_key=f"jd_embedding:{text_hash}"

    # step 2 : check redis cache
    try:
        cached =await redis.get(cache_key)
        if cached is not None:
            embedding=json.loads(cached)
            logger.info("embedding_cache_hit",hash=text_hash[:12])
            return embedding,True
    except Exception as e:
        logger.warning("Redis cache read failed",error=str(e)[:100])

    # step3 CAche miss so call openai with retry
    logger.info("embedding_cache_miss", hash=text_hash[:12])
    t0=time.monotonic()
    client=_get_openai_client()

    embedding=None
    async for attempt in AsyncRetrying(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((Exception,)),
    ):
    with attempt:
        response=client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=[text],
        )
        embedding=response.data[0].embedding
    latency_ms = int((time.monotonic() - t0) * 1000)
    logger.info("embedding_generated", latency_ms=latency_ms, dimensions=len(embedding))

    # Step 3 strre in redis cache limit =24 hrs
    try:
        await redis.set(
            cache_key,
            json.dumps(embedding),
            ex=settings.EMBEDDING_CACHE_TTL,
        )
        logger.debug("embedding_cached", hash=text_hash[:12])
    except Exception as e:
        # Cache write failed? Not critical — next time we'll just call OpenAI again
        logger.warning("redis_cache_write_failed", error=str(e)[:100])
    return embedding, False