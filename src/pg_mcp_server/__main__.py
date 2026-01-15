"""Entry point for the PostgreSQL MCP Server."""

import logging
import os
import sys

from pg_mcp_server.config import get_settings
from pg_mcp_server.server import mcp

# Import tools to register them with the server
from pg_mcp_server.tools import query_tools, relationship_tools, schema_tools  # noqa: F401


def setup_logging(level: str, format_type: str) -> None:
    """Configure logging based on settings.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR).
        format_type: Log format type ('json' or 'text').
    """
    if format_type == "json":
        log_format = (
            '{"time": "%(asctime)s", "name": "%(name)s", '
            '"level": "%(levelname)s", "message": "%(message)s"}'
        )
    else:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level.upper(),
        format=log_format,
        stream=sys.stderr,  # MCP stdio uses stdout, so log to stderr
    )


def main() -> None:
    """Main entry point for the MCP server."""
    settings = get_settings()

    setup_logging(settings.server.log_level, settings.server.log_format)

    logger = logging.getLogger(__name__)
    logger.info(f"Starting PostgreSQL MCP Server with {settings.server.transport} transport")

    # Run with appropriate transport
    if settings.server.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        # Set host/port via environment variables for uvicorn
        os.environ.setdefault("UVICORN_HOST", settings.server.host)
        os.environ.setdefault("UVICORN_PORT", str(settings.server.port))
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
