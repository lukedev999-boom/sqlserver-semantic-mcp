from mcp.types import Tool

from ...services import object_service
from ..app import get_context, register_tool


def register() -> None:
    register_tool(
        Tool(
            name="describe_view",
            description="Return view definition + dependencies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "name":   {"type": "string"},
                },
                "required": ["schema", "name"],
            },
        ),
        _describe_view,
    )
    register_tool(
        Tool(
            name="describe_procedure",
            description="Return stored procedure definition + dependencies.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "name":   {"type": "string"},
                },
                "required": ["schema", "name"],
            },
        ),
        _describe_procedure,
    )
    register_tool(
        Tool(
            name="trace_object_dependencies",
            description="Return a list of objects/tables the given object depends on.",
            inputSchema={
                "type": "object",
                "properties": {
                    "schema": {"type": "string"},
                    "name":   {"type": "string"},
                    "type":   {"type": "string",
                               "enum": ["VIEW", "PROCEDURE", "FUNCTION"]},
                },
                "required": ["schema", "name", "type"],
            },
        ),
        _trace,
    )


async def _describe_view(args: dict) -> dict:
    ctx = get_context()
    return await object_service.describe_object(
        args["schema"], args["name"], "VIEW", ctx.cfg,
    )


async def _describe_procedure(args: dict) -> dict:
    ctx = get_context()
    return await object_service.describe_object(
        args["schema"], args["name"], "PROCEDURE", ctx.cfg,
    )


async def _trace(args: dict) -> list[str]:
    ctx = get_context()
    return await object_service.trace_dependencies(
        args["schema"], args["name"], args["type"], ctx.cfg,
    )
