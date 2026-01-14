# Product Requirements Document: PostgreSQL MCP Server

**Version:** 1.0  
**Status:** Draft  
**Author:** Sequenzia  
**Date:** January 14, 2026

---

## 1. Executive Summary

This document defines the requirements for a Model Context Protocol (MCP) server that enables Large Language Models (LLMs) to interact with PostgreSQL databases. The server implements a layered tool architecture designed to help LLMs progressively understand database schemas before constructing and executing queries.

The MVP focuses exclusively on MCP tools, providing schema discovery, relationship exploration, and query execution capabilities through both STDIO and Streamable HTTP transports.

---

## 2. Problem Statement

LLMs interacting with databases face several challenges:

1. **Schema Blindness**: Without understanding the database structure, LLMs cannot construct valid queries
2. **Relationship Complexity**: Foreign key relationships and join paths are not self-evident
3. **Data Pattern Ignorance**: Column names alone do not reveal the actual data patterns (e.g., enum values, formats)
4. **Query Construction Errors**: Lacking context leads to syntactically valid but semantically incorrect queries

Current solutions often provide a single "execute SQL" tool, forcing the LLM to guess at schema details or repeatedly ask the user for clarification.

---

## 3. Goals and Non-Goals

### 3.1 Goals

- Enable LLMs to autonomously discover and understand PostgreSQL database schemas
- Provide a structured workflow for progressive schema exploration
- Support secure, parameterized query execution
- Offer both local (STDIO) and remote (Streamable HTTP) deployment options
- Maintain a clean, well-documented codebase following Python best practices

### 3.2 Non-Goals (MVP)

- MCP Resources (schema as resources, query results as resources)
- MCP Prompts (workflow prompts, query templates)
- Write operations (INSERT, UPDATE, DELETE) beyond read-only queries
- Multi-database connection management within a single server instance
- Query result caching or optimization
- Authentication/authorization beyond database connection credentials
- GraphQL or REST API interfaces

---

## 4. Technical Requirements

### 4.1 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Required per specification |
| Package Manager | UV | Required per specification; fast, reliable dependency resolution |
| Data Validation | Pydantic v2 | Required per specification; runtime validation, serialization |
| Configuration | pydantic-settings | Required per specification; environment variable management |
| Database ORM | SQLAlchemy 2.0+ | Required per specification; async support, type hints |
| MCP Framework | mcp (official Python SDK) | Official SDK with FastMCP patterns |
| Async Runtime | asyncio + asyncpg | High-performance async PostgreSQL driver |

### 4.2 Transport Support

The server MUST support both transport mechanisms:

**STDIO Transport**
- For local execution via Claude Desktop, CLI tools, or IDE integrations
- Single connection per server instance
- Configuration via environment variables or command-line arguments

**Streamable HTTP Transport**
- For remote/hosted deployments
- Stateless JSON request/response pattern (not SSE streaming)
- Suitable for serverless or containerized environments
- Configuration via environment variables

### 4.3 Configuration Schema

Configuration MUST be managed via pydantic-settings with the following structure:

```python
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="PG_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: SecretStr = Field(..., description="Database password")
    
    # Connection pool settings
    pool_size: int = Field(default=5, ge=1, le=20, description="Connection pool size")
    pool_timeout: float = Field(default=30.0, gt=0, description="Pool connection timeout in seconds")
    
    # Query settings
    statement_timeout: int = Field(default=30000, ge=1000, description="Statement timeout in milliseconds")
    default_schema: str = Field(default="public", description="Default schema for operations")


class ServerSettings(BaseSettings):
    """MCP server configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    transport: str = Field(default="stdio", pattern="^(stdio|http)$", description="Transport type")
    host: str = Field(default="0.0.0.0", description="HTTP server host")
    port: int = Field(default=8080, ge=1, le=65535, description="HTTP server port")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", pattern="^(json|text)$", description="Log output format")


class Settings(BaseSettings):
    """Root settings combining all configuration."""
    
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
```

Environment variables example:
```bash
# Database
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=myapp
PG_USER=readonly_user
PG_PASSWORD=secure_password
PG_POOL_SIZE=5
PG_STATEMENT_TIMEOUT=30000
PG_DEFAULT_SCHEMA=public

# Server
MCP_TRANSPORT=stdio
MCP_LOG_LEVEL=INFO
```

---

## 5. Architecture

### 5.1 Layered Tool Architecture

