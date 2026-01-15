# PostgreSQL MCP Server

A Model Context Protocol (MCP) server that enables LLMs to interact with PostgreSQL databases through a layered tool architecture for progressive schema discovery and query execution.

## Features

### Three-Layer Tool Architecture

**Layer 1 - Schema Discovery:**
- `list_schemas` - Enumerate all database schemas with metadata
- `list_tables` - List tables and views with row counts and sizes
- `describe_table` - Get detailed table structure (columns, indexes, constraints)
- `get_sample_rows` - Retrieve sample data to understand patterns

**Layer 2 - Relationship Discovery:**
- `get_foreign_keys` - Get incoming and outgoing foreign key relationships
- `find_join_path` - Discover join paths between tables via FK relationships

**Layer 3 - Query Execution:**
- `execute_query` - Execute read-only SQL queries with parameterized values
- `explain_query` - Get query execution plans for performance analysis

### Security Features

- **Read-only by design**: Only SELECT queries are allowed
- **Parameterized queries**: All user values use $1, $2 placeholders
- **Blocked operations**: INSERT, UPDATE, DELETE, DROP, and other write operations are blocked
- **Query timeout**: Configurable statement timeout prevents runaway queries

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pg-mcp-server.git
cd pg-mcp-server

# Install dependencies with UV
uv sync

# Install with dev dependencies
uv sync --all-extras
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Database Settings (`PG_*` prefix):**
| Variable | Description | Default |
|----------|-------------|---------|
| `PG_HOST` | PostgreSQL host | `localhost` |
| `PG_PORT` | PostgreSQL port | `5432` |
| `PG_DATABASE` | Database name | (required) |
| `PG_USER` | Database user | (required) |
| `PG_PASSWORD` | Database password | (required) |
| `PG_POOL_SIZE` | Connection pool size | `5` |
| `PG_STATEMENT_TIMEOUT` | Query timeout (ms) | `30000` |
| `PG_DEFAULT_SCHEMA` | Default schema | `public` |

**Server Settings (`MCP_*` prefix):**
| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_TRANSPORT` | Transport type (`stdio` or `http`) | `stdio` |
| `MCP_HOST` | HTTP server host | `0.0.0.0` |
| `MCP_PORT` | HTTP server port | `8080` |
| `MCP_LOG_LEVEL` | Logging level | `INFO` |
| `MCP_LOG_FORMAT` | Log format (`json` or `text`) | `json` |

## Usage

### STDIO Transport (for Claude Desktop)

```bash
uv run pg-mcp-server
```

### HTTP Transport (for remote deployments)

```bash
MCP_TRANSPORT=http MCP_PORT=8080 uv run pg-mcp-server
```

## Claude Desktop Integration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/pg-mcp-server", "pg-mcp-server"],
      "env": {
        "PG_HOST": "localhost",
        "PG_DATABASE": "myapp",
        "PG_USER": "readonly_user",
        "PG_PASSWORD": "your_password"
      }
    }
  }
}
```

## Tool Examples

### List Schemas
```
list_schemas()
-> {"schemas": [{"name": "public", "table_count": 15}], "total_count": 1}
```

### List Tables
```
list_tables(schema_name="public")
-> {"tables": [{"name": "users", "estimated_row_count": 10000, ...}], "total_count": 15}
```

### Describe Table
```
describe_table(table_name="users")
-> {"columns": [{"name": "id", "data_type": "int4", "is_primary_key": true}, ...]}
```

### Get Sample Rows
```
get_sample_rows(table_name="users", limit=5)
-> {"rows": [{"id": 1, "email": "user@example.com"}, ...], "row_count": 5}
```

### Get Foreign Keys
```
get_foreign_keys(table_name="orders")
-> {"outgoing": [{"to_table": "users", ...}], "incoming": [{"from_table": "order_items", ...}]}
```

### Find Join Path
```
find_join_path(from_table="order_items", to_table="users")
-> {"paths": [{"sql_example": "FROM order_items JOIN orders ON ... JOIN users ON ...", ...}]}
```

### Execute Query
```
execute_query(sql="SELECT * FROM users WHERE status = $1", params=["active"], limit=100)
-> {"rows": [...], "row_count": 42, "execution_time_ms": 12.5}
```

### Explain Query
```
explain_query(sql="SELECT * FROM orders WHERE status = 'pending'")
-> {"plan": "Seq Scan on orders (cost=0.00..100.00 rows=1000 width=48)\n  Filter: ..."}
```

## Development

### Run Tests
```bash
uv run pytest
```

### Run Tests with Coverage
```bash
uv run pytest --cov=pg_mcp_server
```

### Type Checking
```bash
uv run mypy src/pg_mcp_server
```

### Linting
```bash
uv run ruff check src tests
```

### Format Code
```bash
uv run ruff format src tests
```

## Project Structure

```
src/pg_mcp_server/
├── __init__.py         # Package version
├── __main__.py         # Entry point
├── server.py           # FastMCP server with lifespan
├── config.py           # Pydantic settings
├── errors.py           # Error handling
├── database/
│   ├── engine.py       # SQLAlchemy async engine
│   ├── schema.py       # Schema discovery queries
│   ├── relationships.py # FK discovery queries
│   └── queries.py      # Query execution
├── tools/
│   ├── schema_tools.py     # Layer 1 tools
│   ├── relationship_tools.py # Layer 2 tools
│   └── query_tools.py      # Layer 3 tools
└── models/
    ├── schema.py       # Schema Pydantic models
    ├── relationships.py # Relationship Pydantic models
    └── results.py      # Query result models
```

## Requirements

- Python 3.11+
- PostgreSQL 14+ (tested with 14, 15, 16)

## License

MIT License - see LICENSE file for details.
