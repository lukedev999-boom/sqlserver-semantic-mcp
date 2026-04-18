# P0 Token Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce default MCP tool response payload size by ≥40% and collapse `list_resources` to constant size, without changing tool semantics.

**Architecture:** A single transport-layer `compact()` helper applies pretty-print removal, null/empty stripping, and identifier merging at the `_call_tool` boundary. `list_resources` switches from per-table enumeration to 2 concrete resources + 2 `ResourceTemplate`s. `describe_view`/`describe_procedure` gain an `include_definition=false` default that returns `definition_hash` + `definition_bytes`.

**Tech Stack:** Python 3.11+, mcp SDK (`mcp.server.Server`, `mcp.types.ResourceTemplate`), pytest, pytest-asyncio.

**Spec reference:** `docs/superpowers/specs/2026-04-19-p0-token-optimization-design.md`

---

## Task 1: Build `compact()` helper with TDD

**Files:**
- Create: `sqlserver_semantic_mcp/server/compact.py`
- Create: `tests/unit/test_compact.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/unit/test_compact.py`:

```python
import json

from sqlserver_semantic_mcp.server.compact import compact


def test_r1_drops_none_empty_false():
    assert compact({"a": 1, "b": None, "c": [], "d": {}, "e": False}) == {"a": 1}


def test_r1_keeps_zero_and_empty_string():
    assert compact({"count": 0, "label": ""}) == {"count": 0, "label": ""}


def test_r1_whitelist_preserves_is_nullable_false():
    assert compact({"is_nullable": False, "default_value": False}) == {"is_nullable": False}


def test_r2_merges_schema_and_table():
    assert compact({"schema_name": "dbo", "table_name": "Users", "type": "USER_TABLE"}) == {
        "table": "dbo.Users", "type": "USER_TABLE",
    }


def test_r3_merges_schema_and_object():
    assert compact({"schema": "dbo", "object_name": "vw_x", "object_type": "VIEW", "depends_on": []}) == {
        "object": "dbo.vw_x", "type": "VIEW",
    }


def test_r2_guard_skips_when_empty():
    assert compact({"schema_name": "dbo", "table_name": "", "other": 1}) == {
        "schema_name": "dbo", "other": 1,
    }


def test_r2_guard_skips_when_none():
    assert compact({"schema_name": "dbo", "table_name": None, "other": 1}) == {
        "schema_name": "dbo", "other": 1,
    }


def test_recursion_into_lists_of_dicts():
    got = compact([
        {"schema_name": "dbo", "table_name": "A", "description": None},
        {"schema_name": "dbo", "table_name": "B", "description": "x"},
    ])
    assert got == [
        {"table": "dbo.A"},
        {"table": "dbo.B", "description": "x"},
    ]


def test_recursion_into_nested_dicts():
    got = compact({
        "outer": {"schema_name": "dbo", "table_name": "X", "columns": [
            {"name": "Id", "is_nullable": False, "description": None},
        ]},
    })
    assert got == {
        "outer": {"table": "dbo.X", "columns": [
            {"name": "Id", "is_nullable": False},
        ]},
    }


def test_key_order_preserved_on_merge():
    out = compact({"schema_name": "dbo", "table_name": "Users", "type": "USER_TABLE"})
    assert list(out.keys()) == ["table", "type"]


def test_golden_size_describe_table_reduces_at_least_30pct():
    before = {
        "schema_name": "dbo",
        "table_name": "Users",
        "type": "USER_TABLE",
        "description": None,
        "columns": [
            {"column_name": "Id", "data_type": "int", "is_nullable": False,
             "default_value": None, "description": None},
            {"column_name": "Email", "data_type": "nvarchar(255)", "is_nullable": False,
             "default_value": None, "description": "login email"},
        ],
        "primary_keys": ["Id"],
        "foreign_keys": [],
        "indexes": [],
    }
    before_bytes = len(json.dumps(before, indent=2))
    after_bytes = len(json.dumps(compact(before), separators=(",", ":")))
    assert after_bytes < 0.7 * before_bytes, (
        f"expected ≥30% reduction; got before={before_bytes} after={after_bytes}"
    )
```

- [ ] **Step 1.2: Run the tests and verify they fail**

Run:
```bash
cd "P:/pCloud Backup/cl3Luke的MacBookAir/pCloud/sqlserver-semantic-mcp"
pytest tests/unit/test_compact.py -v
```

Expected: ImportError on `sqlserver_semantic_mcp.server.compact` — all tests fail.

- [ ] **Step 1.3: Implement `compact.py`**

Create `sqlserver_semantic_mcp/server/compact.py`:

