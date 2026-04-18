# P4 Measurement & Regression — Design Spec

**Date:** 2026-04-19
**Target release:** v0.5.0
**Baseline:** v0.4.0 (commit 0d97aae, post-P2+P3)

---

## 1. Goal & Scope

Record per-tool-call payload metrics so operators can answer **"which tools are burning the most tokens, and is P0–P3 actually helping over time?"** Provide a query tool to surface the top offenders.

**In scope:**

1. New SQLite table `tool_metrics` in the existing cache DB: `(tool_name, response_bytes, array_length, fields_returned, timestamp)`.
2. Instrument the `_call_tool` transport in `server/app.py` to insert a row **after** `compact()` + `json.dumps`, before returning to MCP.
3. New query tool `get_tool_metrics` returning aggregated stats per tool: `call_count`, `total_bytes`, `avg_bytes`, `p95_bytes`, `max_bytes`. Sorted by `total_bytes` desc by default.
4. Toggle via `SEMANTIC_MCP_METRICS_ENABLED` env var (default `true`).

**Out of scope:**

- Array-length summary for nested arrays (only top-level list length is captured).
- Per-call argument hashing or request fingerprinting.
- Per-task aggregation (`calls_per_task`) — requires correlation IDs from the client; deferred.
- External metrics push (Prometheus, OpenTelemetry).

---

## 2. Architecture

### 2.1 Table

```sql
CREATE TABLE IF NOT EXISTS tool_metrics (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  tool_name         TEXT NOT NULL,
  response_bytes    INTEGER NOT NULL,
  array_length      INTEGER,           -- NULL if response was a dict
  fields_returned   INTEGER,           -- number of top-level keys (NULL if list)
  recorded_at       TEXT NOT NULL      -- ISO-8601 UTC
);

CREATE INDEX IF NOT EXISTS ix_tool_metrics_tool_name
    ON tool_metrics(tool_name);
```

Added to `infrastructure/cache/store.py:SCHEMA` alongside existing tables.

### 2.2 Instrumentation in `_call_tool`

After computing the compact JSON text, but before wrapping in `TextContent`:

```python
compact_text = json.dumps(compact_result, ...)
if ctx.cfg.metrics_enabled:
    await _record_tool_metric(
        ctx.cfg.cache_path,
        name,
        response_bytes=len(compact_text.encode("utf-8")),
        array_length=len(compact_result) if isinstance(compact_result, list) else None,
        fields_returned=len(compact_result) if isinstance(compact_result, dict) else None,
    )
return [TextContent(...)]
```

Error branch also records (with `tool_name` = actual + `_ERROR` suffix marker?) — actually simpler: do NOT record on error path, to avoid polluting stats with failure payloads.

### 2.3 `get_tool_metrics` tool

Registered in the `metrics` group (new group) — so it can be toggled via `SEMANTIC_MCP_TOOL_PROFILE`. Accepts `limit` (default 10), returns:

```json
[
  {"tool": "describe_table", "call_count": 42, "total_bytes": 12480,
   "avg_bytes": 297, "p95_bytes": 412, "max_bytes": 512},
  ...
]
```

SQL aggregation:

```sql
SELECT
  tool_name,
  COUNT(*)                               AS call_count,
  SUM(response_bytes)                    AS total_bytes,
  AVG(response_bytes)                    AS avg_bytes,
  MAX(response_bytes)                    AS max_bytes
FROM tool_metrics
GROUP BY tool_name
ORDER BY total_bytes DESC
LIMIT ?;
```

SQLite lacks a native P95 aggregate; compute with a window query:

```sql
-- simpler approximation: 95th percentile via ORDER BY + index calc in Python
```

We compute `p95` in Python after the aggregation round-trip — grab all bytes for each top-N tool and take `sorted(bytes)[int(0.95 * len) - 1]`.

---

## 3. File Touch Points

| File | Change |
|---|---|
| `sqlserver_semantic_mcp/config.py` | add `metrics_enabled: bool = True` |
| `sqlserver_semantic_mcp/infrastructure/cache/store.py` | add `tool_metrics` table DDL |
| `sqlserver_semantic_mcp/services/metrics_service.py` | **new** — record + query helpers |
| `sqlserver_semantic_mcp/server/app.py` | instrument `_call_tool` success path |
| `sqlserver_semantic_mcp/server/tools/metrics.py` | **new** — `get_tool_metrics` registration |
| `sqlserver_semantic_mcp/server/tools/__init__.py` | register new `metrics` group |
| `tests/unit/test_metrics_service.py` | **new** — record + query cases |
| `tests/unit/test_call_tool_metrics.py` | **new** — end-to-end transport instrumentation |

---

## 4. Testing Strategy

### 4.1 `test_metrics_service.py`

- `record_metric(tool_name, bytes, array_len, fields)` inserts a row.
- Multiple records accumulate.
- `query_top_tools(limit=5)` returns sorted-by-total-bytes with correct aggregations.
- `p95_bytes` calculation correct for small and odd-sized samples.

### 4.2 `test_call_tool_metrics.py`

- Calling a tool through `_call_tool` records a metric.
- Error path does NOT record.
- `SEMANTIC_MCP_METRICS_ENABLED=false` disables recording.

---

## 5. Risk & Rollback

**Performance risk:** adding a SQLite insert per tool call adds ~1ms overhead. Mitigation: insert is sync from Python's perspective but uses aiosqlite (async) — no blocking. For very chatty agents, `metrics_enabled=false` disables.

**Storage growth:** table grows unbounded. Mitigation is deferred to P5+ (retention/trim policy). For now, operators can `DELETE FROM tool_metrics WHERE recorded_at < ...` manually.

**Rollback:** opt-out via env flag; revertible per commit; DDL is IF NOT EXISTS (safe on downgrade).

---

## 6. Success Criteria

- [ ] `test_metrics_service.py` — record + query cases pass.
- [ ] `test_call_tool_metrics.py` — instrumentation end-to-end verified.
- [ ] Full unit suite — 0 failures.
- [ ] `get_tool_metrics` tool registered and callable.
- [ ] `pyproject.toml` + README → 0.5.0.
- [ ] Commits pushed to `origin/main`.
