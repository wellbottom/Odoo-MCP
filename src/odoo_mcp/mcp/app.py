"""Build the Odoo MCP server from small, obvious pieces."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..server.context import app_lifespan, resolve_odoo_client
from ..server.routes import register_http_routes
from .resources.odoo import register_resources
from .tools.registry import register_toolsets


def create_mcp_server() -> FastMCP:
    """Create and wire the Odoo FastMCP server."""
    mcp = FastMCP(
        "Odoo MCP Server",
        dependencies=["requests"],
        lifespan=app_lifespan,
        streamable_http_path="/mcp",
        stateless_http=True,
    )
    register_http_routes(mcp)
    register_resources(mcp, resolve_odoo_client=resolve_odoo_client)
    register_toolsets(mcp, resolve_odoo_client=resolve_odoo_client)
    return mcp


mcp = create_mcp_server()
