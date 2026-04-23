from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db_engine() -> None:
    global _engine, async_session_factory
    if _engine is not None:
        return
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
    )
    async_session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


async def shutdown_db_engine() -> None:
    global _engine, async_session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    async_session_factory = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("Database not initialized")
    async with async_session_factory() as session:
        yield session
