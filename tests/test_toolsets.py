import pytest

from odoo_mcp.mcp.app import create_mcp_server
from odoo_mcp.mcp.tools.registry import get_enabled_toolsets


def test_get_enabled_toolsets_defaults_to_payroll_focus(monkeypatch):
    monkeypatch.delenv("MCP_TOOLSETS", raising=False)

    assert get_enabled_toolsets() == ("hrm",)


def test_get_enabled_toolsets_accepts_all():
    assert get_enabled_toolsets("all") == ("hrm",)
    assert get_enabled_toolsets("*") == ("hrm",)


def test_get_enabled_toolsets_deduplicates_and_normalizes():
    assert get_enabled_toolsets(" HRM,hrm ") == ("hrm",)


def test_get_enabled_toolsets_rejects_unknown_group():
    with pytest.raises(ValueError, match="Unknown MCP toolset"):
        get_enabled_toolsets("general,crm")


@pytest.mark.anyio
async def test_default_server_registers_expected_tools(monkeypatch):
    monkeypatch.delenv("MCP_TOOLSETS", raising=False)

    mcp = create_mcp_server()
    tools = await mcp.list_tools()
    tool_names = [tool.name for tool in tools]

    assert tool_names == ["odoo_execute_method", "hrm_export_payroll_table"]


@pytest.mark.anyio
async def test_hrm_toolset_can_be_enabled_explicitly(monkeypatch):
    monkeypatch.setenv("MCP_TOOLSETS", "hrm")

    mcp = create_mcp_server()
    tools = await mcp.list_tools()
    tool_names = {tool.name for tool in tools}

    assert tool_names == {"odoo_execute_method", "hrm_export_payroll_table"}


@pytest.mark.anyio
async def test_tool_descriptions_explain_payroll_export_routing(monkeypatch):
    monkeypatch.delenv("MCP_TOOLSETS", raising=False)

    mcp = create_mcp_server()
    tools = await mcp.list_tools()
    descriptions = {tool.name: tool.description for tool in tools}

    assert "hr.payslip.run.export_xlsx" in descriptions["odoo_execute_method"]
    assert "odoo://guides/execute-method-recipes" in descriptions["odoo_execute_method"]
    assert "convenience wrapper" in descriptions["hrm_export_payroll_table"]
