from mcp.types import Tool

from ..app import get_context, register_tool


def register() -> None:
    register_tool(
        Tool(
            name="validate_query",
            description="Analyze a SQL query and report intent + whether policy allows it.",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        _validate,
    )
    register_tool(
        Tool(
            name="run_safe_query",
            description=(
                "Execute SQL after policy validation. Result rows are truncated "
                "to max_rows_returned."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_rows": {"type": "integer", "minimum": 1},
                },
                "required": ["query"],
            },
        ),
        _run_safe,
    )


async def _validate(args: dict) -> dict:
    return get_context().query.validate(args["query"])


async def _run_safe(args: dict) -> dict:
    return get_context().query.run_safe_query(
        args["query"], max_rows=args.get("max_rows"),
    )
