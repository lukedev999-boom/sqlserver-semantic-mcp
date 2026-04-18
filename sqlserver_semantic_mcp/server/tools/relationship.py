from mcp.types import Tool

from ...services import relationship_service
from ..app import get_context, register_tool


def register() -> None:
    register_tool(
        Tool(
            name="get_table_relationships",
            description="List inbound + outbound FK relationships for a table.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "table":  {"type": "string"},
                },
                "required": ["schema", "table"],
            },
        ),
        _rels,
    )
    register_tool(
        Tool(
            name="find_join_path",
            description=(
                "Find a shortest FK-based join path between two tables "
                "(BFS, bidirectional edges)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_schema": {"type": "string"},
                    "from_table":  {"type": "string"},
                    "to_schema":   {"type": "string"},
                    "to_table":    {"type": "string"},
                    "max_hops":    {"type": "integer", "minimum": 1, "default": 5},
                },
                "required": ["from_schema", "from_table", "to_schema", "to_table"],
            },
        ),
        _path,
    )
    register_tool(
        Tool(
            name="get_dependency_chain",
            description="List all tables reachable from a given table via FKs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "table":  {"type": "string"},
                    "max_depth": {"type": "integer", "default": 10},
                },
                "required": ["schema", "table"],
            },
        ),
        _chain,
    )


async def _rels(args: dict) -> list[dict]:
    ctx = get_context()
    return await relationship_service.get_table_relationships(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
        args["schema"], args["table"],
    )


async def _path(args: dict) -> dict:
    ctx = get_context()
    path = await relationship_service.find_join_path(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
        args["from_schema"], args["from_table"],
        args["to_schema"], args["to_table"],
        max_hops=args.get("max_hops", 5),
    )
    return {"found": path is not None, "path": path or []}


async def _chain(args: dict) -> list[dict]:
    ctx = get_context()
    return await relationship_service.get_dependency_chain(
        ctx.cfg.cache_path, ctx.cfg.mssql_database,
        args["schema"], args["table"],
        max_depth=args.get("max_depth", 10),
    )
