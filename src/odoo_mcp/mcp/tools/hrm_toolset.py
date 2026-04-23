from __future__ import annotations

import json
from typing import Dict, Optional
from urllib.parse import quote

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent

from ...server.observability import execute_observed_call
from . import hrm, odoo

XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def register_hrm_tools(
    mcp: FastMCP,
    *,
    resolve_odoo_client,
) -> None:
    """Register the MCP tools currently exposed to clients."""

    @mcp.tool(
        description=(
            "Execute an arbitrary Odoo model method through XML-RPC. Provide the "
            "target model name, method name, optional positional args, and optional "
            "keyword args. Also use this for agent-planned payroll export flows "
            "that intentionally translate a request such as 'xuat phieu luong cua "
            "cong ty A vao thang 3 nam 2026' into explicit res.company.search_read, "
            "hr.payslip.run.search_read, and hr.payslip.run.export_xlsx calls. "
            "For common call plans, read the MCP resource "
            "odoo://guides/execute-method-recipes and any linked recipe resource. "
            "Prefer the narrower payroll export tool only when the caller "
            "explicitly wants the convenience wrapper or embedded file-resource "
            "delivery."
        )
    )
    def odoo_execute_method(
        ctx: Context,
        model: str,
        method: str,
        args: list[object] | None = None,
        kwargs: Dict[str, object] | None = None,
    ) -> CallToolResult:
        odoo_client = resolve_odoo_client(ctx)
        result = execute_observed_call(
            ctx,
            odoo_client=odoo_client,
            surface="tool",
            surface_name="odoo_execute_method",
            model=model.strip() if model.strip() else "<invalid>",
            method=method.strip() if method.strip() else "<invalid>",
            operation=lambda: odoo.execute_method(
                odoo_client,
                model=model,
                method=method,
                args=list(args or []),
                kwargs=dict(kwargs or {}),
            ),
        )
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(result, ensure_ascii=False, indent=2),
                )
            ],
            structuredContent=result,
            isError=not bool(result.get("success")),
        )

    @mcp.tool(
        description=(
            "Export the custom Odoo payroll table/Báo cáo tổng hợp lương for one "
            "company and payroll stage/month. Provide company_id and stage "
            "(for example 'tháng 3 năm 2026', '2026-03', or '03/2026'); run_id "
            "is optional and only needed when the caller already knows the exact "
            "hr.payslip.run batch. By default the XLSX bytes are returned as an "
            "embedded MCP file resource so clients that support file resources can "
            "offer an immediate download/open action. include_file_content also "
            "keeps the raw file_content_base64 fallback in structured metadata; "
            "the server also saves a copy under data/export by default, and "
            "output_path overrides that server-side destination. This calls the "
            "Odoo custom method hr.payslip.run.export_xlsx, preserving the same "
            "columns and formatting as the web UI. This is the convenience "
            "wrapper; prefer odoo_execute_method when an agent needs explicit "
            "control over the underlying model, method, and args for a natural-"
            "language company plus month payroll export request."
        )
    )
    def hrm_export_payroll_table(
        ctx: Context,
        run_id: Optional[int] = None,
        company_id: Optional[int] = None,
        stage: Optional[str] = None,
        page: int = 1,
        records_per_page: int = 20,
        khoi: Optional[str] = None,
        phong: Optional[str] = None,
        code: Optional[str] = None,
        name: Optional[str] = None,
        output_path: Optional[str] = None,
        include_file_content: bool = True,
        return_file_resource: bool = True,
    ) -> CallToolResult:
        odoo_client = resolve_odoo_client(ctx)
        include_content_for_result = include_file_content or return_file_resource
        result = execute_observed_call(
            ctx,
            odoo_client=odoo_client,
            surface="tool",
            surface_name="hrm_export_payroll_table",
            model="hr.payslip.run",
            method="export_xlsx",
            operation=lambda: hrm.export_payroll_table(
                odoo_client,
                run_id=run_id,
                company_id=company_id,
                stage=stage,
                page=page,
                records_per_page=records_per_page,
                khoi=khoi,
                phong=phong,
                code=code,
                name=name,
                output_path=output_path,
                include_file_content=include_content_for_result,
            ),
        )
        return _build_payroll_export_tool_result(
            result,
            include_file_content=include_file_content,
            return_file_resource=return_file_resource,
        )


def _build_payroll_export_tool_result(
    result: Dict[str, object],
    *,
    include_file_content: bool,
    return_file_resource: bool,
) -> CallToolResult:
    structured = dict(result)
    file_content_base64 = structured.get("file_content_base64")

    if not include_file_content:
        structured.pop("file_content_base64", None)
        structured.pop("encoding", None)

    if not result.get("success"):
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(structured, ensure_ascii=False, indent=2),
                )
            ],
            structuredContent=structured,
            isError=True,
        )

    if return_file_resource and isinstance(file_content_base64, str):
        default_file_name = f"payroll_table_run_{result.get('run_id')}.xlsx"
        file_name = str(result.get("file_name") or default_file_name)
        file_type = str(result.get("file_type") or XLSX_MIME_TYPE)
        run_id = result.get("run_id")
        resource_uri = f"odoo://exports/payroll-table/{run_id}/{quote(file_name)}"

        structured["delivery"] = "embedded_resource"
        structured["client_download_instructions"] = (
            "The XLSX is attached as an embedded MCP resource. Clients that support "
            "file resources can expose it as a file download/open action."
        )

        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"Payroll export ready: {file_name} "
                        f"({structured.get('file_size_bytes')} bytes)."
                    ),
                ),
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(
                        uri=resource_uri,
                        mimeType=file_type,
                        blob=file_content_base64,
                    ),
                ),
            ],
            structuredContent=structured,
            isError=False,
        )

    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(structured, ensure_ascii=False, indent=2),
            )
        ],
        structuredContent=structured,
        isError=False,
    )
