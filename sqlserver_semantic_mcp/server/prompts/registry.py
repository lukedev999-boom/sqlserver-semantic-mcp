"""Prompt registry wired up against ``server.app.app``."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from mcp.types import GetPromptResult, Prompt, PromptArgument

from ..app import app


Handler = Callable[[dict[str, Any]], Awaitable[GetPromptResult]]
_REGISTRY: dict[str, tuple[Prompt, Handler]] = {}


def register_prompt(prompt: Prompt, handler: Handler) -> None:
    _REGISTRY[prompt.name] = (prompt, handler)


@app.list_prompts()
async def _list_prompts() -> list[Prompt]:
    return [p for (p, _) in _REGISTRY.values()]


@app.get_prompt()
async def _get_prompt(name: str, arguments: dict | None = None) -> GetPromptResult:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown prompt: {name}")
    _p, handler = _REGISTRY[name]
    return await handler(arguments or {})


def register_prompts() -> None:
    """Import prompt modules to trigger their registrations."""
    from . import execution, discovery, analysis  # noqa: F401

    execution.register()
    discovery.register()
    analysis.register()


__all__ = ["PromptArgument", "Prompt", "register_prompt", "register_prompts"]
