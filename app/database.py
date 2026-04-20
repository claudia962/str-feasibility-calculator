"""
Async SQLAlchemy engine and session factory.
SQLite (aiosqlite) for serverless/dev, PostgreSQL (asyncpg) for production.
Auto-creates tables on first request if SQLite.
"""
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()
_db_url = settings.get_database_url()

_connect_args = {}
if _db_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    _db_url,
    pool_pre_ping=True,
    echo=settings.debug,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False,
)


class Base(DeclarativeBase):
    pass


_db_initialized = False


async def _ensure_tables() -> None:
    """Create tables if not yet initialized (idempotent)."""
    global _db_initialized
    if _db_initialized:
        return
    from app.models import database_models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    _db_initialized = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await _ensure_tables()
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Explicit table creation (for startup hooks)."""
    await _ensure_tables()


async def close_db() -> None:
    await engine.dispose()
