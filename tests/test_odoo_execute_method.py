import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from odoo_mcp.mcp.app import create_mcp_server
from odoo_mcp.mcp.tools import odoo
from odoo_mcp.mcp.tools.hrm_toolset import register_hrm_tools


def test_execute_method_forwards_args_and_kwargs():
    class FakeOdoo:
        def __init__(self):
            self.calls = []

        def execute_method(self, model, method, *args, **kwargs):
            self.calls.append(
                {
                    "model": model,
                    "method": method,
                    "args": args,
                    "kwargs": kwargs,
                }
            )
            return {"records": [1, 2, 3], "count": 3}

    fake_odoo = FakeOdoo()
    result = odoo.execute_method(
        fake_odoo,
        model="res.partner",
        method="search_read",
        args=[[["is_company", "=", True]]],
        kwargs={"limit": 5, "fields": ["name"]},
    )

    assert result == {
        "success": True,
        "model": "res.partner",
        "method": "search_read",
        "args": [[["is_company", "=", True]]],
        "kwargs": {"limit": 5, "fields": ["name"]},
        "result": {"records": [1, 2, 3], "count": 3},
    }
    assert fake_odoo.calls == [
        {
            "model": "res.partner",
            "method": "search_read",
            "args": ([["is_company", "=", True]],),
            "kwargs": {"limit": 5, "fields": ["name"]},
        }
    ]


def test_execute_method_rejects_blank_model_or_method():
    class FakeOdoo:
        def execute_method(self, model, method, *args, **kwargs):
            raise AssertionError("should not be called")

    assert odoo.execute_method(FakeOdoo(), model=" ", method="read") == {
        "success": False,
        "error": "model must be a non-empty string.",
    }
    assert odoo.execute_method(FakeOdoo(), model="res.partner", method=" ") == {
        "success": False,
        "error": "method must be a non-empty string.",
    }


@pytest.mark.anyio
async def test_odoo_execute_method_tool_returns_structured_payload():
    class FakeOdoo:
        def __init__(self):
            self.calls = []

        def execute_method(self, model, method, *args, **kwargs):
            self.calls.append(
                {
                    "model": model,
                    "method": method,
                    "args": args,
                    "kwargs": kwargs,
                }
            )
            return [{"id": 7, "name": "My Company"}]

    fake_odoo = FakeOdoo()
    mcp = FastMCP("test")
    register_hrm_tools(mcp, resolve_odoo_client=lambda ctx: fake_odoo)

    result = await mcp.call_tool(
        "odoo_execute_method",
        {
            "model": "res.company",
            "method": "search_read",
            "args": [[["id", "=", 7]]],
            "kwargs": {"fields": ["name"], "limit": 1},
        },
    )

    assert isinstance(result, CallToolResult)
    assert result.isError is False
    structured = dict(result.structuredContent)
    rate_limit = structured.pop("rate_limit")
    assert structured == {
        "success": True,
        "model": "res.company",
        "method": "search_read",
        "args": [[["id", "=", 7]]],
        "kwargs": {"fields": ["name"], "limit": 1},
        "result": [{"id": 7, "name": "My Company"}],
    }
    assert rate_limit["max_calls"] == 60
    assert rate_limit["window_seconds"] == 60
    assert rate_limit["retry_after_seconds"] == 0
    assert fake_odoo.calls == [
        {
            "model": "res.company",
            "method": "search_read",
            "args": ([["id", "=", 7]],),
            "kwargs": {"fields": ["name"], "limit": 1},
        }
    ]


@pytest.mark.anyio
async def test_odoo_execute_method_tool_is_listed_with_expected_schema():
    mcp = create_mcp_server()

    tools = await mcp.list_tools()
    execute_tool = next(tool for tool in tools if tool.name == "odoo_execute_method")

    properties = execute_tool.inputSchema["properties"]
    assert "model" in properties
    assert "method" in properties
    assert "args" in properties
    assert "kwargs" in properties
    assert set(execute_tool.inputSchema["required"]) == {"model", "method"}
