import pytest
from sqlserver_semantic_mcp.infrastructure.cache.store import init_store
from sqlserver_semantic_mcp.infrastructure.cache.structural import (
    write_structural_snapshot, StructuralSnapshot,
)
from sqlserver_semantic_mcp.services.semantic_service import (
    classify_table, analyze_columns, detect_lookup_tables,
)


async def _setup(tmp_path):
    db_path = str(tmp_path / "t.db")
    await init_store(db_path)
    snap = StructuralSnapshot(
        tables=[("dbo", "Users"), ("dbo", "OrderItems"),
                ("dbo", "StatusCode"), ("dbo", "AuditLog")],
        columns=[
            ("dbo", "OrderItems", "Id", "int", None, 0, None, 1),
            ("dbo", "OrderItems", "OrderId", "int", None, 0, None, 2),
            ("dbo", "OrderItems", "ProductId", "int", None, 0, None, 3),
            ("dbo", "OrderItems", "Quantity", "int", None, 0, None, 4),
            ("dbo", "StatusCode", "Code", "nvarchar", 10, 0, None, 1),
            ("dbo", "StatusCode", "Name", "nvarchar", 50, 0, None, 2),
            ("dbo", "AuditLog", "Id", "int", None, 0, None, 1),
            ("dbo", "AuditLog", "CreatedAt", "datetime", None, 0, None, 2),
            ("dbo", "AuditLog", "CreatedBy", "nvarchar", 100, 0, None, 3),
            ("dbo", "Users", "Id", "int", None, 0, None, 1),
            ("dbo", "Users", "Name", "nvarchar", 100, 0, None, 2),
            ("dbo", "Users", "Email", "nvarchar", 200, 0, None, 3),
        ],
        primary_keys=[
            ("dbo", "OrderItems", "Id"),
            ("dbo", "StatusCode", "Code"),
            ("dbo", "AuditLog", "Id"),
            ("dbo", "Users", "Id"),
        ],
        foreign_keys=[
            ("dbo", "OrderItems", "OrderId", "dbo", "Orders", "Id"),
            ("dbo", "OrderItems", "ProductId", "dbo", "Products", "Id"),
        ],
        indexes=[],
        objects=[],
        comments=[],
    )
    await write_structural_snapshot(db_path, "testdb", snap)
    return db_path


@pytest.mark.asyncio
async def test_classify_fact_table(tmp_path):
    db_path = await _setup(tmp_path)
    result = await classify_table(db_path, "testdb", "dbo", "OrderItems")
    assert result["type"] in ("fact", "bridge")
    assert result["confidence"] > 0


@pytest.mark.asyncio
async def test_classify_lookup(tmp_path):
    db_path = await _setup(tmp_path)
    r = await classify_table(db_path, "testdb", "dbo", "StatusCode")
    assert r["type"] == "lookup"


@pytest.mark.asyncio
async def test_classify_audit(tmp_path):
    db_path = await _setup(tmp_path)
    r = await classify_table(db_path, "testdb", "dbo", "AuditLog")
    assert r["type"] == "audit"


@pytest.mark.asyncio
async def test_analyze_columns(tmp_path):
    db_path = await _setup(tmp_path)
    cols = await analyze_columns(db_path, "testdb", "dbo", "AuditLog")
    created_at = next(c for c in cols if c["column"] == "CreatedAt")
    assert created_at["semantic_type"] == "audit_timestamp"
    created_by = next(c for c in cols if c["column"] == "CreatedBy")
    assert created_by["semantic_type"] == "audit_user"


@pytest.mark.asyncio
async def test_detect_lookup_tables(tmp_path):
    db_path = await _setup(tmp_path)
    lookups = await detect_lookup_tables(db_path, "testdb")
    names = [(l["schema_name"], l["table_name"]) for l in lookups]
    assert ("dbo", "StatusCode") in names