The server implements a three-layer tool architecture designed to guide LLMs through progressive database understanding:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Layer 3: Query Execution                      │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  execute_query   │  │  explain_query   │                     │
│  └──────────────────┘  └──────────────────┘                     │
├─────────────────────────────────────────────────────────────────┤
│                 Layer 2: Relationship Discovery                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ get_foreign_keys │  │  find_join_path  │                     │
│  └──────────────────┘  └──────────────────┘                     │
├─────────────────────────────────────────────────────────────────┤
│                   Layer 1: Schema Discovery                      │
│  ┌──────────────┐ ┌───────────────┐ ┌──────────────────┐        │
│  │ list_schemas │ │  list_tables  │ │  describe_table  │        │
│  └──────────────┘ └───────────────┘ └──────────────────┘        │
│  ┌──────────────────┐                                           │
│  │  get_sample_rows │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MCP Server                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Tool Registry                         │    │
│  │  (Schema Discovery | Relationships | Query Execution)    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Database Service                       │    │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │    │
│  │  │   Schema    │  │ Relationship │  │     Query      │  │    │
│  │  │   Service   │  │   Service    │  │    Service     │  │    │
│  │  └─────────────┘  └──────────────┘  └────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SQLAlchemy Async Engine                     │    │
│  │                   (Connection Pool)                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     PostgreSQL      │
                    └─────────────────────┘
```

### 5.3 Project Structure

```
pg-mcp-server/
├── pyproject.toml              # UV/pip configuration
├── uv.lock                     # Locked dependencies
├── README.md                   # Project documentation
├── .env.example                # Example environment configuration
├── src/
│   └── pg_mcp_server/
│       ├── __init__.py
│       ├── __main__.py         # Entry point
│       ├── server.py           # MCP server initialization
│       ├── config.py           # Pydantic settings
│       ├── database/
│       │   ├── __init__.py
│       │   ├── engine.py       # SQLAlchemy engine management
│       │   ├── schema.py       # Schema discovery queries
│       │   ├── relationships.py # FK/relationship queries
│       │   └── queries.py      # Query execution
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── schema_tools.py     # Layer 1 tools
│       │   ├── relationship_tools.py # Layer 2 tools
│       │   └── query_tools.py      # Layer 3 tools
│       └── models/
│           ├── __init__.py
│           ├── schema.py       # Pydantic models for schema objects
│           ├── relationships.py # Pydantic models for relationships
│           └── results.py      # Pydantic models for query results
└── tests/
    ├── __init__.py
    ├── conftest.py             # Pytest fixtures
    ├── test_schema_tools.py
    ├── test_relationship_tools.py
    └── test_query_tools.py
```

---

## 6. Tool Specifications

### 6.1 Layer 1: Schema Discovery Tools

#### 6.1.1 list_schemas

**Purpose**: Enumerate all non-system schemas in the database.

**Input Schema**:
```python
class ListSchemasInput(BaseModel):
    """Input for list_schemas tool."""
    include_system: bool = Field(
        default=False,
        description="Include system schemas (pg_*, information_schema)"
    )
```

**Output Schema**:
```python
class SchemaInfo(BaseModel):
    """Information about a database schema."""
    name: str = Field(description="Schema name")
    owner: str = Field(description="Schema owner")
    description: str | None = Field(description="Schema comment/description")
    table_count: int = Field(description="Number of tables in schema")


class ListSchemasOutput(BaseModel):
    """Output for list_schemas tool."""
    schemas: list[SchemaInfo]
    total_count: int
```

**Tool Annotations**:
- `readOnlyHint`: true
- `destructiveHint`: false
- `idempotentHint`: true
- `openWorldHint`: false

**Example Output**:
```json
{
  "schemas": [
    {
      "name": "public",
      "owner": "postgres",
      "description": "Standard public schema",
      "table_count": 15
    },
    {
      "name": "analytics",
      "owner": "analytics_admin",
      "description": "Analytics and reporting tables",
      "table_count": 8
    }
  ],
  "total_count": 2
}
```

---

#### 6.1.2 list_tables

**Purpose**: List all tables within a schema with metadata.

**Input Schema**:
```python
class ListTablesInput(BaseModel):
    """Input for list_tables tool."""
    schema_name: str = Field(
        default="public",
        description="Schema to list tables from"
    )
    include_views: bool = Field(
        default=True,
        description="Include views in the listing"
    )
    name_pattern: str | None = Field(
        default=None,
        description="Optional LIKE pattern to filter table names (e.g., 'user%')"
    )
