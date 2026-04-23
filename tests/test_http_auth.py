import base64
from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from odoo_mcp.server.auth import (
    HTTPAuthError,
    OdooBasicAuthMiddleware,
    create_authenticated_http_app,
    get_request_odoo_client,
    parse_basic_auth_header,
)


def _basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def test_parse_basic_auth_header_returns_username_and_password():
    username, password = parse_basic_auth_header(_basic_auth("alice", "secret:with:colon"))
    assert username == "alice"
    assert password == "secret:with:colon"


def test_parse_basic_auth_header_rejects_missing_header():
    try:
        parse_basic_auth_header(None)
    except HTTPAuthError as exc:
        assert "Missing Authorization header" in str(exc)
    else:
        raise AssertionError("Expected HTTPAuthError")


def test_get_request_odoo_client_prefers_request_state():
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "state": {}})
    request.state.odoo_client = "request-client"

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            request=request,
            lifespan_context=SimpleNamespace(default_odoo="fallback-client"),
        )
    )

    assert get_request_odoo_client(ctx) == "request-client"


def test_odoo_basic_auth_middleware_rejects_missing_credentials():
    async def ok(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/mcp", ok)])
    app.add_middleware(OdooBasicAuthMiddleware)

    with TestClient(app) as client:
        response = client.get("/mcp")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="Odoo MCP"'


def test_odoo_basic_auth_middleware_attaches_authenticated_client(monkeypatch):
    class FakeOdooClient:
        uid = 73

    def fake_get_odoo_client(username, password, allow_config_fallback):
        assert username == "alice"
        assert password == "secret"
        assert allow_config_fallback is False
        client = FakeOdooClient()
        client.username = username
        return client

    async def whoami(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "username": request.state.odoo_username,
                "uid": request.state.odoo_uid,
                "client_username": request.state.odoo_client.username,
            }
        )

    monkeypatch.setattr("odoo_mcp.server.auth.get_odoo_client", fake_get_odoo_client)

    app = Starlette(routes=[Route("/mcp", whoami), Route("/healthz", whoami)])
    app.add_middleware(OdooBasicAuthMiddleware, excluded_paths={"/healthz"})

    with TestClient(app) as client:
        response = client.get("/mcp", headers={"Authorization": _basic_auth("alice", "secret")})

    assert response.status_code == 200
    assert response.json() == {
        "username": "alice",
        "uid": 73,
        "client_username": "alice",
    }


def test_odoo_basic_auth_middleware_skips_excluded_paths():
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app = Starlette(routes=[Route("/healthz", health)])
    app.add_middleware(OdooBasicAuthMiddleware, excluded_paths={"/healthz"})

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_odoo_basic_auth_middleware_skips_options_requests():
    async def preflight(_: Request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/mcp", preflight, methods=["OPTIONS"])])
    app.add_middleware(OdooBasicAuthMiddleware)

    with TestClient(app) as client:
        response = client.options("/mcp")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_create_authenticated_http_app_allows_inspector_cors(monkeypatch):
    class DummyMCP:
        def streamable_http_app(self):
            app = Starlette(routes=[Route("/mcp", lambda request: JSONResponse({"ok": True}), methods=["OPTIONS"])])
            return app

    app = create_authenticated_http_app(DummyMCP())

    with TestClient(app) as client:
        response = client.options(
            "/mcp",
            headers={
                "Origin": "http://localhost:6274",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:6274"


def test_create_authenticated_http_app_skips_auth_for_inspector_probe_paths():
    class DummyMCP:
        def streamable_http_app(self):
            return Starlette(
                routes=[
                    Route("/mcp/health", lambda request: JSONResponse({"status": "ok"}), methods=["GET"]),
                    Route("/mcp/config", lambda request: JSONResponse({"name": "dummy"}), methods=["GET"]),
                ]
            )

    app = create_authenticated_http_app(DummyMCP())

    with TestClient(app) as client:
        health = client.get("/mcp/health")
        config = client.get("/mcp/config")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert config.status_code == 200
    assert config.json() == {"name": "dummy"}
