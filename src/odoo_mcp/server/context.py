from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Optional

from mcp.server.fastmcp import Context, FastMCP

from .auth import get_request_odoo_client
from .client import OdooClient


@dataclass
class AppContext:
    """Shared app state for FastMCP lifespan hooks."""

    default_odoo: Optional[OdooClient] = None


@asynccontextmanager
async def app_lifespan(_: FastMCP) -> AsyncIterator[AppContext]:
    """Create the shared app state used by FastMCP."""
    yield AppContext()


def resolve_odoo_client(ctx: Context) -> OdooClient:
    """Get the active Odoo client for the current MCP request."""
    return get_request_odoo_client(ctx)