```

**Output Schema**:
```python
class TableInfo(BaseModel):
    """Information about a database table."""
    name: str = Field(description="Table name")
    schema_name: str = Field(description="Schema containing the table")
    type: str = Field(description="Object type: 'table' or 'view'")
    description: str | None = Field(description="Table comment/description")
    estimated_row_count: int = Field(description="Estimated row count from pg_stat")
    size_bytes: int | None = Field(description="Table size in bytes (null for views)")
    size_pretty: str | None = Field(description="Human-readable size (e.g., '1.2 MB')")
    has_primary_key: bool = Field(description="Whether table has a primary key")
    column_count: int = Field(description="Number of columns")


class ListTablesOutput(BaseModel):
    """Output for list_tables tool."""
    tables: list[TableInfo]
    schema_name: str
    total_count: int
```

**Tool Annotations**:
- `readOnlyHint`: true
- `destructiveHint`: false
- `idempotentHint`: true
- `openWorldHint`: false

**Example Output**:
```json
{
  "tables": [
    {
      "name": "users",
      "schema_name": "public",
      "type": "table",
      "description": "Application user accounts",
      "estimated_row_count": 125000,
      "size_bytes": 15728640,
      "size_pretty": "15 MB",
      "has_primary_key": true,
      "column_count": 12
    },
    {
      "name": "orders",
      "schema_name": "public",
      "type": "table",
      "description": "Customer orders",
      "estimated_row_count": 890000,
      "size_bytes": 104857600,
      "size_pretty": "100 MB",
      "has_primary_key": true,
      "column_count": 18
    }
  ],
  "schema_name": "public",
  "total_count": 2
}
```

---

#### 6.1.3 describe_table

**Purpose**: Get detailed structure of a specific table including columns, constraints, and indexes.

**Input Schema**:
```python
class DescribeTableInput(BaseModel):
    """Input for describe_table tool."""
    table_name: str = Field(description="Name of the table to describe")
    schema_name: str = Field(
        default="public",
        description="Schema containing the table"
    )
    include_indexes: bool = Field(
        default=True,
        description="Include index information"
    )
    include_constraints: bool = Field(
        default=True,
        description="Include constraint information"
    )
```

**Output Schema**:
```python
class ColumnInfo(BaseModel):
    """Detailed information about a table column."""
    name: str = Field(description="Column name")
    data_type: str = Field(description="PostgreSQL data type")
    is_nullable: bool = Field(description="Whether column allows NULL")
    default_value: str | None = Field(description="Default value expression")
    description: str | None = Field(description="Column comment")
    is_primary_key: bool = Field(description="Part of primary key")
    is_unique: bool = Field(description="Has unique constraint")
    foreign_key: ForeignKeyRef | None = Field(description="FK reference if applicable")
    character_maximum_length: int | None = Field(description="Max length for char types")
    numeric_precision: int | None = Field(description="Precision for numeric types")
    numeric_scale: int | None = Field(description="Scale for numeric types")


class ForeignKeyRef(BaseModel):
    """Foreign key reference information."""
    constraint_name: str
    referenced_schema: str
    referenced_table: str
    referenced_column: str
    on_update: str
    on_delete: str


class IndexInfo(BaseModel):
    """Information about a table index."""
    name: str = Field(description="Index name")
    columns: list[str] = Field(description="Indexed columns")
    is_unique: bool = Field(description="Whether index enforces uniqueness")
    is_primary: bool = Field(description="Whether this is the primary key index")
    index_type: str = Field(description="Index type (btree, hash, gin, etc.)")
    description: str | None = Field(description="Index comment")


class ConstraintInfo(BaseModel):
    """Information about a table constraint."""
    name: str = Field(description="Constraint name")
    type: str = Field(description="Constraint type (PRIMARY KEY, FOREIGN KEY, UNIQUE, CHECK)")
    columns: list[str] = Field(description="Columns involved")
    definition: str | None = Field(description="Constraint definition (for CHECK)")
    referenced_table: str | None = Field(description="Referenced table (for FK)")


class DescribeTableOutput(BaseModel):
    """Output for describe_table tool."""
    table_name: str
    schema_name: str
    type: str  # 'table' or 'view'
    description: str | None
    columns: list[ColumnInfo]
    indexes: list[IndexInfo] | None
    constraints: list[ConstraintInfo] | None
    estimated_row_count: int
    size_pretty: str | None
