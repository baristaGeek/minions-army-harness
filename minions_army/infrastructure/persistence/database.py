"""Database configuration and connection."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from minions_army.core.config.loader import config as settings

engine = None
AsyncSessionLocal = None


def _get_engine():
    """Create the async engine only when the database is actually needed."""
    global engine

    if engine is None:
        engine = create_async_engine(
            settings.database.async_url,
            echo=settings.app.debug,
            future=True,
        )

    return engine


def _get_sessionmaker():
    """Create the session factory lazily so imports do not require a valid DB driver."""
    global AsyncSessionLocal

    if AsyncSessionLocal is None:
        AsyncSessionLocal = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Get database session."""
    async with _get_sessionmaker()() as session:
        yield session
