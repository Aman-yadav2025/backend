import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add the parent directory to sys.path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.config import settings

async def main():
    print(f"Connecting to {settings.DATABASE_URL.replace(settings.DATABASE_URL.split('@')[0], '***')}")
    engine = create_async_engine(settings.DATABASE_URL)
    
    with open(os.path.join(os.path.dirname(__file__), "..", "migrations", "007_companies_owner_id_partial_index.sql")) as f:
        sql = f.read()

    async with engine.begin() as conn:
        print("Applying migration...")
        await conn.execute(text(sql))
        print("Migration applied successfully!")
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