```

**Tool Annotations**:
- `readOnlyHint`: true
- `destructiveHint`: false
- `idempotentHint`: true
- `openWorldHint`: false

**Example Output**:
```json
{
  "table_name": "orders",
  "schema_name": "public",
  "type": "table",
  "description": "Customer orders with status tracking",
  "columns": [
    {
      "name": "id",
      "data_type": "uuid",
      "is_nullable": false,
      "default_value": "gen_random_uuid()",
      "description": "Unique order identifier",
      "is_primary_key": true,
      "is_unique": true,
      "foreign_key": null,
      "character_maximum_length": null,
      "numeric_precision": null,
      "numeric_scale": null
    },
    {
      "name": "user_id",
      "data_type": "uuid",
      "is_nullable": false,
      "default_value": null,
      "description": "Reference to the ordering user",
      "is_primary_key": false,
      "is_unique": false,
      "foreign_key": {
        "constraint_name": "orders_user_id_fkey",
        "referenced_schema": "public",
        "referenced_table": "users",
        "referenced_column": "id",
        "on_update": "CASCADE",
        "on_delete": "RESTRICT"
      },
      "character_maximum_length": null,
      "numeric_precision": null,
      "numeric_scale": null
    },
    {
      "name": "status",
      "data_type": "varchar(20)",
      "is_nullable": false,
      "default_value": "'pending'",
      "description": "Order status: pending, processing, shipped, delivered, cancelled",
      "is_primary_key": false,
      "is_unique": false,
      "foreign_key": null,
      "character_maximum_length": 20,
      "numeric_precision": null,
      "numeric_scale": null
    }
  ],
  "indexes": [
    {
      "name": "orders_pkey",
      "columns": ["id"],
      "is_unique": true,
      "is_primary": true,
      "index_type": "btree",
      "description": null
    },
    {
      "name": "orders_user_id_idx",
      "columns": ["user_id"],
      "is_unique": false,
      "is_primary": false,
      "index_type": "btree",
      "description": "Index for user order lookups"
    },
    {
      "name": "orders_status_created_idx",
      "columns": ["status", "created_at"],
      "is_unique": false,
      "is_primary": false,
      "index_type": "btree",
      "description": "Composite index for status queries"
    }
  ],
  "constraints": [
    {
      "name": "orders_pkey",
      "type": "PRIMARY KEY",
      "columns": ["id"],
      "definition": null,
      "referenced_table": null
    },
    {
      "name": "orders_user_id_fkey",
      "type": "FOREIGN KEY",
      "columns": ["user_id"],
      "definition": null,
      "referenced_table": "users"
    },
    {
      "name": "orders_status_check",
      "type": "CHECK",
      "columns": ["status"],
      "definition": "status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled')",
      "referenced_table": null
    }
  ],
  "estimated_row_count": 890000,
  "size_pretty": "100 MB"
}
```

---

#### 6.1.4 get_sample_rows

**Purpose**: Retrieve sample rows to understand actual data patterns.

**Input Schema**:
```python
class GetSampleRowsInput(BaseModel):
    """Input for get_sample_rows tool."""
    table_name: str = Field(description="Name of the table to sample")
    schema_name: str = Field(
        default="public",
        description="Schema containing the table"
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of sample rows to retrieve"
    )
    columns: list[str] | None = Field(
        default=None,
        description="Specific columns to include (null for all)"
    )
    where_clause: str | None = Field(
        default=None,
        description="Optional WHERE clause to filter samples (without 'WHERE' keyword)"
    )
    randomize: bool = Field(
        default=False,
        description="Randomize row selection (slower on large tables)"
    )
```

**Output Schema**:
```python
class GetSampleRowsOutput(BaseModel):
    """Output for get_sample_rows tool."""
    table_name: str
    schema_name: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    total_table_rows: int
    note: str | None = Field(
        description="Additional context about the sample (e.g., 'randomized', 'filtered')"
    )
```

**Tool Annotations**:
- `readOnlyHint`: true
- `destructiveHint`: false
- `idempotentHint`: false (if randomize=true)
- `openWorldHint`: false

**Example Output**:
```json
{
  "table_name": "orders",
  "schema_name": "public",
  "columns": ["id", "user_id", "status", "total_amount", "created_at"],
  "rows": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "status": "delivered",
      "total_amount": 129.99,
      "created_at": "2025-01-10T14:30:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "user_id": "123e4567-e89b-12d3-a456-426614174001",
      "status": "pending",
      "total_amount": 49.50,
      "created_at": "2025-01-14T09:15:00Z"
    }
  ],
  "row_count": 2,
  "total_table_rows": 890000,
  "note": "Showing first 2 rows ordered by primary key"
}
```

---

### 6.2 Layer 2: Relationship Discovery Tools

#### 6.2.1 get_foreign_keys

**Purpose**: Get all foreign key relationships for a table (both incoming and outgoing).

**Input Schema**:
```python
class GetForeignKeysInput(BaseModel):
    """Input for get_foreign_keys tool."""
    table_name: str = Field(description="Name of the table")
    schema_name: str = Field(
        default="public",
        description="Schema containing the table"
    )
