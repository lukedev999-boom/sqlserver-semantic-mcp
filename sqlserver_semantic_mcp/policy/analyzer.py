import re
from dataclasses import dataclass, field
from typing import List

from ..domain.enums import SqlOperation, RiskLevel


@dataclass
class SqlIntent:
    primary_operation: SqlOperation
    has_where_clause: bool
    has_top_clause: bool
    affected_tables: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    is_multi_statement: bool = False
    statement_count: int = 1


_OP_MAP = {
    "SELECT": SqlOperation.SELECT,
    "INSERT": SqlOperation.INSERT,
    "UPDATE": SqlOperation.UPDATE,
    "DELETE": SqlOperation.DELETE,
    "TRUNCATE": SqlOperation.TRUNCATE,
    "CREATE": SqlOperation.CREATE,
    "ALTER": SqlOperation.ALTER,
    "DROP": SqlOperation.DROP,
    "EXEC": SqlOperation.EXEC,
    "EXECUTE": SqlOperation.EXECUTE,
    "MERGE": SqlOperation.MERGE,
}

_IDENT = r"\[?[\w]+\]?(?:\.\[?[\w]+\]?)?"


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", "", sql)
    return sql.strip()


def _split_statements(sql: str) -> list[str]:
    parts = re.split(r";\s*", sql)
    return [p.strip() for p in parts if p.strip()]


def _detect_operation(sql: str) -> SqlOperation:
    m = re.match(r"\s*([A-Za-z]+)", sql)
    if not m:
        return SqlOperation.UNKNOWN
    return _OP_MAP.get(m.group(1).upper(), SqlOperation.UNKNOWN)


def _extract_tables(sql: str, operation: SqlOperation) -> list[str]:
    tables: list[str] = []
    tables.extend(re.findall(rf"\bFROM\s+({_IDENT})", sql, re.IGNORECASE))
    tables.extend(re.findall(rf"\bJOIN\s+({_IDENT})", sql, re.IGNORECASE))

    if operation == SqlOperation.UPDATE:
        m = re.search(rf"\bUPDATE\s+({_IDENT})", sql, re.IGNORECASE)
        if m:
            tables.append(m.group(1))
    elif operation == SqlOperation.INSERT:
        m = re.search(rf"\bINTO\s+({_IDENT})", sql, re.IGNORECASE)
        if m:
            tables.append(m.group(1))
    elif operation == SqlOperation.DELETE:
        m = re.search(rf"\bDELETE\s+(?:FROM\s+)?({_IDENT})", sql, re.IGNORECASE)
        if m:
            tables.append(m.group(1))
    elif operation == SqlOperation.MERGE:
        m = re.search(rf"\bMERGE\s+(?:INTO\s+)?({_IDENT})", sql, re.IGNORECASE)
        if m:
            tables.append(m.group(1))
    elif operation in (SqlOperation.TRUNCATE, SqlOperation.DROP, SqlOperation.ALTER):
        m = re.search(rf"\b(?:TABLE|VIEW)\s+({_IDENT})", sql, re.IGNORECASE)
        if m:
            tables.append(m.group(1))

    seen = set()
    out = []
    for t in tables:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _compute_risk(
    operation: SqlOperation, has_where: bool, is_multi: bool,
) -> RiskLevel:
    if operation in (SqlOperation.DROP, SqlOperation.TRUNCATE):
        return RiskLevel.CRITICAL
    if operation == SqlOperation.ALTER:
        return RiskLevel.HIGH
    if operation == SqlOperation.DELETE:
        return RiskLevel.HIGH if not has_where else RiskLevel.MEDIUM
    if operation in (SqlOperation.UPDATE, SqlOperation.MERGE):
        return RiskLevel.HIGH if not has_where else RiskLevel.MEDIUM
    if operation in (SqlOperation.INSERT, SqlOperation.CREATE,
                     SqlOperation.EXEC, SqlOperation.EXECUTE):
        return RiskLevel.MEDIUM
    if is_multi:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def analyze_sql(sql: str) -> SqlIntent:
    clean = _strip_comments(sql)
    statements = _split_statements(clean)
    is_multi = len(statements) > 1
    first = statements[0] if statements else ""

    operation = _detect_operation(first)
    has_where = bool(re.search(r"\bWHERE\b", first, re.IGNORECASE))
    has_top = bool(re.search(r"\bTOP\b", first, re.IGNORECASE))
    tables = _extract_tables(first, operation)
    risk = _compute_risk(operation, has_where, is_multi)

    return SqlIntent(
        primary_operation=operation,
        has_where_clause=has_where,
        has_top_clause=has_top,
        affected_tables=tables,
        risk_level=risk,
        is_multi_statement=is_multi,
        statement_count=len(statements),
    )
