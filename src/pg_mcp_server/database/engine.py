"""SQLAlchemy async engine management for PostgreSQL."""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from pg_mcp_server.config import DatabaseSettings


async def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    """Create async SQLAlchemy engine with connection pool.

    Args:
        settings: Database configuration settings.

    Returns:
        AsyncEngine configured for asyncpg with connection pooling.
    """
    engine = create_async_engine(
        settings.async_url,
        pool_size=settings.pool_size,
        pool_timeout=settings.pool_timeout,
        pool_pre_ping=True,  # Health check connections before use
        echo=False,
    )
    return engine


async def dispose_engine(engine: AsyncEngine) -> None:
    """Dispose of the engine and close all connections.

    Args:
        engine: The async engine to dispose.
    """
    await engine.dispose()
