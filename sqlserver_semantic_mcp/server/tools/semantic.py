from mcp.types import Tool

from ...services import semantic_service
from ..app import get_context, register_tool


def register() -> None:
    register_tool(
        Tool(
            name="classify_table",
            description="Classify a table (fact / dimension / lookup / bridge / audit).",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "table":  {"type": "string"},
                    "force":  {"type": "boolean", "default": False},
                },
                "required": ["schema", "table"],
            },
        ),
        _classify,
    )
    register_tool(
        Tool(
            name="analyze_columns",
            description="Return semantic labels for each column (audit, status, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "table":  {"type": "string"},
                },
                "required": ["schema", "table"],
            },
        ),
        _columns,
    )
    register_tool(
        Tool(
            name="detect_lookup_tables",
            description="Scan DB and return likely lookup tables.",
            inputSchema={"type": "object", "properties": {}},
        ),
        _lookups,
    )


async def _classify(args: dict) -> dict:
    ctx = get_context()
    return await semantic_service.classify_table(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
        args["schema"], args["table"],
        force=args.get("force", False),
    )


async def _columns(args: dict) -> list[dict]:
    ctx = get_context()
    return await semantic_service.analyze_columns(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
        args["schema"], args["table"],
    )


async def _lookups(args: dict) -> list[dict]:
    ctx = get_context()
    return await semantic_service.detect_lookup_tables(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
    )
