import hashlib
from typing import Any

from mcp.types import Tool

from ...services import object_service
from ..app import get_context, register_tool
from .shape import project_describe_object, resolve_detail


_DETAIL_PROP = {
    "type": "string", "enum": ["brief", "standard", "full"],
    "default": "brief",
    "description": "Response verbosity. brief strips definition; full always "
                   "includes it. include_definition overrides to include at "
                   "brief/standard tiers.",
}


def _input_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "schema":             {"type": "string"},
            "name":               {"type": "string"},
            "detail":             _DETAIL_PROP,
            "include_definition": {"type": "boolean", "default": False},
        },
        "required": ["schema", "name"],
    }


def register() -> None:
    register_tool(
        Tool(
            name="describe_view",
            description=(
                "Return view metadata + dependencies. detail=brief (default) "
                "strips SQL definition; detail=full or include_definition=true "
                "returns the full text."
            ),
            inputSchema=_input_schema(),
        ),
        _describe_view,
    )
    register_tool(
        Tool(
            name="describe_procedure",
            description=(
                "Return procedure metadata + dependencies. detail=brief (default) "
                "strips SQL definition; detail=full or include_definition=true "
                "returns the full text."
            ),
            inputSchema=_input_schema(),
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


def _attach_hash_and_bytes(obj: dict) -> dict:
    definition = obj.get("definition")
    if not isinstance(definition, str) or not definition:
        return obj
    if "definition_hash" in obj and "definition_bytes" in obj:
        return obj
    encoded = definition.encode("utf-8")
    out = dict(obj)
    out.setdefault("definition_hash", hashlib.sha1(encoded).hexdigest()[:8])
    out.setdefault("definition_bytes", len(encoded))
    return out


async def _describe_object(args: dict, object_type: str) -> dict:
    ctx = get_context()
    detail = resolve_detail(args)
    include = bool(args.get("include_definition", False))
    obj = await object_service.describe_object(
        args["schema"], args["name"], object_type, ctx.cfg,
    )
    obj = _attach_hash_and_bytes(obj)
    return project_describe_object(obj, detail=detail, include_definition=include)


async def _describe_view(args: dict) -> dict:
    return await _describe_object(args, "VIEW")


async def _describe_procedure(args: dict) -> dict:
    return await _describe_object(args, "PROCEDURE")


async def _trace(args: dict) -> list[str]:
    ctx = get_context()
    return await object_service.trace_dependencies(
        args["schema"], args["name"], args["type"], ctx.cfg,
    )
