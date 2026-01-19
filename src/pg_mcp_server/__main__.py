"""Entry point for the PostgreSQL MCP Server."""

import logging
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from pg_mcp_server.config import get_settings, set_env_file_path
from pg_mcp_server.server import mcp

# Import tools to register them with the server
from pg_mcp_server.tools import query_tools, relationship_tools, schema_tools  # noqa: F401

app = typer.Typer(
    name="pg-mcp-server",
    help="PostgreSQL MCP Server for database access via Model Context Protocol",
    no_args_is_help=False,
)


def validate_env_file(ctx: typer.Context, value: str | None) -> str | None:
    """Validate that the specified env file exists.

    Args:
        ctx: Typer context for handling shell completion.
        value: Path to env file, or None if not specified.

    Returns:
        Resolved absolute path to the env file, or None if not specified.

    Raises:
        typer.BadParameter: If the file doesn't exist or is not a file.
    """
    # Skip validation during shell completion
    if ctx.resilient_parsing:
        return None

    if value is None:
        return None

    env_path = Path(value)
    if not env_path.exists():
        raise typer.BadParameter(f"Environment file not found: {value}")
    if not env_path.is_file():
        raise typer.BadParameter(f"Path is not a file: {value}")
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


@app.command()
def main(
    env_file: Annotated[
        str | None,
        typer.Option(
            "--env-file",
            help="Path to .env file (default: .env in current directory)",
            callback=validate_env_file,
            metavar="PATH",
        ),
    ] = None,
) -> None:
    """Start the PostgreSQL MCP Server."""
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
    app()
