import pytest


@pytest.fixture(autouse=True)
def default_toolsets_env(monkeypatch):
    monkeypatch.delenv("MCP_TOOLSETS", raising=False)
