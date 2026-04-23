from starlette.testclient import TestClient

from odoo_mcp.server.http import create_app


def test_public_server_routes_work_without_auth(monkeypatch):
    monkeypatch.delenv("MCP_TOOLSETS", raising=False)

    app = create_app()

    with TestClient(app) as client:
        health = client.get("/healthz")
        mcp_health = client.get("/mcp/health")
        config = client.get("/mcp/config")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert mcp_health.status_code == 200
    assert mcp_health.json() == {"status": "ok"}
    assert config.status_code == 200
    assert config.json() == {
        "name": "Odoo MCP Server",
        "transport": "streamable-http",
        "endpoint": "/mcp",
        "auth": {
            "type": "basic",
            "header": "Authorization",
        },
        "toolsets": {
            "enabled": ["hrm"],
            "available": ["hrm"],
            "env": "MCP_TOOLSETS",
        },
        "observability": {
            "audit_log": {
                "enabled": True,
                "format": "jsonl",
                "path": "logs/odoo_audit.jsonl",
            },
            "rate_limit": {
                "enabled": True,
                "max_calls": 60,
                "window_seconds": 60,
            },
        },
    }
