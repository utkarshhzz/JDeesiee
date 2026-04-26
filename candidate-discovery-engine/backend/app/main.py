from __future__ import annotations

from contextlib import asynccontextmanager
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.logging import setup_logging
from app.core.middleware import (
    RequestIdMiddleware,
    RateLimitMiddleware,
    register_exception_handlers,
)
from app.db.session import async_session_factory
from app.api.v1.search import router as search_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.candidates import router as candidates_router

setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage startup and shutdown resources.
    On startup: create Redis connection pool.
    On shutdown: close Redis pool, release all connections.
    """
    logger.info("app_starting", environment=settings.ENVIRONMENT)

    # Redis connection pool
    app.state.redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )

    # Verify Redis connection
    try:
        await app.state.redis.ping()
        logger.info("redis_connected", url=settings.REDIS_URL)
    except Exception as e:
        logger.error("redis_connection_failed", error=str(e))

    app.state.db_factory = async_session_factory
    yield
    await app.state.redis.close()
    logger.info("app_shutdown_complete")


def create_app() -> FastAPI:
    """Factory function — creates and configures the FastAPI app."""
    app = FastAPI(
        title="Candidate Discovery Engine",
        description="AI-powered candidate search across 110M+ resumes",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── Middleware (order matters: outermost runs first) ──────────
    # 1. Request ID — wraps everything, adds X-Request-ID header
    app.add_middleware(RequestIdMiddleware)
    # 2. Rate Limiting — checks Redis before hitting the route
    app.add_middleware(RateLimitMiddleware)
    # 3. CORS — allows React frontend to call this API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── RFC 7807 Error Handlers ──────────────────────────────────
    register_exception_handlers(app)

    # ── Mount API routes ─────────────────────────────────────────
    app.include_router(search_router, prefix="/api/v1")
    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(candidates_router, prefix="/api/v1")

    # ── Health check ─────────────────────────────────────────────
    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "1.0.0"}

    return app


# This is what uvicorn imports: `uvicorn app.main:app`
app = create_app()