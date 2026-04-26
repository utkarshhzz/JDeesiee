# webhook dispatcher sends HTTP notifications for high scoring matches
"""
whne -> a candidate scores > 90 on the LLM match
what -> post a json payload to a configured webhook url
how-> hmac-sha256 sighned,3 eretries with exponenial backoff
evey attmept is logge dto webhook_events table

Security
the paylaod is signed with hmac-sha256 using a shared secret
the receiver n8n/Power automate checks the x-webhook-signature
header to verify the paylaod came from us,not an attacker

uses httpx.ASyncclient (async,non-blocking).
3 attempts with 2s->4s->8s backoff
if all 3 fail ,logs the error but doesnot crash the search

"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
logger=structlog.get_logger()

MAX_ATTEMPTS=3

REQUEST_TIMEOUT=10.0

def _sign_payload(payload_bytes:bytes,secret: str) -> str:
    """
    Create HMAC-SHA256 signature for webhook payload.
    The receiver should:
        1. Read the raw request body
        2. Compute HMAC-SHA256 with the same shared secret
        3. Compare with the X-Webhook-Signature header
        4. Reject if they don't match (tampered payload)
    """

    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

async def dispatch_webhook(
    match_result_id: str,
    candidate_id:str,
    match_score:float,
    justification_1:str,
    justification_2:str,
    jd_text:str,
    webhook_url:str,
    db:AsyncSession,

) -> bool:
    """
    Send a webhook notification for a high-scoring candidate match.
    Args:
        match_result_id: UUID of the match_results row
        candidate_id:    UUID of the candidate
        match_score:     The LLM match score (0-100)
        justification_1: First justification bullet
        justification_2: Second justification bullet
        jd_text:         The JD text (we send first 200 chars as snippet)
        webhook_url:     URL to POST the payload to
        db:              SQLAlchemy async session for logging attempts
    Returns:
        True if delivery succeeded, False if all attempts failed
    """
    
    payload={
         "event": "high_match_candidate",
        "candidate_id": candidate_id,
        "match_score": match_score,
        "justification_bullets": [justification_1, justification_2],
        "jd_snippet": jd_text[:200],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    signature=_sign_payload(payload_bytes,settings.WEBHOOK_HMAC_SECRET)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "User-Agent": "CandidateDiscoveryEngine/1.0",
    }

    succeeded=False

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            event_id = str(uuid.uuid4())
            t0 = time.monotonic()
            http_status = None
            response_body = None
            try:
                response = await client.post(
                    webhook_url,
                    content=payload_bytes,
                    headers=headers,
                )
                http_status = response.status_code
                response_body = response.text[:500]
                if 200 <= http_status < 300:
                    succeeded = True
                    logger.info(
                        "webhook_delivered",
                        candidate_id=candidate_id,
                        attempt=attempt,
                        status=http_status,
                        latency_ms=int((time.monotonic() - t0) * 1000),
                    )
                else:
                    logger.warning(
                        "webhook_non_2xx",
                        candidate_id=candidate_id,
                        attempt=attempt,
                        status=http_status,
                    )
            except Exception as e:
                logger.error(
                    "webhook_request_failed",
                    candidate_id=candidate_id,
                    attempt=attempt,
                    error=str(e)[:200],
                )
            # ── Log this attempt to webhook_events table ─────────
            try:
                await db.execute(
                    text("""
                        INSERT INTO webhook_events (
                            id, match_result_id, webhook_url, payload,
                            http_status, response_body, attempt_number,
                            succeeded_at
                        ) VALUES (
                            :id, :match_result_id, :url, :payload,
                            :status, :response, :attempt,
                            :succeeded_at
                        )
                    """),
                    {
                        "id": event_id,
                        "match_result_id": match_result_id,
                        "url": webhook_url,
                        "payload": json.dumps(payload),
                        "status": http_status,
                        "response": response_body,
                        "attempt": attempt,
                        "succeeded_at": (
                            datetime.now(timezone.utc) if succeeded else None
                        ),
                    },
                )
                await db.commit()
            except Exception as e:
                logger.error("webhook_log_failed", error=str(e)[:100])
            if succeeded:
                return True
            # Wait before retry: 2s, 4s, 8s (exponential backoff)
            if attempt < MAX_ATTEMPTS:
                import asyncio
                await asyncio.sleep(2 ** attempt)
    logger.error(
        "webhook_all_attempts_failed",
        candidate_id=candidate_id,
        match_result_id=match_result_id,
        attempts=MAX_ATTEMPTS,
    )
    return False