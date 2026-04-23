from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette

from ..mcp.app import mcp
from .auth import create_authenticated_http_app


def create_app() -> Starlette:
    return create_authenticated_http_app(
        mcp,
        excluded_paths={"/healthz"},
    )


def _resolve_tls_file(env_name: str) -> str | None:
    raw_value = os.environ.get(env_name)
    if raw_value is None or not raw_value.strip():
        return None

    resolved_path = Path(raw_value).expanduser()
    if not resolved_path.is_file():
        raise FileNotFoundError(f"{env_name} points to a missing file: {resolved_path}")

    return str(resolved_path)


def get_uvicorn_run_kwargs() -> dict[str, Any]:
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "6969"))
    log_level = os.environ.get("MCP_LOG_LEVEL", "info").lower()

    run_kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "log_level": log_level,
    }

    ssl_certfile_raw = os.environ.get("MCP_SSL_CERTFILE")
    ssl_keyfile_raw = os.environ.get("MCP_SSL_KEYFILE")
    ssl_keyfile_password = os.environ.get("MCP_SSL_KEYFILE_PASSWORD")
    https_requested = any(
        value is not None and value.strip()
        for value in (ssl_certfile_raw, ssl_keyfile_raw, ssl_keyfile_password)
    )

    if https_requested:
        if not ssl_certfile_raw or not ssl_certfile_raw.strip():
            raise ValueError(
                "MCP_SSL_CERTFILE and MCP_SSL_KEYFILE must both be set to enable "
                "native HTTPS on the MCP server."
            )
        if not ssl_keyfile_raw or not ssl_keyfile_raw.strip():
            raise ValueError(
                "MCP_SSL_CERTFILE and MCP_SSL_KEYFILE must both be set to enable "
                "native HTTPS on the MCP server."
            )

        run_kwargs["ssl_certfile"] = _resolve_tls_file("MCP_SSL_CERTFILE")
        run_kwargs["ssl_keyfile"] = _resolve_tls_file("MCP_SSL_KEYFILE")
        if ssl_keyfile_password and ssl_keyfile_password.strip():
            run_kwargs["ssl_keyfile_password"] = ssl_keyfile_password

    return run_kwargs


def run_http_server(*, run_kwargs: dict[str, Any] | None = None) -> None:
    resolved_run_kwargs = get_uvicorn_run_kwargs() if run_kwargs is None else dict(run_kwargs)

    uvicorn.run(
        create_app(),
        **resolved_run_kwargs,
    )
