"""Quick test: can we connect to Supabase?"""
import asyncio
import sys
sys.path.insert(0, ".")

from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def test():
    print(f"Connecting to: {settings.DATABASE_URL[:80]}...")
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version()"))
            print(f"CONNECTED: {result.scalar()[:80]}")
            result2 = await conn.execute(text("SELECT current_database()"))
            print(f"Database: {result2.scalar()}")
        print("SUCCESS!")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
    finally:
        await engine.dispose()


asyncio.run(test())