```

**Output Schema**:
```python
class ForeignKeyRelation(BaseModel):
    """A single foreign key relationship."""
    constraint_name: str
    from_schema: str
    from_table: str
    from_columns: list[str]
    to_schema: str
    to_table: str
    to_columns: list[str]
    on_update: str
    on_delete: str


class GetForeignKeysOutput(BaseModel):
    """Output for get_foreign_keys tool."""
    table_name: str
    schema_name: str
    outgoing: list[ForeignKeyRelation] = Field(
        description="Tables this table references (this table has the FK column)"
    )
    incoming: list[ForeignKeyRelation] = Field(
        description="Tables that reference this table (other tables have FK to this)"
    )
    outgoing_count: int
    incoming_count: int
```

**Tool Annotations**:
- `readOnlyHint`: true
- `destructiveHint`: false
- `idempotentHint`: true
- `openWorldHint`: false

**Example Output**:
```json
{
  "table_name": "orders",
  "schema_name": "public",
  "outgoing": [
    {
      "constraint_name": "orders_user_id_fkey",
      "from_schema": "public",
      "from_table": "orders",
      "from_columns": ["user_id"],
      "to_schema": "public",
      "to_table": "users",
      "to_columns": ["id"],
      "on_update": "CASCADE",
      "on_delete": "RESTRICT"
    },
    {
      "constraint_name": "orders_shipping_address_id_fkey",
      "from_schema": "public",
      "from_table": "orders",
      "from_columns": ["shipping_address_id"],
      "to_schema": "public",
      "to_table": "addresses",
      "to_columns": ["id"],
      "on_update": "CASCADE",
      "on_delete": "SET NULL"
    }
  ],
  "incoming": [
    {
      "constraint_name": "order_items_order_id_fkey",
      "from_schema": "public",
      "from_table": "order_items",
      "from_columns": ["order_id"],
      "to_schema": "public",
      "to_table": "orders",
      "to_columns": ["id"],
      "on_update": "CASCADE",
      "on_delete": "CASCADE"
    },
    {
      "constraint_name": "payments_order_id_fkey",
      "from_schema": "public",
      "from_table": "payments",
      "from_columns": ["order_id"],
      "to_schema": "public",
      "to_table": "orders",
      "to_columns": ["id"],
      "on_update": "CASCADE",
      "on_delete": "RESTRICT"
    }
  ],
  "outgoing_count": 2,
  "incoming_count": 2
}
```

---

#### 6.2.2 find_join_path

**Purpose**: Find possible join paths between two tables via foreign key relationships.

**Input Schema**:
```python
class FindJoinPathInput(BaseModel):
    """Input for find_join_path tool."""
    from_table: str = Field(description="Starting table name")
    to_table: str = Field(description="Target table name")
    from_schema: str = Field(default="public", description="Schema of starting table")
    to_schema: str = Field(default="public", description="Schema of target table")
    max_depth: int = Field(
        default=4,
        ge=1,
        le=6,
        description="Maximum number of joins to traverse"
    )
```

**Output Schema**:
```python
class JoinStep(BaseModel):
    """A single step in a join path."""
    from_table: str
    from_schema: str
    from_column: str
    to_table: str
    to_schema: str
    to_column: str
    join_type: str = Field(description="Suggested join type based on FK direction")
    constraint_name: str


class JoinPath(BaseModel):
    """A complete path between two tables."""
    steps: list[JoinStep]
    depth: int
    sql_example: str = Field(description="Example JOIN clause for this path")


class FindJoinPathOutput(BaseModel):
    """Output for find_join_path tool."""
    from_table: str
    to_table: str
    paths: list[JoinPath]
    paths_found: int
    note: str | None = Field(
        description="Additional context (e.g., 'multiple paths found, showing shortest')"
    )
