from __future__ import annotations

import base64
import binascii
from collections.abc import Iterable
from http import HTTPStatus

from mcp.server.fastmcp import Context, FastMCP
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .client import OdooClient, get_odoo_client
from .errors import OdooAuthenticationError, OdooConfigurationError, OdooError


class HTTPAuthError(ValueError):
    """Raised when an incoming HTTP request is missing valid credentials."""


def parse_basic_auth_header(authorization: str | None) -> tuple[str, str]:
    """Parse an HTTP Basic Auth header into username and password."""
    if not authorization:
        raise HTTPAuthError("Missing Authorization header.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "basic" or not token:
        raise HTTPAuthError("Expected HTTP Basic authentication.")

    try:
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise HTTPAuthError("Invalid Basic Auth encoding.") from exc

    username, separator, password = decoded.partition(":")
    if not separator or not username or not password:
        raise HTTPAuthError("Basic Auth credentials must include username and password.")

    return username, password


def _json_error(
    status_code: int,
    message: str,
    *,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {"success": False, "error": message},
        status_code=status_code,
        headers=headers,
    )


class OdooBasicAuthMiddleware:
    """ASGI middleware that authenticates each HTTP request against Odoo."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        excluded_paths: Iterable[str] = (),
    ) -> None:
        self.app = app
        self.excluded_paths = set(excluded_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("method") == "OPTIONS" or scope.get("path") in self.excluded_paths:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)

        try:
            username, password = parse_basic_auth_header(headers.get("authorization"))
            odoo_client = get_odoo_client(
                username=username,
                password=password,
                allow_config_fallback=False,
            )
        except HTTPAuthError as exc:
            response = _json_error(
                HTTPStatus.UNAUTHORIZED,
                str(exc),
                headers={"WWW-Authenticate": 'Basic realm="Odoo MCP"'},
            )
            await response(scope, receive, send)
            return
        except OdooAuthenticationError as exc:
            response = _json_error(
                HTTPStatus.UNAUTHORIZED,
                exc.message,
                headers={"WWW-Authenticate": 'Basic realm="Odoo MCP"'},
            )
            await response(scope, receive, send)
            return
        except OdooConfigurationError as exc:
            response = _json_error(HTTPStatus.INTERNAL_SERVER_ERROR, exc.message)
            await response(scope, receive, send)
            return
        except OdooError as exc:
            headers = (
                {"WWW-Authenticate": 'Basic realm="Odoo MCP"'}
                if exc.status_code == HTTPStatus.UNAUTHORIZED
                else None
            )
            response = _json_error(exc.status_code, exc.message, headers=headers)
            await response(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state["odoo_client"] = odoo_client
        state["odoo_username"] = username
        state["odoo_uid"] = odoo_client.uid

        await self.app(scope, receive, send)


def get_request_odoo_client(ctx: Context) -> OdooClient:
    """Resolve the active Odoo client for the current request."""
    request = ctx.request_context.request
    if request is not None:
        request_client = getattr(request.state, "odoo_client", None)
        if request_client is not None:
            return request_client

    fallback_client = getattr(ctx.request_context.lifespan_context, "default_odoo", None)
    if fallback_client is not None:
        return fallback_client

    raise RuntimeError(
        "No authenticated Odoo client is available. HTTP clients must send "
        "Basic Auth credentials; stdio/local mode requires fixed credentials in config."
    )


def create_authenticated_http_app(
    mcp: FastMCP,
    *,
    excluded_paths: Iterable[str] = (),
) -> Starlette:
    """Create the Streamable HTTP app with per-request Odoo authentication."""
    app = mcp.streamable_http_app()
    public_paths = {
        "/healthz",
        "/mcp/health",
        "/mcp/config",
        *tuple(excluded_paths),
    }
    app.add_middleware(OdooBasicAuthMiddleware, excluded_paths=tuple(public_paths))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:6274",
            "http://127.0.0.1:6274",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