```python
"""Transport-layer response shaping helper.

See docs/superpowers/specs/2026-04-19-p0-token-optimization-design.md for rules.
"""
from typing import Any

NULLABLE_FALSE_KEEP: frozenset[str] = frozenset({"is_nullable"})


def _is_falsy_strippable(value: Any) -> bool:
    return value is None or value == [] or value == {} or value is False


def _merge_table_id(d: dict) -> dict:
    schema = d.get("schema_name")
    table = d.get("table_name")
    if not (isinstance(schema, str) and isinstance(table, str) and schema and table):
        return d
    out: dict[str, Any] = {}
    merged = False
    for k, v in d.items():
        if k == "schema_name":
            if not merged:
                out["table"] = f"{schema}.{table}"
                merged = True
        elif k == "table_name":
            continue
        else:
            out[k] = v
    return out


def _merge_object_id(d: dict) -> dict:
    schema = d.get("schema")
    name = d.get("object_name")
    if not (isinstance(schema, str) and isinstance(name, str) and schema and name):
        return d
    out: dict[str, Any] = {}
    merged = False
    for k, v in d.items():
        if k == "schema":
            if not merged:
                out["object"] = f"{schema}.{name}"
                merged = True
        elif k == "object_name":
            continue
        elif k == "object_type":
            out["type"] = v
        else:
            out[k] = v
    return out


def compact(obj: Any) -> Any:
    """Recursively strip falsy values and merge identifier pairs.

    Application order within a dict: R2 (table merge) → R3 (object merge) → R1 (strip).
    """
    if isinstance(obj, dict):
        merged = _merge_table_id(obj)
        merged = _merge_object_id(merged)
        out: dict[str, Any] = {}
        for k, v in merged.items():
            v = compact(v)
            if k in NULLABLE_FALSE_KEEP and v is False:
                out[k] = v
                continue
            if _is_falsy_strippable(v):
                continue
            out[k] = v
        return out
    if isinstance(obj, list):
        return [compact(x) for x in obj]
    return obj
```

- [ ] **Step 1.4: Run tests and verify they pass**

Run:
```bash
pytest tests/unit/test_compact.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 1.5: Commit**

```bash
git add sqlserver_semantic_mcp/server/compact.py tests/unit/test_compact.py
git commit -m "feat(compact): transport-layer response shaper (R1-R3 + guards)"
```

---

## Task 2: Wire `compact()` into `_call_tool` and drop `indent=2`

**Files:**
- Modify: `sqlserver_semantic_mcp/server/app.py:52-66`

- [ ] **Step 2.1: Inspect current `_call_tool`**

Current code at `sqlserver_semantic_mcp/server/app.py:52-66` is:

```python
@app.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name not in _TOOL_REGISTRY:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    _t, handler = _TOOL_REGISTRY[name]
    try:
        result = await handler(arguments or {})
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2, default=str),
        )]
    except Exception as e:
        logger.exception("Tool %s raised", name)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
```

- [ ] **Step 2.2: Edit the import block and the serializer call**

At the top of `sqlserver_semantic_mcp/server/app.py`, add the import (after existing imports, before the `app = Server(...)` line — find the existing `from` imports and append):

```python
from .compact import compact
```

Then replace the success branch of `_call_tool`. The exact `old_string` to replace:

```python
        result = await handler(arguments or {})
        return [TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, indent=2, default=str),
        )]
```

With:

```python
        result = await handler(arguments or {})
        return [TextContent(
            type="text",
            text=json.dumps(
                compact(result),
                ensure_ascii=False,
                default=str,
                separators=(",", ":"),
            ),
        )]
```

The error branch is left untouched — debugging info should not be stripped.

- [ ] **Step 2.3: Run server-wiring test to verify no import break**

Run:
```bash
pytest tests/unit/test_server_wiring.py -v
```

Expected: PASS (registration test is import/registry-only, unaffected by wiring).

- [ ] **Step 2.4: Commit**

```bash
git add sqlserver_semantic_mcp/server/app.py
git commit -m "feat(server): apply compact() and drop indent=2 in _call_tool"
```

---

## Task 3: Collapse `list_resources` to ResourceTemplate

**Files:**
- Modify: `sqlserver_semantic_mcp/server/resources/schema.py:1-31`
- Test: `tests/unit/test_list_resources.py` (new)

- [ ] **Step 3.1: Write failing test**

Create `tests/unit/test_list_resources.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_list_resources_is_constant_size(monkeypatch, tmp_path):
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_SERVER", "x")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_DATABASE", "testdb")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_USER", "u")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_PASSWORD", "p")
    monkeypatch.setenv("SEMANTIC_MCP_CACHE_PATH", str(tmp_path / "t.db"))
    from sqlserver_semantic_mcp.config import reset_config
    reset_config()

    # Import triggers decorator registration.
    import sqlserver_semantic_mcp.server.resources.schema as mod

    # list_tables is NOT called by the new list_resources; stub defensively anyway.
    with patch("sqlserver_semantic_mcp.services.metadata_service.list_tables",
               new=AsyncMock(return_value=[])):
        resources = await mod.list_resources()

    assert len(resources) == 2
    uris = [str(r.uri) for r in resources]
    assert "semantic://schema/tables" in uris
    assert "semantic://summary/database" in uris


@pytest.mark.asyncio
async def test_list_resource_templates_returns_two_patterns(monkeypatch, tmp_path):
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_SERVER", "x")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_DATABASE", "testdb")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_USER", "u")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_PASSWORD", "p")
    monkeypatch.setenv("SEMANTIC_MCP_CACHE_PATH", str(tmp_path / "t.db"))
    from sqlserver_semantic_mcp.config import reset_config
    reset_config()

    import sqlserver_semantic_mcp.server.resources.schema as mod
    templates = await mod.list_resource_templates()

    assert len(templates) == 2
    patterns = [t.uriTemplate for t in templates]
    assert "semantic://schema/tables/{qualified}" in patterns
    assert "semantic://analysis/classification/{qualified}" in patterns
```

- [ ] **Step 3.2: Run and verify failure**

Run:
```bash
pytest tests/unit/test_list_resources.py -v
```

Expected: first test fails (returns >2 resources because current code loops over tables); second test fails (`list_resource_templates` attribute does not exist).

- [ ] **Step 3.3: Rewrite `schema.py` `list_resources` and add `list_resource_templates`**

Replace the entire `sqlserver_semantic_mcp/server/resources/schema.py` file with:

```python
import json
from mcp.types import Resource, ResourceTemplate
from pydantic import AnyUrl

from ...services import metadata_service, semantic_service, object_service
from ..app import app, get_context


@app.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri=AnyUrl("semantic://schema/tables"),
            name="All tables", mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("semantic://summary/database"),
            name="Database summary", mimeType="application/json",
        ),
    ]


@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            uriTemplate="semantic://schema/tables/{qualified}",
            name="Table metadata", mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="semantic://analysis/classification/{qualified}",
            name="Table classification", mimeType="application/json",
        ),
    ]


@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    ctx = get_context()
    cp = ctx.cfg.cache_path
    db = ctx.cfg.mssql_database
    s = str(uri)

    if s == "semantic://schema/tables":
        return json.dumps(await metadata_service.list_tables(cp, db), default=str)

    if s == "semantic://summary/database":
        return json.dumps(
            await metadata_service.database_summary(cp, db), default=str,
        )

    def _split_qualified(qualified: str, uri: str) -> tuple[str, str]:
        parts = qualified.split(".", 1)
        if len(parts) != 2:
            raise ValueError(f"invalid qualified name in URI: {uri}")
        return parts[0], parts[1]

    PREFIX_TABLE = "semantic://schema/tables/"
    PREFIX_CLASS = "semantic://analysis/classification/"

    if s.startswith(PREFIX_TABLE):
        schema, table = _split_qualified(s[len(PREFIX_TABLE):], s)
        data = await metadata_service.describe_table(cp, db, schema, table)
        return json.dumps(data, default=str)

    if s.startswith(PREFIX_CLASS):
        schema, table = _split_qualified(s[len(PREFIX_CLASS):], s)
        data = await semantic_service.classify(cp, db, schema, table)
        return json.dumps(data, default=str)

    raise ValueError(f"unknown resource URI: {uri}")
```

**Note:** preserve all existing `read_resource` paths (table metadata + classification). If the file has additional paths like dependency URIs, keep them. Verify against the current file before applying — if the current `read_resource` contains paths not listed above, copy them into the new version unchanged.

- [ ] **Step 3.4: Run the test and verify pass**

Run:
```bash
pytest tests/unit/test_list_resources.py -v
```

Expected: both tests PASS.

- [ ] **Step 3.5: Run the existing resource-related tests to catch regressions**

Run:
```bash
pytest tests/unit/ -v -k "resource or schema"
```

Expected: PASS. If any fail due to `read_resource` missing a prior URI path, add it back.

- [ ] **Step 3.6: Commit**

```bash
git add sqlserver_semantic_mcp/server/resources/schema.py tests/unit/test_list_resources.py
git commit -m "feat(resources): constant-size list + ResourceTemplates"
```

---

## Task 4: `include_definition` opt-in for `describe_view` / `describe_procedure`

**Files:**
- Modify: `sqlserver_semantic_mcp/server/tools/object_tool.py`
- Create: `tests/unit/test_object_tool.py`

- [ ] **Step 4.1: Write failing test**

Create `tests/unit/test_object_tool.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_SERVER", "x")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_DATABASE", "testdb")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_USER", "u")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_PASSWORD", "p")
    monkeypatch.setenv("SEMANTIC_MCP_CACHE_PATH", str(tmp_path / "t.db"))
    from sqlserver_semantic_mcp.config import reset_config
    reset_config()


@pytest.mark.asyncio
async def test_describe_view_default_strips_definition(env):
    from sqlserver_semantic_mcp.server.tools import object_tool

    fake = {
        "schema": "dbo", "object_name": "vw_x", "object_type": "VIEW",
        "definition": "CREATE VIEW vw_x AS SELECT 1",
        "dependencies": ["dbo.Users"],
        "status": "ready",
    }
    with patch.object(object_tool.object_service, "describe_object",
                      new=AsyncMock(return_value=fake)):
        result = await object_tool._describe_view({"schema": "dbo", "name": "vw_x"})

    import hashlib
    expected_hash = hashlib.sha1(b"CREATE VIEW vw_x AS SELECT 1").hexdigest()[:8]

    assert "definition" not in result
    assert result["definition_hash"] == expected_hash
    assert result["definition_bytes"] == len(b"CREATE VIEW vw_x AS SELECT 1")


@pytest.mark.asyncio
async def test_describe_view_include_definition_returns_full(env):
    from sqlserver_semantic_mcp.server.tools import object_tool

    fake = {
        "schema": "dbo", "object_name": "vw_x", "object_type": "VIEW",
        "definition": "CREATE VIEW vw_x AS SELECT 1",
        "dependencies": [],
        "status": "ready",
    }
    with patch.object(object_tool.object_service, "describe_object",
                      new=AsyncMock(return_value=fake)):
        result = await object_tool._describe_view(
            {"schema": "dbo", "name": "vw_x", "include_definition": True}
        )

    assert result["definition"] == "CREATE VIEW vw_x AS SELECT 1"
    assert len(result["definition_hash"]) == 8
    assert result["definition_bytes"] == len("CREATE VIEW vw_x AS SELECT 1".encode())


@pytest.mark.asyncio
async def test_describe_procedure_default_strips_definition(env):
    from sqlserver_semantic_mcp.server.tools import object_tool

    fake = {
        "schema": "dbo", "object_name": "usp_x", "object_type": "PROCEDURE",
        "definition": "CREATE PROCEDURE usp_x AS SELECT 1",
        "dependencies": [],
        "status": "ready",
    }
    with patch.object(object_tool.object_service, "describe_object",
                      new=AsyncMock(return_value=fake)):
        result = await object_tool._describe_procedure({"schema": "dbo", "name": "usp_x"})

    assert "definition" not in result
    assert len(result["definition_hash"]) == 8


@pytest.mark.asyncio
async def test_handles_missing_definition(env):
    """When the object service returns an error/pending state with no definition."""
    from sqlserver_semantic_mcp.server.tools import object_tool

    fake = {"status": "error", "error_message": "not found"}
    with patch.object(object_tool.object_service, "describe_object",
                      new=AsyncMock(return_value=fake)):
        result = await object_tool._describe_view({"schema": "dbo", "name": "missing"})

    assert result["status"] == "error"
    assert "definition_hash" not in result
```

- [ ] **Step 4.2: Run and verify failure**

Run:
```bash
pytest tests/unit/test_object_tool.py -v
```

Expected: all 4 tests FAIL (current `_describe_view` returns the full object including `definition`).

- [ ] **Step 4.3: Rewrite `object_tool.py`**

Replace the full contents of `sqlserver_semantic_mcp/server/tools/object_tool.py` with:

```python
import hashlib
from typing import Any

from mcp.types import Tool

from ...services import object_service
from ..app import get_context, register_tool


_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "schema":             {"type": "string"},
        "name":               {"type": "string"},
        "include_definition": {"type": "boolean", "default": False},
    },
    "required": ["schema", "name"],
}


def register() -> None:
    register_tool(
        Tool(
            name="describe_view",
            description=(
                "Return view metadata + dependencies. By default the full SQL "
                "definition is stripped and replaced with definition_hash + "
                "definition_bytes. Pass include_definition=true to get the full text."
            ),
            inputSchema=_INPUT_SCHEMA,
        ),
        _describe_view,
    )
    register_tool(
        Tool(
            name="describe_procedure",
            description=(
                "Return procedure metadata + dependencies. By default the full SQL "
                "definition is stripped and replaced with definition_hash + "
                "definition_bytes. Pass include_definition=true to get the full text."
            ),
            inputSchema=_INPUT_SCHEMA,
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


def _apply_definition_policy(obj: dict, include_definition: bool) -> dict:
    """Strip definition by default; always add hash + byte length when definition exists."""
    definition = obj.get("definition")
    if not isinstance(definition, str) or not definition:
        return obj

    encoded = definition.encode("utf-8")
    digest = hashlib.sha1(encoded).hexdigest()[:8]
    out: dict[str, Any] = {}
    for k, v in obj.items():
        if k == "definition":
            if include_definition:
                out[k] = v
            continue
        out[k] = v
    out["definition_hash"] = digest
    out["definition_bytes"] = len(encoded)
    return out


async def _describe_view(args: dict) -> dict:
    ctx = get_context()
    include = bool(args.get("include_definition", False))
    obj = await object_service.describe_object(
        args["schema"], args["name"], "VIEW", ctx.cfg,
    )
    return _apply_definition_policy(obj, include)


async def _describe_procedure(args: dict) -> dict:
    ctx = get_context()
    include = bool(args.get("include_definition", False))
    obj = await object_service.describe_object(
        args["schema"], args["name"], "PROCEDURE", ctx.cfg,
    )
    return _apply_definition_policy(obj, include)


async def _trace(args: dict) -> list[str]:
    ctx = get_context()
    return await object_service.trace_dependencies(
        args["schema"], args["name"], args["type"], ctx.cfg,
    )
```

- [ ] **Step 4.4: Run and verify pass**

Run:
```bash
pytest tests/unit/test_object_tool.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 4.5: Commit**

```bash
git add sqlserver_semantic_mcp/server/tools/object_tool.py tests/unit/test_object_tool.py
git commit -m "feat(object_tool): add include_definition opt-in; default strips SQL text"
```

---

## Task 5: Full regression suite

- [ ] **Step 5.1: Run the whole unit test suite**

Run:
```bash
pytest tests/unit -v
```

Expected: all existing tests pass. Some pre-existing tests may hit assertion mismatches if they inspect raw tool outputs with old field names — these must be updated.

- [ ] **Step 5.2: Fix any broken tests**

For each failure, decide:
- **Old-shape assertion that is now contractually wrong** (e.g., `assert "schema_name" in resp`) → update to `assert "table" in resp`
- **Genuine regression** (e.g., `describe_object` no longer returning `dependencies`) → this is a bug; go back and fix the implementation

Document each update in the commit message.

- [ ] **Step 5.3: Re-run full suite**

Run:
```bash
pytest tests/unit -v
```

Expected: 0 failures.

- [ ] **Step 5.4: Commit any test fixes**

```bash
git add tests/
git commit -m "test: update shape assertions for P0 compact responses"
```

(Skip if no test changes were needed.)

---

## Task 6: Version bump, README badges, push

**Files:**
- Modify: `pyproject.toml:3`
- Modify: `README.md` (badge row)
- Modify: `README.zh-TW.md` (badge row)

- [ ] **Step 6.1: Bump pyproject.toml version**

In `pyproject.toml`, change:
```toml
version = "0.1.0"
```
to:
```toml
version = "0.2.0"
```

- [ ] **Step 6.2: Update version badge in both READMEs**

In `README.md` and `README.zh-TW.md`, change:
```markdown
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](pyproject.toml)
```
to:
```markdown
[![Version](https://img.shields.io/badge/version-0.2.0-green.svg)](pyproject.toml)
```

- [ ] **Step 6.3: Commit version bump**

```bash
git add pyproject.toml README.md README.zh-TW.md
git commit -m "chore: bump to v0.2.0 (P0 token optimization)"
```

- [ ] **Step 6.4: Push to GitHub**

```bash
git push origin main
```

Expected: push succeeds, all P0 commits land on `origin/main`.

- [ ] **Step 6.5: Verify remote state**

Run:
```bash
git log --oneline origin/main | head -10
```

Expected: commits ordered newest-first include the version bump, test fixes (if any), object_tool, resources, compact wiring, compact helper.

---

## Success Criteria (maps to spec §7)

- [x] `test_compact.py` passes (all R1–R3 + guards + recursion + golden size).
- [x] `test_list_resources.py` confirms constant-size listing and 2 templates.
- [x] `test_object_tool.py` confirms default strips definition, opt-in returns it.
- [x] Full unit suite passes.
- [x] Version 0.2.0 in `pyproject.toml` and both README badges.
- [x] All commits pushed to `origin/main`.
