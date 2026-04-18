from mcp.types import Tool

from ...services import metadata_service
from ..app import get_context, register_tool


def register() -> None:
    register_tool(
        Tool(
            name="get_tables",
            description="List all tables in the database (schema + name).",
            inputSchema={"type": "object", "properties": {}},
        ),
        _get_tables,
    )
    register_tool(
        Tool(
            name="describe_table",
            description="Return columns, PK, FKs, indexes, and description of a table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "table":  {"type": "string"},
                },
                "required": ["schema", "table"],
            },
        ),
        _describe_table,
    )
    register_tool(
        Tool(
            name="get_columns",
            description="List columns of a table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "table":  {"type": "string"},
                },
                "required": ["schema", "table"],
            },
        ),
        _get_columns,
    )


async def _get_tables(args: dict) -> list[dict]:
    ctx = get_context()
    return await metadata_service.list_tables(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
    )


async def _describe_table(args: dict) -> dict | None:
    ctx = get_context()
    return await metadata_service.describe_table(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
        args["schema"], args["table"],
    )


async def _get_columns(args: dict) -> list[dict]:
    ctx = get_context()
    return await metadata_service.list_columns(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
        args["schema"], args["table"],
    )
