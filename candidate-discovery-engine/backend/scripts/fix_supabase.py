"""Drop email unique constraint and truncate candidates table in Supabase."""
import asyncio
import sys
sys.path.insert(0, ".")

from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def fix():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        # Drop email unique constraint
        await conn.execute(text("ALTER TABLE candidates DROP CONSTRAINT IF EXISTS candidates_email_key"))
        print("Dropped email UNIQUE constraint")

        # Truncate candidates
        await conn.execute(text("TRUNCATE TABLE candidates CASCADE"))
        print("Truncated candidates table")

        # Verify
        result = await conn.execute(text("SELECT COUNT(*) FROM candidates"))
        print(f"Candidates count: {result.scalar()}")

    await engine.dispose()
    print("DONE — ready for re-seed!")


asyncio.run(fix())
