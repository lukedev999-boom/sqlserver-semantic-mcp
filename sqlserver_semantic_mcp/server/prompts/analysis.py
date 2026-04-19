"""Object / impact analysis prompts."""
from __future__ import annotations

from mcp.types import (
    GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent,
)

from .registry import register_prompt


_PROMPT = Prompt(
    name="trace_data_impact",
    description=(
        "Trace the downstream impact of changing a view/procedure/function "
        "without dumping raw SQL bodies into the context."
    ),
    arguments=[
        PromptArgument(name="schema", required=True),
        PromptArgument(name="name", required=True),
        PromptArgument(
            name="type",
            description="VIEW | PROCEDURE | FUNCTION",
            required=True,
        ),
    ],
)


_BODY = """You need to understand the impact of modifying {type} {schema}.{name}. Follow the impact chain:

1. `summarize_object_for_impact(schema={schema!r}, name={name!r}, type={type!r})` — returns reads / writes / depends_on in compact form.
2. `trace_object_dependencies(schema={schema!r}, name={name!r}, type={type!r})` — returns the dependency list.
3. `bundle_context_for_next_step(items=[...], goal="object_impact")` — compress before recommending changes.

Only request full definitions (`describe_view` / `describe_procedure` with detail="full") if the summaries leave a concrete gap.
"""


async def _handler(arguments: dict) -> GetPromptResult:
    schema = arguments.get("schema", "")
    name = arguments.get("name", "")
    obj_type = (arguments.get("type") or "VIEW").upper()
    text = _BODY.format(schema=schema, name=name, type=obj_type)
    return GetPromptResult(
        description="Impact analysis chain for schema objects.",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=text),
            ),
        ],
    )


def register() -> None:
    register_prompt(_PROMPT, _handler)
