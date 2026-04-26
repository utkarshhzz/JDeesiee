"""
Enterprise Middleware — Request ID + Rate Limiting + Error Handling.

REQUEST ID:
    Every request gets a unique UUID attached. This UUID is:
    1. Added to all structlog entries for that request
    2. Returned in the X-Request-ID response header
    3. Used for tracing across services

RATE LIMITING:
    Uses Redis sliding window to enforce per-recruiter limits.
    Default: 30 searches/hour.

ERROR HANDLING:
    RFC 7807 Problem+JSON format for all errors.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = structlog.get_logger()


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request for observability."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        t0 = time.monotonic()

        # Bind request_id to structlog context for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        except Exception as e:
            logger.error(
                "unhandled_exception",
                path=request.url.path,
                error=str(e)[:200],
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "type": "about:blank",
                    "title": "Internal Server Error",
                    "status": 500,
                    "detail": "An unexpected error occurred. Check server logs.",
                    "instance": request.url.path,
                    "request_id": request_id,
                },
            )

        latency_ms = int((time.monotonic() - t0) * 1000)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(latency_ms)

        logger.info(
            "request_complete",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limit searches per recruiter using Redis sliding window.

    Only applies to POST /api/v1/search and POST /api/v1/ingest.
    Other endpoints are not rate limited.
    """

    RATE_LIMITED_PATHS = {"/api/v1/search", "/api/v1/ingest"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only rate limit search endpoints
        if request.method != "POST" or request.url.path not in self.RATE_LIMITED_PATHS:
            return await call_next(request)

        # Get recruiter identifier (IP for now, JWT sub in production)
        client_id = request.client.host if request.client else "unknown"
        redis = getattr(request.app.state, "redis", None)

        if redis:
            key = f"ratelimit:{client_id}:{int(time.time() // 3600)}"
            try:
                current = await redis.incr(key)
                if current == 1:
                    await redis.expire(key, 3600)

                remaining = max(0, settings.RATE_LIMIT_SEARCHES_PER_HOUR - current)

                if current > settings.RATE_LIMIT_SEARCHES_PER_HOUR:
                    logger.warning(
                        "rate_limit_exceeded",
                        client_id=client_id,
                        current=current,
                        limit=settings.RATE_LIMIT_SEARCHES_PER_HOUR,
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "type": "about:blank",
                            "title": "Too Many Requests",
                            "status": 429,
                            "detail": f"Rate limit exceeded. Maximum {settings.RATE_LIMIT_SEARCHES_PER_HOUR} searches per hour.",
                            "instance": request.url.path,
                        },
                        headers={
                            "Retry-After": "3600",
                            "X-RateLimit-Limit": str(settings.RATE_LIMIT_SEARCHES_PER_HOUR),
                            "X-RateLimit-Remaining": "0",
                        },
                    )
            except Exception as e:
                # Redis failure should not block searches
                logger.error("rate_limit_redis_error", error=str(e)[:100])
                remaining = settings.RATE_LIMIT_SEARCHES_PER_HOUR
        else:
            remaining = settings.RATE_LIMIT_SEARCHES_PER_HOUR

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_SEARCHES_PER_HOUR)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register RFC 7807 error handlers for common HTTP errors."""

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "type": "about:blank",
                "title": "Not Found",
                "status": 404,
                "detail": f"The path {request.url.path} was not found.",
                "instance": request.url.path,
            },
        )

    @app.exception_handler(422)
    async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "type": "about:blank",
                "title": "Validation Error",
                "status": 422,
                "detail": str(exc),
                "instance": request.url.path,
            },
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("internal_server_error", path=request.url.path, error=str(exc)[:200])
        return JSONResponse(
            status_code=500,
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred.",
                "instance": request.url.path,
            },
        )
