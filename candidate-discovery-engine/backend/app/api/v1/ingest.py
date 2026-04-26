"""
JD file uplaoder with post /api/v1/ingest
Data ingestion pipeline
accepts PDF,DOCX or plain text file uplaods
extracts text=> runs full search pipeline -> returns ranked candidates

as file upload needs multipart/form-data,not JSON
the extraction step adds latency 
we archive the original file to azure blob for audit
different validation  rules (file size,type checking)
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter,FIle,Form,HTTPException,Request,UploadFile
from pydantic import BaseModel

from app.db.session import async_session_factory
from app.services.extractor import extract_text_from_bytes
from app.services.pipeline import execute_search
from app.api.v1.search import SearchResponse, LatencyBreakdown, CandidateResponse
logger = structlog.get_logger()
router = APIRouter(tags=["ingest"])
# Max file size: 10MB (resumes should never be this large)
MAX_FILE_SIZE = 10 * 1024 * 1024

@router.post("/ingest",response_model=SearchResponse)
async def ingest_jd_file(
    request:Request,
    file:UploadFile=File(...,description="PDF,DOCX,TXT file"),
    top_k: int = Form(default=20, ge=1, le=50),
    location_country: str | None = Form(default=None),
    min_years: int | None = Form(default=None),
):
    """
    Upload a JD file and search for matching candidates.
    This endpoint:
    1. Validates file size and type (via magic bytes, NOT filename)
    2. Extracts clean text from the document
    3. Runs the full 2-stage search pipeline
    4. Returns scored candidates (same format as POST /search)
    Supported formats: PDF, DOCX, TXT
    Max file size: 10MB
    """
    # read file bytes
    content= await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size is {MAX_FILE_SIZE // (1024*1024)}MB.",
        )
    if len(content) < 10:
         raise HTTPException(
            status_code=400,
            detail="File is empty or too small.",
        )
    # extract text
    try:
        jd_text=extract_text_from_bytes(content,filename=file.filename or "")
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))

    if len(jd_text) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Extracted only {len(jd_text)} characters. JD must be at least 50 characters.",
        )

    logger.info(
        "jd_file_ingested",
        filename=file.filename,
        file_size=len(content),
        extracted_chars=len(jd_text),
    )

    # buulding filters
    filters={}
    if location_country:
        filters["location_country"] = location_country
    if min_years:
        filters["min_years"] = min_years

    # running search pipeline
    redis=request.app.state.redis

    async with async_session_factory() as db:
        result = await execute_search(
            jd_text=jd_text,
            redis=redis,
            db=db,
            filters=filters or None,
            top_k_scoring=top_k,
        )

    # ── Transform to response ────────────────────────────────────
    candidate_responses = []
    for c in result.candidates:
        location_parts = [c.location_city, c.location_country]
        location = ", ".join(p for p in location_parts if p)
        candidate_responses.append(CandidateResponse(
            candidate_id=c.candidate_postgres_id,
            match_score=c.match_score,
            justifications=[c.justification_1, c.justification_2, c.justification_3],
            matched_section=c.section_type,
            skills=c.skills_str,
            location=location or "Unknown",
            years_of_experience=c.years_of_experience,
            education_level=c.education_level or "Unknown",
        ))
    return SearchResponse(
        search_event_id=result.search_event_id,
        candidates=candidate_responses,
        total_candidates_searched=result.total_candidates_searched,
        latency=LatencyBreakdown(
            stage1_ms=result.latency_stage1_ms,
            stage2_ms=result.latency_stage2_ms,
            total_ms=result.total_latency_ms,
            embedding_cached=result.embedding_cache_hit,
        ),
    )