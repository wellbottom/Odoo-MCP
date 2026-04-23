import pytest

from odoo_mcp.server.http import get_uvicorn_run_kwargs, run_http_server


def _clear_server_env(monkeypatch) -> None:
    for env_name in (
        "MCP_HOST",
        "MCP_PORT",
        "MCP_LOG_LEVEL",
        "MCP_SSL_CERTFILE",
        "MCP_SSL_KEYFILE",
        "MCP_SSL_KEYFILE_PASSWORD",
    ):
        monkeypatch.delenv(env_name, raising=False)


def test_get_uvicorn_run_kwargs_defaults_to_plain_http(monkeypatch):
    _clear_server_env(monkeypatch)

    assert get_uvicorn_run_kwargs() == {
        "host": "0.0.0.0",
        "port": 6969,
        "log_level": "info",
    }


def test_get_uvicorn_run_kwargs_adds_ssl_settings_when_configured(tmp_path, monkeypatch):
    _clear_server_env(monkeypatch)

    cert_path = tmp_path / "server.crt"
    key_path = tmp_path / "server.key"
    cert_path.write_text("cert", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")

    monkeypatch.setenv("MCP_SSL_CERTFILE", str(cert_path))
    monkeypatch.setenv("MCP_SSL_KEYFILE", str(key_path))
    monkeypatch.setenv("MCP_SSL_KEYFILE_PASSWORD", "secret")

    assert get_uvicorn_run_kwargs() == {
        "host": "0.0.0.0",
        "port": 6969,
        "log_level": "info",
        "ssl_certfile": str(cert_path),
        "ssl_keyfile": str(key_path),
        "ssl_keyfile_password": "secret",
    }


def test_get_uvicorn_run_kwargs_rejects_partial_ssl_configuration(monkeypatch):
    _clear_server_env(monkeypatch)
    monkeypatch.setenv("MCP_SSL_CERTFILE", "/tmp/server.crt")

    with pytest.raises(ValueError, match="MCP_SSL_CERTFILE and MCP_SSL_KEYFILE"):
        get_uvicorn_run_kwargs()


def test_run_http_server_passes_resolved_ssl_settings_to_uvicorn(tmp_path, monkeypatch):
    _clear_server_env(monkeypatch)

    cert_path = tmp_path / "server.crt"
    key_path = tmp_path / "server.key"
    cert_path.write_text("cert", encoding="utf-8")
    key_path.write_text("key", encoding="utf-8")

    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "7443")
    monkeypatch.setenv("MCP_LOG_LEVEL", "debug")
    monkeypatch.setenv("MCP_SSL_CERTFILE", str(cert_path))
    monkeypatch.setenv("MCP_SSL_KEYFILE", str(key_path))

    captured: dict[str, object] = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr("odoo_mcp.server.http.uvicorn.run", fake_run)

    run_http_server()

    kwargs = captured["kwargs"]
    assert kwargs == {
        "host": "127.0.0.1",
        "port": 7443,
        "log_level": "debug",
        "ssl_certfile": str(cert_path),
        "ssl_keyfile": str(key_path),
    }
    assert captured["app"] is not None


def test_get_uvicorn_run_kwargs_rejects_missing_ssl_files(tmp_path, monkeypatch):
    _clear_server_env(monkeypatch)

    cert_path = tmp_path / "server.crt"
    cert_path.write_text("cert", encoding="utf-8")
    missing_key_path = tmp_path / "missing.key"

    monkeypatch.setenv("MCP_SSL_CERTFILE", str(cert_path))
    monkeypatch.setenv("MCP_SSL_KEYFILE", str(missing_key_path))

    with pytest.raises(FileNotFoundError, match="MCP_SSL_KEYFILE"):
        get_uvicorn_run_kwargs()
