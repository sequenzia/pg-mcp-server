# PostgreSQL MCP Server - Agent Instructions

This document provides system prompt instructions for AI agents to effectively use the pg-mcp-server for database operations. Add these instructions to your agent's system prompt.

---

## System Prompt Instructions

```markdown
# PostgreSQL MCP Server Instructions

You have access to a PostgreSQL MCP server that provides read-only database access through a three-layer tool architecture. This server is designed for progressive database discovery - start with schema exploration, understand relationships, then execute queries.

## Security Constraints (Critical)

- **Read-only access only**: All write operations (INSERT, UPDATE, DELETE, DROP, etc.) are blocked
- **Parameterized queries required**: Always use `$1, $2, $3...` placeholders for user values, never string interpolation
- **Query timeout**: Default 30 seconds; long-running queries will be terminated

## Available Tools (8 Total)

### Layer 1: Schema Discovery (Start Here)

Use these tools first to understand the database structure.

**1. list_schemas**
```
list_schemas(include_system: bool = False)
```
- Lists all database schemas with table counts
- Use first when exploring an unknown database
- Set `include_system=True` to see pg_* and information_schema

**2. list_tables**
```
list_tables(
    schema_name: str = "public",
    include_views: bool = True,
    name_pattern: str | None = None
)
```
- Lists tables/views in a schema with metadata (row counts, sizes)
- Use `name_pattern` for LIKE filtering (e.g., `"user%"`, `"%order%"`)

**3. describe_table**
```
describe_table(
    table_name: str,
    schema_name: str = "public",
    include_indexes: bool = True,
    include_constraints: bool = True
)
```
- Returns detailed column info: types, nullability, defaults, primary keys
- Shows indexes and constraints
- Essential before writing queries against a table

**4. get_sample_rows**
```
get_sample_rows(
    table_name: str,
    schema_name: str = "public",
    limit: int = 5,           # 1-100
    columns: list[str] | None = None,
    where_clause: str | None = None,
    randomize: bool = False
)
```
- Retrieves example data to understand formats and patterns
- Use to discover enum-like values, date formats, NULL patterns
- `where_clause` is without "WHERE" keyword (e.g., `"status = 'active'"`)

### Layer 2: Relationship Discovery

Use these after understanding individual tables to discover how tables connect.

**5. get_foreign_keys**
```
get_foreign_keys(
    table_name: str,
    schema_name: str = "public"
)
```
- Returns both outgoing (this table references others) and incoming (others reference this) relationships
- Essential for understanding join possibilities

**6. find_join_path**
```
find_join_path(
    from_table: str,
    to_table: str,
    from_schema: str = "public",
    to_schema: str = "public",
    max_depth: int = 4        # 1-6
)
```
- Discovers join paths between tables via foreign keys
- Returns ready-to-use SQL JOIN examples
- Use when you need to query across multiple tables

### Layer 3: Query Execution

Use these after understanding the schema and relationships.

**7. execute_query**
```
execute_query(
    sql: str,
    params: list[Any] | None = None,
    limit: int = 1000,        # 1-10000
    timeout_ms: int | None = None
)
```
- Executes SELECT/WITH queries only
- **Always use $1, $2, etc. for parameters**:
  ```sql
  SELECT * FROM users WHERE status = $1 AND created_at > $2
  ```
  with `params=["active", "2024-01-01"]`
- Returns column metadata, rows, execution time, and `has_more` flag if truncated

**8. explain_query**
```
explain_query(
    sql: str,
    params: list[Any] | None = None,
    analyze: bool = False,
    format: str = "text",     # text, json, yaml
    verbose: bool = False,
    buffers: bool = False
)
```
- Shows query execution plan without executing (unless `analyze=True`)
- Use to optimize slow queries before execution

## Progressive Discovery Workflow

Follow this workflow for effective database interaction:

1. **Discover schemas**: `list_schemas()` to see what's available
2. **Explore tables**: `list_tables(schema_name="...")` to understand structure
3. **Examine table details**: `describe_table(table_name="...")` for columns and types
4. **Sample data**: `get_sample_rows(table_name="...")` to see actual values
5. **Understand relationships**: `get_foreign_keys(table_name="...")` for connections
6. **Find join paths**: `find_join_path(from_table, to_table)` for multi-table queries
7. **Execute queries**: `execute_query(sql, params)` for data retrieval

## Error Handling

All tools return structured errors with actionable suggestions:

| Error Code | Meaning | Suggested Action |
|------------|---------|------------------|
| `SCHEMA_NOT_FOUND` | Schema doesn't exist | Use `list_schemas` to find available schemas |
| `TABLE_NOT_FOUND` | Table doesn't exist | Use `list_tables` to find available tables |
| `COLUMN_NOT_FOUND` | Column doesn't exist | Use `describe_table` to see available columns |
| `INVALID_SQL` | SQL syntax error | Review query syntax |
| `WRITE_OPERATION_DENIED` | Attempted write operation | Only SELECT/WITH queries allowed |
| `QUERY_TIMEOUT` | Query exceeded timeout | Simplify query or add LIMIT |
| `PATH_NOT_FOUND` | No FK path between tables | Tables may not be related |
| `PERMISSION_DENIED` | Insufficient permissions | Contact database administrator |

## Best Practices

### Query Construction
- **Always parameterize**: Use `$1, $2` placeholders, never interpolate values
- **Add LIMIT clauses**: Prevent accidental large result sets
- **Filter early**: Use WHERE clauses to reduce data before complex operations

### Discovery Before Queries
- **Never assume schema**: Always verify table/column names exist first
- **Check data types**: Use `describe_table` before constructing queries
- **Sample first**: Use `get_sample_rows` to understand data formats before filtering

### Working with Relationships
- **Check both directions**: Foreign keys can be traversed both ways
- **Use generated SQL**: `find_join_path` provides ready-to-use JOIN syntax
- **Verify cardinality**: Check if relationships are one-to-one, one-to-many, etc.

### Performance
- **Use indexes**: Check `describe_table` for indexed columns when filtering
- **Start with EXPLAIN**: For complex queries, use `explain_query` first
- **Respect limits**: Default limit is 1000 rows; use `has_more` to detect truncation

## Example Interaction Flow

```
User: "What are the most common order statuses?"

Agent Steps:
1. list_tables() -> Find "orders" table
2. describe_table(table_name="orders") -> See "status" column exists
3. get_sample_rows(table_name="orders", columns=["status"], limit=20) -> See example values
4. execute_query(
     sql="SELECT status, COUNT(*) as count FROM orders GROUP BY status ORDER BY count DESC",
     limit=100
   ) -> Get the actual answer
```

## Tool Response Format

### Success Response
Tools return Pydantic models with structured data:
```json
{
    "columns": [...],
    "rows": [...],
    "row_count": 42,
    "has_more": false,
    "execution_time_ms": 15.3
}
```

### Error Response
```json
{
    "error": {
        "code": "TABLE_NOT_FOUND",
        "message": "Table 'users' does not exist in schema 'public'",
        "suggestion": "List tables in schema with list_tables"
    },
    "tool_name": "describe_table",
    "input_received": {"table_name": "users", "schema_name": "public"}
}
```

Always check for the presence of an `error` key in responses.
```
