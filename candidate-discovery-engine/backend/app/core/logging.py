"""
Structured JSON logging configuration using structlog.

WHY JSON LOGS:
    Plain text: "INFO: Generated embedding in 245ms (cache miss)"
    JSON:       {"event": "embedding_generated", "latency_ms": 245, "cache_hit": false}

    JSON logs let Azure Application Insights search by any field.
    
HOW TO USE IN ANY FILE:
    import structlog
    logger = structlog.get_logger()
    logger.info("search_started", recruiter_id="user-123")
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(debug: bool = False) -> None:
    """
    Configure structlog for the entire application.
    Call ONCE during app startup (in main.py lifespan).

    Args:
        debug: True = pretty console output, False = JSON for production
    """
    if debug:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.StackInfoRenderer(),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )
