from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

from mcp.server.fastmcp import Context

from .audit import extract_export_metadata, get_audit_logger
from .errors import OdooRateLimitError, error_to_payload
from .rate_limit import get_rate_limiter


def execute_observed_call(
    ctx: Context | None,
    *,
    odoo_client: Any | None,
    surface: str,
    surface_name: str,
    model: str,
    method: str,
    operation: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Apply temporary rate limiting and emit one audit log per surface call."""
    user = resolve_call_user(ctx, odoo_client)
    started_at = datetime.now(timezone.utc)
    started_clock = perf_counter()
    rate_limit = get_rate_limiter().check(user=user, surface_name=surface_name)

    if not rate_limit.allowed:
        payload = error_to_payload(
            OdooRateLimitError(
                "Rate limit exceeded for this user. Retry the call after the cooldown window.",
                details={
                    "retry_after_seconds": rate_limit.retry_after_seconds,
                    "window_seconds": rate_limit.window_seconds,
                    "max_calls": rate_limit.max_calls,
                },
            ),
            model=model,
            method=method,
        )
        payload["rate_limit"] = _rate_limit_payload(rate_limit)
        _write_audit_event(
            surface=surface,
            surface_name=surface_name,
            user=user,
            model=model,
            method=method,
            started_at=started_at,
            duration_ms=(perf_counter() - started_clock) * 1000,
            result=payload,
            status="rate_limited",
        )
        return payload

    try:
        result = operation()
    except Exception as exc:
        result = error_to_payload(
            exc,
            model=model,
            method=method,
            operation=f"{surface} {surface_name}",
        )

    result.setdefault("model", model)
    result.setdefault("method", method)
    result.setdefault("rate_limit", _rate_limit_payload(rate_limit))

    _write_audit_event(
        surface=surface,
        surface_name=surface_name,
        user=user,
        model=model,
        method=method,
        started_at=started_at,
        duration_ms=(perf_counter() - started_clock) * 1000,
        result=result,
        status="success" if result.get("success") else "error",
    )
    return result


def resolve_call_user(ctx: Context | None, odoo_client: Any | None) -> str:
    if ctx is not None:
        try:
            request_context = ctx.request_context
        except ValueError:
            request_context = None
        request = getattr(request_context, "request", None)
        if request is not None:
            username = getattr(request.state, "odoo_username", None)
            if username:
                return str(username)

    client_username = getattr(odoo_client, "username", None)
    if client_username:
        return str(client_username)

    return "anonymous"


def _rate_limit_payload(rate_limit) -> dict[str, Any]:
    return {
        "max_calls": rate_limit.max_calls,
        "remaining": rate_limit.remaining,
        "window_seconds": rate_limit.window_seconds,
        "retry_after_seconds": rate_limit.retry_after_seconds,
        "reset_in_seconds": rate_limit.reset_in_seconds,
    }


def _write_audit_event(
    *,
    surface: str,
    surface_name: str,
    user: str,
    model: str,
    method: str,
    started_at: datetime,
    duration_ms: float,
    result: dict[str, Any],
    status: str,
) -> None:
    audit_event: dict[str, Any] = {
        "timestamp": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round(duration_ms, 3),
        "surface": surface,
        "surface_name": surface_name,
        "user": user,
        "model": model,
        "method": method,
        "status": status,
        "success": bool(result.get("success")),
    }

    error = result.get("error")
    if isinstance(error, str) and error:
        audit_event["error"] = error
    error_category = result.get("error_category")
    if isinstance(error_category, str) and error_category:
        audit_event["error_category"] = error_category
    retryable = result.get("retryable")
    if isinstance(retryable, bool):
        audit_event["retryable"] = retryable

    export = extract_export_metadata(result)
    if export:
        audit_event["export"] = export

    get_audit_logger().write_event(audit_event)
