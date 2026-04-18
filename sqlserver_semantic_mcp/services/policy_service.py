from typing import Optional

from ..config import Config, get_config
from ..policy.analyzer import analyze_sql
from ..policy.enforcer import enforce
from ..policy.loader import load_active_policy
from ..policy.models import PolicyProfile


class PolicyService:
    def __init__(self, cfg: Optional[Config] = None) -> None:
        self._cfg = cfg or get_config()
        self._policy: Optional[PolicyProfile] = None

    def load(self) -> None:
        self._policy = load_active_policy(self._cfg)

    def reload(self) -> None:
        self.load()

    def current_policy(self) -> PolicyProfile:
        if self._policy is None:
            self.load()
        assert self._policy is not None
        return self._policy

    def validate(self, sql: str, database: str = "") -> dict:
        policy = self.current_policy()
        intent = analyze_sql(sql)
        result = enforce(intent, policy, database=database)
        return {
            "allowed": result.allowed,
            "reason": result.reason,
            "intent": {
                "primary_operation": intent.primary_operation.value,
                "has_where_clause": intent.has_where_clause,
                "has_top_clause": intent.has_top_clause,
                "affected_tables": intent.affected_tables,
                "risk_level": intent.risk_level.value,
                "is_multi_statement": intent.is_multi_statement,
                "statement_count": intent.statement_count,
            },
        }
