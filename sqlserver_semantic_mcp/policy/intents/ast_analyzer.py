"""AST analyzer placeholder.

Currently falls back to :class:`RegexIntentAnalyzer`. The slot exists so
the workflow layer and tests do not need to change when a real parser
lands.
"""
from __future__ import annotations

from ..analyzer import SqlIntent
from .regex_analyzer import RegexIntentAnalyzer


class AstIntentAnalyzer:
    name = "ast"

    def __init__(self) -> None:
        self._fallback = RegexIntentAnalyzer()

    def analyze(self, sql: str) -> SqlIntent:
        # Real AST analysis TBD; until then, return the regex result but
        # lower the confidence so routing code can treat it as provisional.
        intent = self._fallback.analyze(sql)
        intent.confidence = min(intent.confidence, 0.7)
        return intent
