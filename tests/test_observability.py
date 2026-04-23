import json

import pytest
from mcp.server.fastmcp import FastMCP

from odoo_mcp.mcp.tools.hrm_toolset import register_hrm_tools
from odoo_mcp.server.audit import reset_audit_logger
from odoo_mcp.server.rate_limit import reset_rate_limiter


@pytest.mark.anyio
async def test_tool_calls_write_audit_log_and_enforce_rate_limit(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MCP_AUDIT_LOG_PATH", str(audit_path))
    monkeypatch.setenv("MCP_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("MCP_RATE_LIMIT_MAX_CALLS", "1")
    monkeypatch.setenv("MCP_RATE_LIMIT_WINDOW_SECONDS", "60")
    reset_audit_logger()
    reset_rate_limiter()

    class FakeOdoo:
        username = "alice"

        def execute_method(self, model, method, *args, **kwargs):
            return [{"id": 1, "name": "Alice"}]

    mcp = FastMCP("test")
    register_hrm_tools(mcp, resolve_odoo_client=lambda ctx: FakeOdoo())

    first = await mcp.call_tool(
        "odoo_execute_method",
        {
            "model": "res.partner",
            "method": "search_read",
            "args": [[["id", "=", 1]]],
        },
    )
    second = await mcp.call_tool(
        "odoo_execute_method",
        {
            "model": "res.partner",
            "method": "search_read",
            "args": [[["id", "=", 2]]],
        },
    )

    assert first.isError is False
    assert second.isError is True
    assert second.structuredContent["error_category"] == "rate_limit"
    assert second.structuredContent["rate_limit"]["retry_after_seconds"] >= 1

    lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert [line["status"] for line in lines] == ["success", "rate_limited"]
    assert all(line["user"] == "alice" for line in lines)
    assert all(line["surface"] == "tool" for line in lines)
    assert all(line["surface_name"] == "odoo_execute_method" for line in lines)
    assert lines[0]["model"] == "res.partner"
    assert lines[0]["method"] == "search_read"