```

**Tool Annotations**:
- `readOnlyHint`: true
- `destructiveHint`: false
- `idempotentHint`: true
- `openWorldHint`: false

**Example Output**:
```json
{
  "from_table": "order_items",
  "to_table": "users",
  "paths": [
    {
      "steps": [
        {
          "from_table": "order_items",
          "from_schema": "public",
          "from_column": "order_id",
          "to_table": "orders",
          "to_schema": "public",
          "to_column": "id",
          "join_type": "INNER JOIN",
          "constraint_name": "order_items_order_id_fkey"
        },
        {
          "from_table": "orders",
          "from_schema": "public",
          "from_column": "user_id",
          "to_table": "users",
          "to_schema": "public",
          "to_column": "id",
          "join_type": "INNER JOIN",
          "constraint_name": "orders_user_id_fkey"
        }
      ],
      "depth": 2,
      "sql_example": "FROM order_items oi INNER JOIN orders o ON oi.order_id = o.id INNER JOIN users u ON o.user_id = u.id"
    }
  ],
  "paths_found": 1,
  "note": null
}
```

---

### 6.3 Layer 3: Query Execution Tools

#### 6.3.1 execute_query

**Purpose**: Execute a read-only SQL query with parameterized values.

**Input Schema**:
```python
class ExecuteQueryInput(BaseModel):
    """Input for execute_query tool."""
    sql: str = Field(
        description="SQL SELECT query to execute. Use $1, $2, etc. for parameters."
    )
    params: list[Any] | None = Field(
        default=None,
        description="Parameter values for the query (positional, matching $1, $2, etc.)"
    )
    limit: int | None = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum rows to return (applied if query lacks LIMIT)"
    )
    timeout_ms: int | None = Field(
        default=None,
        description="Query timeout in milliseconds (uses server default if not specified)"
    )
```

**Output Schema**:
```python
class QueryColumn(BaseModel):
    """Metadata about a result column."""
    name: str
    data_type: str


class ExecuteQueryOutput(BaseModel):
    """Output for execute_query tool."""
    columns: list[QueryColumn]
    rows: list[dict[str, Any]]
    row_count: int
    has_more: bool = Field(description="Whether results were truncated by limit")
    execution_time_ms: float
    query_hash: str = Field(description="Hash of executed query for reference")
```

**Tool Annotations**:
- `readOnlyHint`: true
- `destructiveHint`: false
- `idempotentHint`: true
- `openWorldHint`: false

**Security Requirements**:
1. Query MUST be validated as read-only (SELECT, WITH...SELECT only)
2. Statements containing INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE, GRANT, REVOKE MUST be rejected
3. Parameters MUST be used for all user-provided values
4. SET and other session-modifying statements MUST be rejected

**Example Output**:
```json
{
  "columns": [
    {"name": "user_name", "data_type": "varchar"},
    {"name": "order_count", "data_type": "bigint"},
    {"name": "total_spent", "data_type": "numeric"}
  ],
  "rows": [
    {"user_name": "alice", "order_count": 15, "total_spent": 1249.99},
    {"user_name": "bob", "order_count": 8, "total_spent": 567.50}
  ],
  "row_count": 2,
  "has_more": false,
  "execution_time_ms": 23.5,
  "query_hash": "a1b2c3d4"
}
```

---

#### 6.3.2 explain_query

**Purpose**: Get the query execution plan without executing the query.

**Input Schema**:
```python
class ExplainQueryInput(BaseModel):
    """Input for explain_query tool."""
    sql: str = Field(description="SQL query to explain")
    params: list[Any] | None = Field(
        default=None,
        description="Parameter values (for accurate estimates)"
    )
    analyze: bool = Field(
        default=False,
        description="Actually execute query to get real timings (slower but more accurate)"
    )
    format: str = Field(
        default="text",
        pattern="^(text|json|yaml)$",
        description="Output format for the plan"
    )
    verbose: bool = Field(
        default=False,
        description="Include additional detail in the plan"
    )
    buffers: bool = Field(
        default=False,
        description="Include buffer usage statistics (requires analyze=true)"
    )
```

**Output Schema**:
```python
class ExplainQueryOutput(BaseModel):
    """Output for explain_query tool."""
    plan: str | dict = Field(description="Query execution plan")
    format: str
    estimated_cost: float | None = Field(description="Total estimated cost")
    estimated_rows: int | None = Field(description="Estimated rows returned")
    actual_time_ms: float | None = Field(description="Actual execution time (if analyze=true)")
    warnings: list[str] | None = Field(description="Potential performance issues detected")
```

**Tool Annotations**:
- `readOnlyHint`: true (unless analyze=true)
- `destructiveHint`: false
- `idempotentHint`: true
- `openWorldHint`: false

**Example Output** (format="text"):
```json
{
  "plan": "Hash Join  (cost=234.00..456.78 rows=1000 width=48)\n  Hash Cond: (orders.user_id = users.id)\n  ->  Seq Scan on orders  (cost=0.00..189.00 rows=5000 width=24)\n        Filter: (status = 'pending')\n  ->  Hash  (cost=159.00..159.00 rows=6000 width=24)\n        ->  Seq Scan on users  (cost=0.00..159.00 rows=6000 width=24)",
  "format": "text",
  "estimated_cost": 456.78,
  "estimated_rows": 1000,
  "actual_time_ms": null,
  "warnings": ["Sequential scan on 'orders' table - consider index on 'status' column"]
}
```

---

## 7. Error Handling

### 7.1 Error Response Schema

All tools MUST return structured errors following this schema:

```python
class ErrorDetail(BaseModel):
    """Detailed error information."""
    code: str = Field(description="Machine-readable error code")
    message: str = Field(description="Human-readable error message")
    suggestion: str | None = Field(description="Actionable suggestion to resolve the error")
    context: dict[str, Any] | None = Field(description="Additional context for debugging")


