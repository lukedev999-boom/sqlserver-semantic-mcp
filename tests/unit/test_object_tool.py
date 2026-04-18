import hashlib

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

    # P1 brief contract: definition and definition_hash stripped; only bytes kept.
    assert "definition" not in result
    assert "definition_hash" not in result
    assert result["definition_bytes"] == len(b"CREATE VIEW vw_x AS SELECT 1")
    assert result["object"] == "dbo.vw_x"
    assert result["type"] == "VIEW"


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

    # include_definition on brief adds definition + hash; bytes always present.
    assert result["definition"] == "CREATE VIEW vw_x AS SELECT 1"
    assert len(result["definition_hash"]) == 8
    assert result["definition_bytes"] == len(b"CREATE VIEW vw_x AS SELECT 1")


@pytest.mark.asyncio
async def test_describe_view_detail_full_includes_definition(env):
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
            {"schema": "dbo", "name": "vw_x", "detail": "full"}
        )

    # detail=full always yields full shape (definition + hash + bytes).
    assert result["definition"] == "CREATE VIEW vw_x AS SELECT 1"
    assert len(result["definition_hash"]) == 8
    assert result["affected_tables"] == []


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
    assert "definition_hash" not in result  # P1 brief drops hash
    assert result["definition_bytes"] == len(b"CREATE PROCEDURE usp_x AS SELECT 1")


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
