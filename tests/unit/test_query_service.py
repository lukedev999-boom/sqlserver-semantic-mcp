import pytest
from unittest.mock import patch, MagicMock
from sqlserver_semantic_mcp.config import reset_config
from sqlserver_semantic_mcp.services.query_service import QueryService
from sqlserver_semantic_mcp.services.policy_service import PolicyService


@pytest.fixture
def policy_svc(monkeypatch):
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_SERVER", "x")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_DATABASE", "x")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_USER", "u")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_PASSWORD", "p")
    reset_config()
    svc = PolicyService()
    svc.load()
    return svc


def test_validate_rejects_update(policy_svc):
    qs = QueryService(policy_svc)
    res = qs.validate("UPDATE T SET x=1 WHERE Id=1")
    assert res["allowed"] is False


def test_run_safe_query_blocks_when_disallowed(policy_svc):
    qs = QueryService(policy_svc)
    result = qs.run_safe_query("DROP TABLE X")
    assert result["executed"] is False
    assert result["error"]


@patch("sqlserver_semantic_mcp.services.query_service.open_connection")
def test_run_safe_query_executes_select(mock_open, policy_svc):
    conn = MagicMock()
    cursor = MagicMock()
    cursor.description = [("Id",), ("Name",)]
    cursor.fetchmany.return_value = [(1, "A"), (2, "B")]
    conn.cursor.return_value = cursor
    mock_open.return_value.__enter__.return_value = conn

    qs = QueryService(policy_svc)
    result = qs.run_safe_query("SELECT * FROM T")
    assert result["executed"] is True
    assert result["columns"] == ["Id", "Name"]
    assert result["rows"] == [[1, "A"], [2, "B"]]
    assert result["row_count"] == 2