class ToolError(BaseModel):
    """Standard error response for tool failures."""
    error: ErrorDetail
    tool_name: str
    input_received: dict[str, Any] | None
```

### 7.2 Error Codes

| Code | Description | Typical Suggestion |
|------|-------------|-------------------|
| `SCHEMA_NOT_FOUND` | Specified schema does not exist | List available schemas with list_schemas |
| `TABLE_NOT_FOUND` | Specified table does not exist | List tables in schema with list_tables |
| `COLUMN_NOT_FOUND` | Specified column does not exist | Describe table to see available columns |
| `INVALID_SQL` | SQL syntax error | Review query syntax |
| `WRITE_OPERATION_DENIED` | Attempted write operation | This server only supports read operations |
| `QUERY_TIMEOUT` | Query exceeded timeout | Simplify query or increase timeout |
| `CONNECTION_ERROR` | Database connection failed | Check database connectivity |
| `PERMISSION_DENIED` | Insufficient database privileges | Contact database administrator |
| `PARAMETER_ERROR` | Invalid parameter value | Review parameter constraints |
| `PATH_NOT_FOUND` | No join path exists between tables | Tables may not be related via foreign keys |

### 7.3 Example Error Response

```json
{
  "error": {
    "code": "TABLE_NOT_FOUND",
    "message": "Table 'order' does not exist in schema 'public'",
    "suggestion": "Did you mean 'orders'? Use list_tables to see available tables.",
    "context": {
      "requested_table": "order",
      "requested_schema": "public",
      "similar_tables": ["orders", "order_items", "order_history"]
    }
  },
  "tool_name": "describe_table",
  "input_received": {
    "table_name": "order",
    "schema_name": "public"
  }
}
```

---

## 8. Security Requirements

### 8.1 Query Validation

The server MUST implement strict query validation:

1. **Allowlist Approach**: Only permit SELECT statements and WITH clauses that resolve to SELECT
2. **Statement Parsing**: Use SQLAlchemy's SQL parser or sqlparse to analyze query structure
3. **Keyword Blocking**: Reject queries containing dangerous keywords even in comments

**Blocked Keywords** (case-insensitive):
- Data Modification: INSERT, UPDATE, DELETE, UPSERT, MERGE
- Schema Modification: CREATE, ALTER, DROP, TRUNCATE, RENAME
- Permissions: GRANT, REVOKE
- Session: SET, RESET, DISCARD
- Administrative: VACUUM, ANALYZE, CLUSTER, REINDEX, COPY
- Transaction: BEGIN, COMMIT, ROLLBACK, SAVEPOINT

### 8.2 Parameter Handling

1. All user-provided values MUST use parameterized queries
2. Parameters MUST be type-validated before execution
3. String parameters MUST NOT be interpolated directly into SQL

### 8.3 Connection Security

1. Database credentials MUST be stored using SecretStr (masked in logs)
2. SSL/TLS SHOULD be required for production deployments
3. Connection strings MUST NOT be logged

### 8.4 Result Sanitization

1. Large results MUST be truncated to configured limits
2. Binary data SHOULD be base64-encoded or excluded
3. Sensitive column patterns (password, secret, token) MAY be redacted

---

## 9. Performance Considerations

### 9.1 Connection Pooling

- Use SQLAlchemy's async connection pool
- Configure pool size based on expected concurrency
- Implement connection health checks

### 9.2 Query Timeouts

- Apply statement_timeout at the database session level
- Provide per-query timeout override option
- Return partial results on timeout where possible

### 9.3 Result Limits

- Enforce maximum row limits on all queries
- Warn when results are truncated
- Consider cursor-based pagination for large result sets (future enhancement)

---

## 10. Testing Requirements

### 10.1 Unit Tests

- Test each tool with valid inputs
- Test error handling for invalid inputs
- Test SQL validation with attack vectors
- Mock database connections for isolation

### 10.2 Integration Tests

- Test against real PostgreSQL instance (Docker)
- Test connection pooling under load
- Test timeout handling
- Test with various PostgreSQL versions (14, 15, 16)

### 10.3 MCP Protocol Tests

- Test tool registration and discovery
- Test both STDIO and HTTP transports
- Test error response formatting
- Test with MCP Inspector

---

## 11. Documentation Requirements

### 11.1 README.md

- Installation instructions (UV-based)
- Configuration guide
- Quick start examples
- Transport configuration (STDIO vs HTTP)

### 11.2 Tool Documentation

- Each tool MUST have comprehensive docstrings
- Include examples in tool descriptions
- Document all parameters with constraints

### 11.3 API Documentation

- OpenAPI/JSON Schema for HTTP transport
- MCP tool schemas exportable

---

## 12. Future Considerations (Post-MVP)

These items are explicitly out of scope for MVP but should inform architectural decisions:

### 12.1 MCP Resources

- Expose schemas as browsable resources
- Expose saved queries as resources
- Query results as cacheable resources

### 12.2 MCP Prompts

- "Explore database" workflow prompt
- "Generate report" query template
- "Find data" natural language interface

### 12.3 Write Operations

- Controlled INSERT/UPDATE/DELETE with confirmation
- Transaction support
- Audit logging

### 12.4 Advanced Features

- Multi-database connections
- Query result caching
- Query history and favorites
- Natural language to SQL translation
- Schema visualization/ERD generation

---

## 13. Success Metrics

### 13.1 Functional Metrics

- All 8 tools implemented and passing tests
- Both transports operational
- Error rate < 1% for valid queries

### 13.2 Quality Metrics

- Test coverage > 80%
- All tools have comprehensive docstrings
- No critical security vulnerabilities

### 13.3 Usability Metrics

- LLM can successfully explore unknown database schema
- LLM can construct valid multi-table queries using discovered relationships
- Average tool calls to answer question < 5 (for typical queries)

---

## 14. Appendix

### 14.1 Reference SQL Queries

**List Schemas Query**:
```sql
SELECT 
    n.nspname AS name,
    pg_catalog.pg_get_userbyid(n.nspowner) AS owner,
    pg_catalog.obj_description(n.oid, 'pg_namespace') AS description,
    (SELECT count(*) FROM pg_tables WHERE schemaname = n.nspname) AS table_count
