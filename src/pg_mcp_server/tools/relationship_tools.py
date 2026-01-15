"""Layer 2: Relationship Discovery Tools.

These tools help LLMs discover foreign key relationships and join paths
between tables.
"""

from typing import Any

from mcp.server.fastmcp import Context
from mcp.server.session import ServerSession
from mcp.types import ToolAnnotations

from pg_mcp_server.database.relationships import RelationshipService
from pg_mcp_server.errors import ErrorCode, create_tool_error
from pg_mcp_server.models.relationships import (
    FindJoinPathOutput,
    ForeignKeyRelation,
    GetForeignKeysOutput,
    JoinPath,
    JoinStep,
)
from pg_mcp_server.server import AppContext, mcp


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def get_foreign_keys(
    table_name: str,
    schema_name: str = "public",
    ctx: Context[ServerSession, AppContext] | None = None,
) -> GetForeignKeysOutput | dict[str, Any]:
    """Get foreign key relationships for a table.

    Returns both outgoing (this table references other tables) and incoming
    (other tables reference this table) foreign key relationships.

    Args:
        table_name: Name of the table
        schema_name: Schema containing the table. Default: "public"

    Returns:
        Outgoing and incoming foreign key relationships.

    Example:
        get_foreign_keys(table_name="orders") -> {"outgoing": [...], "incoming": [...]}
    """
    if ctx is None:
        return create_tool_error(
            ErrorCode.CONNECTION_ERROR,
            "No context available",
            "get_foreign_keys",
        )

    app_ctx = ctx.request_context.lifespan_context

    try:
        async with app_ctx.engine.connect() as conn:
            service = RelationshipService(conn, app_ctx.settings.database.statement_timeout)
            outgoing = await service.get_outgoing_fks(schema_name, table_name)
            incoming = await service.get_incoming_fks(schema_name, table_name)

        return GetForeignKeysOutput(
            table_name=table_name,
            schema_name=schema_name,
            outgoing=[ForeignKeyRelation(**fk) for fk in outgoing],
            incoming=[ForeignKeyRelation(**fk) for fk in incoming],
            outgoing_count=len(outgoing),
            incoming_count=len(incoming),
        )
    except Exception as e:
        return create_tool_error(
            ErrorCode.TABLE_NOT_FOUND
            if "not exist" in str(e).lower()
            else ErrorCode.CONNECTION_ERROR,
            str(e),
            "get_foreign_keys",
            {"table_name": table_name, "schema_name": schema_name},
        )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def find_join_path(
    from_table: str,
    to_table: str,
    from_schema: str = "public",
    to_schema: str = "public",
    max_depth: int = 4,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> FindJoinPathOutput | dict[str, Any]:
    """Find join paths between two tables.

    Discovers possible paths to join two tables via foreign key relationships.
    Returns SQL examples for each path found.

    Args:
        from_table: Starting table name
        to_table: Target table name
        from_schema: Schema of starting table. Default: "public"
        to_schema: Schema of target table. Default: "public"
        max_depth: Maximum joins to traverse (1-6). Default: 4

    Returns:
        List of possible join paths with SQL examples.

    Example:
        find_join_path(from_table="order_items", to_table="users") -> {"paths": [...]}
    """
    if ctx is None:
        return create_tool_error(
            ErrorCode.CONNECTION_ERROR,
            "No context available",
            "find_join_path",
        )

    # Clamp max_depth to valid range
    max_depth = max(1, min(6, max_depth))

    app_ctx = ctx.request_context.lifespan_context

    try:
        async with app_ctx.engine.connect() as conn:
            service = RelationshipService(conn, app_ctx.settings.database.statement_timeout)
            paths = await service.find_join_path(
                from_schema, from_table, to_schema, to_table, max_depth
            )

        # Convert paths to JoinPath objects
        join_paths = []
        for path in paths:
            steps = []
            for edge in path:
                from_parts = edge["from"].split(".")
                to_parts = edge["to"].split(".")

                # Determine join type based on FK direction
                is_reversed = edge.get("reversed", False)
                join_type = "LEFT JOIN" if is_reversed else "INNER JOIN"

                steps.append(
                    JoinStep(
                        from_schema=from_parts[0],
                        from_table=from_parts[1],
                        from_column=edge["from_col"],
                        to_schema=to_parts[0],
                        to_table=to_parts[1],
                        to_column=edge["to_col"],
                        join_type=join_type,
                        constraint_name=edge["constraint"],
                    )
                )

            # Generate SQL example
            sql_parts = [f"FROM {from_schema}.{from_table}"]
            prev_table = from_table
            for step in steps:
                sql_parts.append(
                    f"{step.join_type} {step.to_schema}.{step.to_table} "
                    f"ON {prev_table}.{step.from_column} = {step.to_table}.{step.to_column}"
                )
                prev_table = step.to_table

            join_paths.append(
                JoinPath(
                    steps=steps,
                    depth=len(steps),
                    sql_example=" ".join(sql_parts),
                )
            )

        note = None
        if len(join_paths) > 1:
            note = f"Multiple paths found ({len(join_paths)}), showing all"
        elif len(join_paths) == 0:
            note = "No path found between tables via foreign keys"

        return FindJoinPathOutput(
            from_table=from_table,
            to_table=to_table,
            paths=join_paths,
            paths_found=len(join_paths),
            note=note,
        )
    except Exception as e:
        return create_tool_error(
            ErrorCode.PATH_NOT_FOUND if "path" in str(e).lower() else ErrorCode.CONNECTION_ERROR,
            str(e),
            "find_join_path",
            {
                "from_table": from_table,
                "to_table": to_table,
                "from_schema": from_schema,
                "to_schema": to_schema,
            },
        )
