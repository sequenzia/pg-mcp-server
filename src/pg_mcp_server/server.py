"""MCP server initialization using FastMCP.

This module creates the FastMCP server instance with lifespan management
for database connection pooling.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncEngine

from pg_mcp_server.config import Settings, get_settings
from pg_mcp_server.database.engine import create_engine, dispose_engine


@dataclass
class AppContext:
    """Application context with shared resources."""

    engine: AsyncEngine
    settings: Settings


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle - database connection pool.

    Args:
        server: The FastMCP server instance.

    Yields:
        AppContext with initialized resources.
    """
    settings = get_settings()

    # Initialize database engine on startup
    engine = await create_engine(settings.database)

    try:
        yield AppContext(engine=engine, settings=settings)
    finally:
        # Cleanup on shutdown
        await dispose_engine(engine)


# Create MCP server with lifespan
mcp = FastMCP(
    "PostgreSQL MCP Server",
    lifespan=app_lifespan,
)