FROM pg_catalog.pg_namespace n
WHERE n.nspname !~ '^pg_' 
  AND n.nspname <> 'information_schema'
ORDER BY n.nspname;
```

**List Tables Query**:
```sql
SELECT 
    t.tablename AS name,
    t.schemaname AS schema_name,
    'table' AS type,
    pg_catalog.obj_description(c.oid, 'pg_class') AS description,
    c.reltuples::bigint AS estimated_row_count,
    pg_total_relation_size(c.oid) AS size_bytes,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS size_pretty,
    EXISTS(SELECT 1 FROM pg_index i WHERE i.indrelid = c.oid AND i.indisprimary) AS has_primary_key,
    (SELECT count(*) FROM information_schema.columns col 
     WHERE col.table_schema = t.schemaname AND col.table_name = t.tablename) AS column_count
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename 
JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.schemaname
WHERE t.schemaname = $1
ORDER BY t.tablename;
```

**Foreign Keys Query**:
```sql
SELECT
    tc.constraint_name,
    tc.table_schema AS from_schema,
    tc.table_name AS from_table,
    array_agg(kcu.column_name ORDER BY kcu.ordinal_position) AS from_columns,
    ccu.table_schema AS to_schema,
    ccu.table_name AS to_table,
    array_agg(ccu.column_name ORDER BY kcu.ordinal_position) AS to_columns,
    rc.update_rule AS on_update,
    rc.delete_rule AS on_delete
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name 
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu 
    ON tc.constraint_name = ccu.constraint_name
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = $1 
  AND tc.table_name = $2
GROUP BY tc.constraint_name, tc.table_schema, tc.table_name, 
         ccu.table_schema, ccu.table_name, rc.update_rule, rc.delete_rule;
```

### 14.2 Example pyproject.toml

```toml
[project]
name = "pg-mcp-server"
version = "0.1.0"
description = "PostgreSQL MCP Server with layered schema discovery"
readme = "README.md"
requires-python = ">=3.11"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "you@example.com"}
]
keywords = ["mcp", "postgresql", "llm", "database", "ai"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "mcp>=1.0.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "uvicorn>=0.30.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[project.scripts]
pg-mcp-server = "pg_mcp_server.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/pg_mcp_server"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 15. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-14 | Sequenzia | Initial draft |
