"""Entry point for the PostgreSQL MCP Server."""

import argparse
import logging
import os
import sys
from pathlib import Path

from pg_mcp_server.config import get_settings, set_env_file_path
from pg_mcp_server.server import mcp

# Import tools to register them with the server
from pg_mcp_server.tools import query_tools, relationship_tools, schema_tools  # noqa: F401


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="pg-mcp-server",
        description="PostgreSQL MCP Server for database access via Model Context Protocol",
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to .env file (default: .env in current directory)",
    )
    return parser.parse_args()


def validate_env_file(path: str | None) -> str | None:
    """Validate that the specified env file exists.

    Args:
        path: Path to env file, or None if not specified.

    Returns:
        Resolved absolute path to the env file, or None if not specified.

    Exits:
        With code 1 if the file doesn't exist or is not a file.
    """
    if path is None:
        return None
    env_path = Path(path)
    if not env_path.exists():
        print(f"Error: Environment file not found: {path}", file=sys.stderr)
        sys.exit(1)
    if not env_path.is_file():
        print(f"Error: Path is not a file: {path}", file=sys.stderr)
        sys.exit(1)
    return str(env_path.resolve())


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
    args = parse_args()
    env_file = validate_env_file(args.env_file)
    set_env_file_path(env_file)

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
