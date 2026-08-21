from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# NOTE: this connection should use a privileged Postgres role (or Supabase's
# service-role connection), NOT the anon/authenticated roles. Authorization
# is enforced at the API layer (see app/security.py); Postgres RLS remains
# enabled on every table as defense-in-depth against any other client that
# talks to the DB directly (e.g. PostgREST/Supabase client SDK).
engine = create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True, future=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
