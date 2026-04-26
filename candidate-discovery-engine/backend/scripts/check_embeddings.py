"""Quick check: how many candidates have been embedded."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings

async def check():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        r1 = await conn.execute(text("SELECT COUNT(*) FROM candidates WHERE vector_id IS NOT NULL"))
        done = r1.scalar()
        r2 = await conn.execute(text("SELECT COUNT(*) FROM candidates"))
        total = r2.scalar()
    await engine.dispose()
    print(f"Embedded: {done}/{total}")

if __name__ == "__main__":
    asyncio.run(check())
