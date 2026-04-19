"""MCP prompts for agent-oriented workflows."""
from . import execution, discovery, analysis  # noqa: F401
from .registry import register_prompts

__all__ = ["register_prompts"]
