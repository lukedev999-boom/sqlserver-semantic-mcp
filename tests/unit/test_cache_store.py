import pytest
import aiosqlite
from sqlserver_semantic_mcp.infrastructure.cache.store import (
    init_store, SCHEMA_TABLES,
)


@pytest.mark.asyncio
async def test_init_store_creates_all_tables(tmp_path):
    db_path = tmp_path / "test.db"
    await init_store(str(db_path))
    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        names = {row[0] for row in await cursor.fetchall()}
    for table in SCHEMA_TABLES:
        assert table in names, f"missing table: {table}"


@pytest.mark.asyncio
async def test_init_store_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    await init_store(str(db_path))
    await init_store(str(db_path))  # must not error
