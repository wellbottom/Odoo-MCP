from __future__ import annotations

import os
from typing import Callable

from mcp.server.fastmcp import FastMCP

from .hrm_toolset import register_hrm_tools

TOOLSET_ENV_VAR = "MCP_TOOLSETS"
AVAILABLE_TOOLSETS = ("hrm",)
DEFAULT_TOOLSETS = ("hrm",)


def get_enabled_toolsets(raw_value: str | None = None) -> tuple[str, ...]:
    """
    Resolve which tool groups should be exposed.

    The server currently exposes the payroll export workflow plus a generic
    Odoo method execution tool.
    """
    value = raw_value if raw_value is not None else os.environ.get(TOOLSET_ENV_VAR)
    if not value:
        return DEFAULT_TOOLSETS

    normalized = value.strip().lower()
    if normalized in {"*", "all"}:
        return AVAILABLE_TOOLSETS

    enabled: list[str] = []
    unknown: list[str] = []
    for part in value.split(","):
        name = part.strip().lower()
        if not name:
            continue
        if name not in AVAILABLE_TOOLSETS:
            unknown.append(name)
            continue
        if name not in enabled:
            enabled.append(name)

    if unknown:
        allowed = ", ".join(AVAILABLE_TOOLSETS)
        raise ValueError(
            f"Unknown MCP toolset(s): {', '.join(unknown)}. "
            f"Allowed values: {allowed}, all."
        )

    return tuple(enabled) if enabled else DEFAULT_TOOLSETS


def register_toolsets(
    mcp: FastMCP,
    *,
    resolve_odoo_client,
    enabled_toolsets: tuple[str, ...] | None = None,
) -> None:
    """Register the enabled MCP tool groups."""
    toolset_registrars: dict[str, Callable] = {
        "hrm": register_hrm_tools,
    }

    for toolset_name in enabled_toolsets or get_enabled_toolsets():
        toolset_registrars[toolset_name](
            mcp,
            resolve_odoo_client=resolve_odoo_client,
        )
