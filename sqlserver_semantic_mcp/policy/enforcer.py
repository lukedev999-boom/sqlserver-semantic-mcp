from dataclasses import dataclass

from ..domain.enums import SqlOperation
from .analyzer import SqlIntent
from .models import PolicyProfile


@dataclass
class EnforcementResult:
    allowed: bool
    reason: str


_OP_FIELD = {
    SqlOperation.SELECT:   "select",
    SqlOperation.INSERT:   "insert",
    SqlOperation.UPDATE:   "update",
    SqlOperation.DELETE:   "delete",
    SqlOperation.TRUNCATE: "truncate",
    SqlOperation.CREATE:   "create",
    SqlOperation.ALTER:    "alter",
    SqlOperation.DROP:     "drop",
    SqlOperation.EXEC:     "execute",
    SqlOperation.EXECUTE:  "execute",
    SqlOperation.MERGE:    "merge",
}


def _bare(name: str) -> str:
    return name.strip("[]").split(".")[-1].strip("[]")


def enforce(
    intent: SqlIntent, policy: PolicyProfile, database: str = "",
) -> EnforcementResult:
    op = intent.primary_operation
    if op == SqlOperation.UNKNOWN:
        return EnforcementResult(False, "Unable to determine SQL operation")

    field = _OP_FIELD.get(op)
    if field is None or not getattr(policy.operations, field, False):
        return EnforcementResult(
            False, f"Operation {op.value} is not allowed by policy"
        )

    if intent.is_multi_statement and not policy.constraints.allow_multi_statement:
        return EnforcementResult(False, "Multi-statement queries are not allowed")

    if op == SqlOperation.UPDATE and policy.constraints.require_where_for_update \
            and not intent.has_where_clause:
        return EnforcementResult(False, "UPDATE requires a WHERE clause")

    if op == SqlOperation.DELETE and policy.constraints.require_where_for_delete \
            and not intent.has_where_clause:
        return EnforcementResult(False, "DELETE requires a WHERE clause")

    if op == SqlOperation.SELECT and policy.constraints.require_top_for_select \
            and not intent.has_top_clause:
        return EnforcementResult(False, "SELECT requires a TOP clause")

    scope = policy.scope

    if scope.allowed_databases and database:
        if database not in scope.allowed_databases:
            return EnforcementResult(
                False, f"Database '{database}' is not allowed by policy"
            )

    bare_tables = [_bare(t) for t in intent.affected_tables]

    if scope.denied_tables:
        for name in bare_tables:
            if name in scope.denied_tables:
                return EnforcementResult(
                    False, f"Table '{name}' is denied by policy"
                )

    if scope.allowed_tables:
        for name in bare_tables:
            if name not in scope.allowed_tables:
                return EnforcementResult(
                    False,
                    f"Table '{name}' is not in the allowed tables list",
                )

    if scope.allowed_schemas:
        for t in intent.affected_tables:
            parts = t.strip("[]").split(".")
            if len(parts) == 2:
                schema = parts[0].strip("[]")
                if schema not in scope.allowed_schemas:
                    return EnforcementResult(
                        False,
                        f"Schema '{schema}' is not in the allowed schemas list",
                    )
            else:
                # Unqualified table name — cannot verify schema, reject
                return EnforcementResult(
                    False,
                    f"Table '{t}' is unqualified; allowed_schemas requires "
                    f"schema-qualified names (e.g., 'dbo.{t}')",
                )

    return EnforcementResult(True, "Query is allowed")
