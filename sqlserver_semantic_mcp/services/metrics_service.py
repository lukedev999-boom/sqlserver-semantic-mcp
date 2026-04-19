"""Per-tool response metrics recording and query.

See docs/superpowers/specs/2026-04-19-p4-measurement-design.md for the
original design. v0.5 extends the record with workflow-aware fields so
the team can measure how many tasks complete via the direct-execute
fast path and which tools still dominate the token budget.
"""
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite


_EXTRA_FIELDS = (
    "route_type",
    "detail",
    "response_mode",
    "token_budget_hint",
    "was_direct_execute",
    "bundle_used",
    "next_action",
)


async def _ensure_extra_columns(db: aiosqlite.Connection) -> None:
    """Best-effort migration for in-place stores created before v0.5."""
    cur = await db.execute("PRAGMA table_info(tool_metrics)")
    existing = {row[1] for row in await cur.fetchall()}
    for col in _EXTRA_FIELDS:
        if col not in existing:
            coltype = "INTEGER" if col in ("was_direct_execute", "bundle_used") else "TEXT"
            await db.execute(
                f"ALTER TABLE tool_metrics ADD COLUMN {col} {coltype}"
            )
    await db.commit()


async def record_metric(
    db_path: str, tool_name: str, *,
    response_bytes: int,
    array_length: Optional[int] = None,
    fields_returned: Optional[int] = None,
    route_type: Optional[str] = None,
    detail: Optional[str] = None,
    response_mode: Optional[str] = None,
    token_budget_hint: Optional[str] = None,
    was_direct_execute: Optional[bool] = None,
    bundle_used: Optional[bool] = None,
    next_action: Optional[str] = None,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await _ensure_extra_columns(db)
        await db.execute(
            "INSERT INTO tool_metrics "
            "(tool_name, response_bytes, array_length, fields_returned, "
            " route_type, detail, response_mode, token_budget_hint, "
            " was_direct_execute, bundle_used, next_action, recorded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tool_name, response_bytes, array_length, fields_returned,
                route_type, detail, response_mode, token_budget_hint,
                1 if was_direct_execute else (0 if was_direct_execute is False else None),
                1 if bundle_used else (0 if bundle_used is False else None),
                next_action,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        await db.commit()


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    vs = sorted(values)
    idx = max(0, int(0.95 * len(vs)) - 1)
    return vs[idx]


async def query_top_tools(db_path: str, *, limit: int = 10) -> list[dict]:
    """Return tool metrics aggregated, ordered by total_bytes desc."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await _ensure_extra_columns(db)
        cur = await db.execute(
            "SELECT tool_name, COUNT(*) AS call_count, "
            "       SUM(response_bytes) AS total_bytes, "
            "       AVG(response_bytes) AS avg_bytes, "
            "       MAX(response_bytes) AS max_bytes, "
            "       SUM(CASE WHEN was_direct_execute=1 THEN 1 ELSE 0 END) "
            "           AS direct_execute_count, "
            "       SUM(CASE WHEN bundle_used=1 THEN 1 ELSE 0 END) "
            "           AS bundle_count "
            "FROM tool_metrics "
            "GROUP BY tool_name "
            "ORDER BY total_bytes DESC "
            "LIMIT ?",
            (limit,),
        )
        aggregated = [dict(r) for r in await cur.fetchall()]

        for row in aggregated:
            cur = await db.execute(
                "SELECT response_bytes FROM tool_metrics "
                "WHERE tool_name=? ORDER BY response_bytes",
                (row["tool_name"],),
            )
            values = [r[0] for r in await cur.fetchall()]
            row["p95_bytes"] = _p95(values)
            row["avg_bytes"] = int(row["avg_bytes"] or 0)
        return aggregated


async def clear_metrics(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute("DELETE FROM tool_metrics")
        await db.commit()
        return cur.rowcount


__all__: list[str] = [
    "record_metric",
    "query_top_tools",
    "clear_metrics",
]
