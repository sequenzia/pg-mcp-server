# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

pg-mcp-server is a Model Context Protocol (MCP) server that enables LLMs to interact with PostgreSQL databases through a layered tool architecture for progressive schema discovery and query execution.

## Technology Stack

- **Python 3.11+** with **UV** package manager
- **Pydantic v2** for data validation and **pydantic-settings** for configuration
- **SQLAlchemy 2.0+** with **asyncpg** for async PostgreSQL access
- **mcp** (official Python SDK) for MCP server implementation

## Build & Development Commands

```bash
# Install dependencies
uv sync

# Run the server (STDIO transport - default)
uv run pg-mcp-server

# Run with custom .env file
uv run pg-mcp-server --env-file /path/to/.env

# Run with HTTP transport
MCP_TRANSPORT=http uv run pg-mcp-server

# Test database connection
uv run pg-mcp-server test

# Run tests
uv run pytest

# Run single test file
uv run pytest tests/test_schema_tools.py

# Run single test
uv run pytest tests/test_schema_tools.py::test_list_schemas

# Type checking
uv run mypy src/pg_mcp_server

# Linting
uv run ruff check src tests

# Format code
uv run ruff format src tests
```

## Architecture

### Three-Layer Tool Architecture

The server implements progressive database understanding through three tool layers:

1. **Layer 1 - Schema Discovery**: `list_schemas`, `list_tables`, `describe_table`, `get_sample_rows`
2. **Layer 2 - Relationship Discovery**: `get_foreign_keys`, `find_join_path`
3. **Layer 3 - Query Execution**: `execute_query`, `explain_query`

### Project Structure

```
src/pg_mcp_server/
├── __main__.py         # Entry point
├── server.py           # MCP server initialization
├── config.py           # Pydantic settings (PG_*, MCP_* env vars)
├── database/
│   ├── engine.py       # SQLAlchemy async engine/pool
│   ├── schema.py       # Schema discovery queries
│   ├── relationships.py # FK/relationship queries
│   └── queries.py      # Query execution
├── tools/
│   ├── schema_tools.py     # Layer 1 tools
│   ├── relationship_tools.py # Layer 2 tools
│   └── query_tools.py      # Layer 3 tools
└── models/
    ├── schema.py       # Pydantic models for schema objects
    ├── relationships.py # Pydantic models for relationships
    └── results.py      # Pydantic models for query results
```

### Configuration

**CLI Options:**
- `--env-file PATH` - Specify a custom `.env` file path
- If not specified, auto-loads `.env` from the current working directory (if it exists)
- Falls back to environment variables if no `.env` file is found

**Environment variables use prefixes:**
- `PG_*` for database settings (host, port, database, user, password, pool_size, statement_timeout, default_schema)
- `MCP_*` for server settings (transport, host, port, log_level, log_format)

**CLI Commands:**
- `pg-mcp-server` - Start the MCP server
- `pg-mcp-server test` - Test database connection and exit

## Key Implementation Requirements

### Security (Critical)

- **Read-only queries only**: Block INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE, SET, VACUUM, COPY, transaction statements
- **Parameterized queries**: All user values must use $1, $2 parameters, never string interpolation
- **SecretStr for credentials**: Database passwords must use Pydantic's SecretStr

### Tool Annotations

All tools must include MCP annotations:
- `readOnlyHint`: true (for all tools)
- `destructiveHint`: false
- `idempotentHint`: true (false for get_sample_rows with randomize=true)
- `openWorldHint`: false

### Error Handling

Use structured error codes: `SCHEMA_NOT_FOUND`, `TABLE_NOT_FOUND`, `COLUMN_NOT_FOUND`, `INVALID_SQL`, `WRITE_OPERATION_DENIED`, `QUERY_TIMEOUT`, `CONNECTION_ERROR`, `PERMISSION_DENIED`, `PARAMETER_ERROR`, `PATH_NOT_FOUND`

Include actionable suggestions in error responses (e.g., "Did you mean 'orders'? Use list_tables to see available tables.")

## Transport Support

- **STDIO**: For Claude Desktop, CLI tools, IDE integrations
- **Streamable HTTP**: For remote/hosted deployments (stateless JSON, not SSE)
