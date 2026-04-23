"""Generic Odoo method execution helpers for MCP tools."""

from __future__ import annotations

import json
from typing import Any, Dict

from ...server.client import OdooClient
from ...server.errors import error_to_payload


def execute_method(
    odoo: OdooClient,
    model: str,
    method: str,
    *,
    args: list[Any] | None = None,
    kwargs: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Execute an arbitrary Odoo model method and return a JSON-safe payload."""
    normalized_model = model.strip()
    normalized_method = method.strip()
    if not normalized_model:
        return {"success": False, "error": "model must be a non-empty string."}
    if not normalized_method:
        return {"success": False, "error": "method must be a non-empty string."}

    call_args = list(args or [])
    call_kwargs = dict(kwargs or {})

    try:
        result = odoo.execute_method(
            normalized_model,
            normalized_method,
            *call_args,
            **call_kwargs,
        )
        return {
            "success": True,
            "model": normalized_model,
            "method": normalized_method,
            "args": _json_safe(call_args),
            "kwargs": _json_safe(call_kwargs),
            "result": _json_safe(result),
        }
    except Exception as exc:
        payload = error_to_payload(
            exc,
            model=normalized_model,
            method=normalized_method,
            operation=f"Odoo tool call {normalized_model}.{normalized_method}",
        )
        payload["args"] = _json_safe(call_args)
        payload["kwargs"] = _json_safe(call_kwargs)
        return payload


def _json_safe(value: Any) -> Any:
    """Convert XML-RPC results into JSON-safe Python objects."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))
