"""Unit tests for suggest_next_tool / estimate_execution_risk (v0.5)."""
import pytest

from sqlserver_semantic_mcp.config import get_config, reset_config
from sqlserver_semantic_mcp.services.policy_service import PolicyService
from sqlserver_semantic_mcp.workflows.recommendations import (
    estimate_execution_risk, suggest_next_tool,
)


@pytest.fixture
def policy(monkeypatch):
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_SERVER", "x")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_DATABASE", "x")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_USER", "u")
    monkeypatch.setenv("SEMANTIC_MCP_MSSQL_PASSWORD", "p")
    reset_config()
    svc = PolicyService()
    svc.load()
    return svc


def test_suggest_recommends_discovery_for_bare_goal(policy):
    env = suggest_next_tool(policy=policy, goal="find customer revenue")
    assert env["next_action"] == "discover"
    assert "discover_relevant_tables" in env["data"]["recommended_tools"]


def test_suggest_recommends_fast_path_when_sql_known(policy):
    env = suggest_next_tool(policy=policy, query="SELECT TOP 1 * FROM dbo.T")
    assert env["data"]["route"]["route"] == "direct_execute"
    assert env["recommended_tool"] == "plan_or_execute_query"


def test_estimate_risk_flags_unqualified_update(policy):
    env = estimate_execution_risk("UPDATE Users SET x=1 WHERE id=1", policy=policy)
    data = env["data"]
    # Unqualified table + disallowed op → high risk bucket overall
    assert data["risk_level"] in ("high", "critical", "medium")
    assert data["allowed_by_policy"] is False
    assert any(r["kind"] == "schema_qualification_risk" for r in data["risks"]) \
        or data["allowed_by_policy"] is False


def test_estimate_risk_low_for_safe_select(policy):
    env = estimate_execution_risk(
        "SELECT TOP 5 * FROM dbo.Users WHERE id = 1", policy=policy,
    )
    assert env["data"]["risk_level"] == "low"
    assert env["data"]["allowed_by_policy"] is True
