from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..mcp.tools.registry import AVAILABLE_TOOLSETS, TOOLSET_ENV_VAR, get_enabled_toolsets
from .audit import get_audit_log_path
from .rate_limit import get_rate_limit_config


def register_http_routes(mcp: FastMCP) -> None:
    """Register simple public HTTP endpoints used by health checks and inspectors."""

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_: Request) -> Response:
        return JSONResponse({"status": "ok"})

    @mcp.custom_route("/mcp/health", methods=["GET"])
    async def mcp_health(_: Request) -> Response:
        return JSONResponse({"status": "ok"})

    @mcp.custom_route("/mcp/config", methods=["GET"])
    async def mcp_config(_: Request) -> Response:
        rate_limit = get_rate_limit_config()
        return JSONResponse(
            {
                "name": mcp.name,
                "transport": "streamable-http",
                "endpoint": "/mcp",
                "auth": {
                    "type": "basic",
                    "header": "Authorization",
                },
                "toolsets": {
                    "enabled": list(get_enabled_toolsets()),
                    "available": list(AVAILABLE_TOOLSETS),
                    "env": TOOLSET_ENV_VAR,
                },
                "observability": {
                    "audit_log": {
                        "enabled": True,
                        "format": "jsonl",
                        "path": str(get_audit_log_path()),
                    },
                    "rate_limit": {
                        "enabled": rate_limit.enabled,
                        "max_calls": rate_limit.max_calls,
                        "window_seconds": rate_limit.window_seconds,
                    },
                },
            }
        )
