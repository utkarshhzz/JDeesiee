"""Quick test to see why inserts are failing."""
import asyncio
import sys
import uuid
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.services.extractor import extract_text_from_file


async def test():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    # Test 1: simple insert
    insert_sql = text("""
        INSERT INTO candidates (
            id, external_id, full_name, email, phone,
            location_city, location_country, years_of_experience,
            current_title, current_company, education_level,
            skills, resume_text, resume_blob_url, vector_id, is_active
        ) VALUES (
            :id, :external_id, :full_name, :email, :phone,
            :location_city, :location_country, :years_of_experience,
            :current_title, :current_company, :education_level,
            CAST(:skills AS jsonb), :resume_text, :resume_blob_url, :vector_id, :is_active
        )
        ON CONFLICT (external_id) DO NOTHING
    """)

    params = {
        "id": uuid.uuid4(),
        "external_id": "test-debug-001",
        "full_name": "Test User",
        "email": "testdebug@example.com",
        "phone": "+1234567890",
        "location_city": "Mumbai",
        "location_country": "India",
        "years_of_experience": 5,
        "current_title": "Software Engineer",
        "current_company": None,
        "education_level": "Bachelors",
        "skills": json.dumps(["Python", "AWS"]),
        "resume_text": "This is a test resume.",
        "resume_blob_url": None,
        "vector_id": None,
        "is_active": True,
    }

    try:
        async with engine.begin() as conn:
            await conn.execute(insert_sql, params)
        print("TEST 1 (simple insert): SUCCESS")
    except Exception as e:
        print(f"TEST 1 FAILED: {type(e).__name__}: {e}")

    # Test 2: real resume
    try:
        resume_path = next(Path(r"F:\JDEesiee\Resumes\Telegram_scrape").glob("*.pdf"))
        resume_text = extract_text_from_file(resume_path)
        params2 = {
            "id": uuid.uuid4(),
            "external_id": "test-debug-002",
            "full_name": "Real Resume Test",
            "email": None,  # Many resumes may not have parseable email
            "phone": None,
            "location_city": None,
            "location_country": None,
            "years_of_experience": None,
            "current_title": None,
            "current_company": None,
            "education_level": None,
            "skills": json.dumps(["Python"]),
            "resume_text": resume_text,
            "resume_blob_url": None,
            "vector_id": None,
            "is_active": True,
        }

        async with engine.begin() as conn:
            await conn.execute(insert_sql, params2)
        print("TEST 2 (real resume): SUCCESS")
    except Exception as e:
        print(f"TEST 2 FAILED: {type(e).__name__}: {e}")

    # Cleanup
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM candidates WHERE external_id LIKE 'test-debug-%'"))
        print("CLEANUP: done")
    except Exception as e:
        print(f"CLEANUP FAILED: {e}")

    # Count
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM candidates"))
        print(f"Total candidates in DB: {result.scalar()}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test())
