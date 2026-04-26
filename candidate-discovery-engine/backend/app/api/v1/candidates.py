# candiadte api - get .api/v1/candidates/{id}
"""
Returns the full profile of a single candidate, including their
match history (how they scored in past searches).
"""

from __future__ import annotations

from typing import Any
import structlog
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import async_session_factory

logger = structlog.get_logger()
router = APIRouter(tags=["candidates"])

class CandidateDetail(BaseModel):
    # full candidate profile returned by get /candidate/{id}
    id: str
    full_name: str
    email: str | None
    phone: str | None
    location_city: str | None
    location_country: str | None
    years_of_experience: int | None
    current_title: str | None
    current_company: str | None
    education_level: str | None
    skills: list[str]
    resume_text: str | None
    is_active: bool


class MatchHistoryItem(BaseModel):
    """One past search where this candidate was scored."""
    search_event_id: str
    match_score: float
    justification_1: str
    justification_2: str
    rank: int
    searched_at: str


class CandidateDetailResponse(BaseModel):
    candidate: CandidateDetail
    match_history: list[MatchHistoryItem]


@router.get("/candidates/{candidate_id}",response_model=CandidateDetailResponse)
async def get_candidate(candidate_id:str):
    """
    Get full candidate profile + their match history.
    Match history shows every search where this candidate appeared,
    with their score and rank. This helps recruiters see if the same
    candidate keeps showing up across different JDs (strong generalist).
    """

    async with async_session_factory() as db:
        result = await db.execute(
            text("""
            SELECT id,full_name, email, phone,
                   location_city, location_country,
                    years_of_experience, current_title,
                    current_company, education_level,
                    skills, resume_text, is_active
                FROM candidates
                WHERE id = :id
            """),{"id":candidate_id}
        )
        row=result.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate = CandidateDetail(
            id=str(row[0]),
            full_name=row[1],
            email=row[2],
            phone=row[3],
            location_city=row[4],
            location_country=row[5],
            years_of_experience=row[6],
            current_title=row[7],
            current_company=row[8],
            education_level=row[9],
            skills=row[10] if row[10] else [],
            resume_text=row[11],
            is_active=row[12],
        )

        # ── Fetch match history ──────────────────────────────────
        history_result = await db.execute(
            text("""
                SELECT mr.search_event_id, mr.match_score,
                       mr.justification_bullet_1, mr.justification_bullet_2,
                       mr.rank, mr.created_at
                FROM match_results mr
                WHERE mr.candidate_id = :cid
                ORDER BY mr.created_at DESC
                LIMIT 20
            """),
            {"cid": candidate_id},
        )
        match_history = []
        for hr in history_result.fetchall():
            match_history.append(MatchHistoryItem(
                search_event_id=str(hr[0]),
                match_score=float(hr[1]),
                justification_1=hr[2],
                justification_2=hr[3],
                rank=hr[4],
                searched_at=hr[5].isoformat() if hr[5] else "",
            ))
    return CandidateDetailResponse(
        candidate=candidate,
        match_history=match_history,
    )
