"""Reset vector_id for all candidates so the embedding pipeline re-processes them."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings


async def reset():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        result = await conn.execute(text("UPDATE candidates SET vector_id = NULL"))
        print(f"✅ Reset {result.rowcount} candidates (vector_id → NULL)")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reset())
