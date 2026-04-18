from mcp.types import Tool

from ..app import get_context, register_tool


def register() -> None:
    register_tool(
        Tool(
            name="get_execution_policy",
            description="Return the active execution policy.",
            inputSchema={"type": "object", "properties": {}},
        ),
        _get_policy,
    )
    register_tool(
        Tool(
            name="validate_sql_against_policy",
            description="Validate SQL against active policy WITHOUT executing.",
            inputSchema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        ),
        _validate_sql,
    )
    register_tool(
        Tool(
            name="refresh_policy",
            description="Reload policy file from disk.",
            inputSchema={"type": "object", "properties": {}},
        ),
        _refresh,
    )


async def _get_policy(args: dict) -> dict:
    return get_context().policy.current_policy().model_dump()


async def _validate_sql(args: dict) -> dict:
    return get_context().policy.validate(args["query"])


async def _refresh(args: dict) -> dict:
    ctx = get_context()
    ctx.policy.reload()
    return {"reloaded": True, "profile": ctx.policy.current_policy().profile_name}
