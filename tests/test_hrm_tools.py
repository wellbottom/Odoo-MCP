import base64

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult

from odoo_mcp.mcp.app import create_mcp_server
from odoo_mcp.mcp.tools import hrm
from odoo_mcp.mcp.tools.hrm_toolset import register_hrm_tools


def test_export_payroll_table_returns_base64_for_client_download(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class PayrollExportOdoo:
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
            return {
                "file_name": "payroll.xlsx",
                "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "file_content": base64.b64encode(b"excel-bytes").decode("ascii"),
            }

    fake_odoo = PayrollExportOdoo()

    result = hrm.export_payroll_table(
        fake_odoo,
        run_id=190,
        page=1,
        records_per_page=20,
    )

    assert result["success"] is True
    assert result["delivery"] == "client_payload"
    assert result["server_saved"] is True
    assert result["file_path"].startswith("data/export/payroll_run_190_page_1_20_")
    assert result["file_path"].endswith(".xlsx")
    assert result["saved_file_name"].startswith("payroll_run_190_page_1_20_")
    assert result["saved_file_name"].endswith(".xlsx")
    assert result["file_name"] == "payroll.xlsx"
    assert result["file_content_base64"] == base64.b64encode(b"excel-bytes").decode("ascii")
    assert base64.b64decode(result["file_content_base64"]) == b"excel-bytes"
    assert (tmp_path / result["file_path"]).read_bytes() == b"excel-bytes"
    assert fake_odoo.calls == [
        {
            "model": "hr.payslip.run",
            "method": "export_xlsx",
            "args": (190, 1, 20, False, False, False, False),
            "kwargs": {},
        }
    ]


def test_export_payroll_table_can_write_explicit_server_side_copy(tmp_path):
    class PayrollExportOdoo:
        def execute_method(self, model, method, *args, **kwargs):
            return {
                "file_name": "payroll.xlsx",
                "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "file_content": base64.b64encode(b"excel-bytes").decode("ascii"),
            }

    output_path = tmp_path / "payroll.xlsx"

    result = hrm.export_payroll_table(
        PayrollExportOdoo(),
        run_id=190,
        output_path=str(output_path),
        include_file_content=False,
    )

    assert result["success"] is True
    assert result["server_saved"] is True
    assert result["file_path"] == str(output_path)
    assert result["saved_file_name"] == "payroll.xlsx"
    assert "file_content_base64" not in result
    assert output_path.read_bytes() == b"excel-bytes"


def test_export_payroll_table_resolves_run_from_company_and_stage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class PayrollExportOdoo:
        def __init__(self):
            self.searches = []

        def get_model_fields(self, model, **kwargs):
            assert model == "hr.payslip.run"
            return {
                "id": {},
                "name": {},
                "company_id": {},
                "date_start": {},
                "date_end": {},
                "state": {},
            }

        def search_read(self, model, domain, **kwargs):
            self.searches.append({"model": model, "domain": domain, "kwargs": kwargs})
            return [
                {
                    "id": 190,
                    "name": "Bảng lương tháng 3/2026",
                    "company_id": [7, "Company"],
                    "date_start": "2026-03-01",
                    "date_end": "2026-03-31",
                    "state": "close",
                }
            ]

        def execute_method(self, model, method, *args, **kwargs):
            return {
                "file_name": "payroll.xlsx",
                "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "file_content": base64.b64encode(b"excel-bytes").decode("ascii"),
            }

    fake_odoo = PayrollExportOdoo()
    result = hrm.export_payroll_table(
        fake_odoo,
        company_id=7,
        stage="tháng 3 năm 2026",
        include_file_content=False,
    )

    assert result["success"] is True
    assert result["run_id"] == 190
    assert result["company_id"] == 7
    assert result["stage"] == "tháng 3 năm 2026"
    assert result["file_path"].startswith("data/export/payroll_run_190_page_1_20_")
    assert result["saved_file_name"].startswith("payroll_run_190_page_1_20_")
    assert (tmp_path / result["file_path"]).read_bytes() == b"excel-bytes"
    assert result["run_resolution"]["mode"] == "company_stage"
    assert result["run_resolution"]["stage_period"]["display"] == "2026-03"
    assert fake_odoo.searches[0]["domain"] == [
        ("company_id", "=", 7),
        ("date_start", "<=", "2026-03-31"),
        ("date_end", ">=", "2026-03-01"),
    ]


def test_export_payroll_table_explains_company_stage_acl_failure():
    class PayrollExportOdoo:
        def get_model_fields(self, model, **kwargs):
            return {
                "id": {},
                "company_id": {},
                "date_start": {},
                "date_end": {},
            }

        def search_read(self, model, domain, **kwargs):
            raise Exception(
                "You are not allowed to access 'Payslip Batches' "
                "(hr.payslip.run) records. Payroll/Officer"
            )

    result = hrm.export_payroll_table(
        PayrollExportOdoo(),
        company_id=7,
        stage="03/2026",
    )

    assert result["success"] is False
    assert "Cannot resolve payroll batch from company_id and stage" in result["error"]
    assert "Direct export by run_id may still work" in result["error"]
    assert result["company_id"] == 7
    assert result["stage_period"]["display"] == "2026-03"


@pytest.mark.anyio
async def test_hrm_export_payroll_table_returns_embedded_file_resource_by_default(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    class PayrollExportOdoo:
        def get_model_fields(self, model, **kwargs):
            return {
                "id": {},
                "name": {},
                "company_id": {},
                "date_start": {},
                "date_end": {},
            }

        def search_read(self, model, domain, **kwargs):
            return [
                {
                    "id": 190,
                    "name": "Bảng lương tháng 3/2026",
                    "company_id": [7, "Company"],
                    "date_start": "2026-03-01",
                    "date_end": "2026-03-31",
                }
            ]

        def execute_method(self, model, method, *args, **kwargs):
            return {
                "file_name": "payroll.xlsx",
                "file_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "file_content": base64.b64encode(b"excel-bytes").decode("ascii"),
            }

    mcp = FastMCP("test")
    register_hrm_tools(mcp, resolve_odoo_client=lambda ctx: PayrollExportOdoo())

    result = await mcp.call_tool(
        "hrm_export_payroll_table",
        {
            "company_id": 7,
            "stage": "03/2026",
            "include_file_content": False,
        },
    )

    assert isinstance(result, CallToolResult)
    assert result.isError is False
    assert result.structuredContent["delivery"] == "embedded_resource"
    assert result.structuredContent["file_name"] == "payroll.xlsx"
    assert result.structuredContent["server_saved"] is True
    assert result.structuredContent["file_path"].startswith(
        "data/export/payroll_run_190_page_1_20_"
    )
    assert result.structuredContent["saved_file_name"].startswith(
        "payroll_run_190_page_1_20_"
    )
    assert "file_content_base64" not in result.structuredContent
    assert (tmp_path / result.structuredContent["file_path"]).read_bytes() == b"excel-bytes"

    resources = [content for content in result.content if content.type == "resource"]
    assert len(resources) == 1
    assert (
        resources[0].resource.mimeType
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert base64.b64decode(resources[0].resource.blob) == b"excel-bytes"


@pytest.mark.anyio
async def test_hrm_export_payroll_table_schema_is_registered():
    mcp = create_mcp_server()

    tools = await mcp.list_tools()
    export_tool = next(tool for tool in tools if tool.name == "hrm_export_payroll_table")

    properties = export_tool.inputSchema["properties"]
    assert "run_id" in properties
    assert "company_id" in properties
    assert "stage" in properties
    assert "page" in properties
    assert "records_per_page" in properties
    assert "khoi" in properties
    assert "phong" in properties
    assert "code" in properties
    assert "name" in properties
    assert "output_path" in properties
    assert "include_file_content" in properties
    assert "return_file_resource" in properties
    assert "run_id" not in export_tool.inputSchema.get("required", [])
