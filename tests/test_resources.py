import json

import pytest
from mcp.server.fastmcp import FastMCP

from odoo_mcp.mcp.app import create_mcp_server
from odoo_mcp.mcp.resources.odoo import register_resources


@pytest.mark.anyio
async def test_create_mcp_server_lists_semantic_odoo_resources():
    mcp = create_mcp_server()

    resources = await mcp.list_resources()

    resource_uris = {str(resource.uri) for resource in resources}
    assert "odoo://server/info" in resource_uris
    assert "odoo://models" in resource_uris
    assert "odoo://guides/execute-method-recipes" in resource_uris
    assert "odoo://recipes/payroll-export/company-month" in resource_uris
    assert "odoo://models/hr.payslip.run/fields" in resource_uris
    assert "odoo://domains/hr/companies" in resource_uris
    assert "odoo://domains/hr/departments" in resource_uris
    assert "odoo://domains/hr/payroll/runs" in resource_uris
    assert "odoo://domains/finance/journals" in resource_uris
    assert all(resource.mimeType == "application/json" for resource in resources)


@pytest.mark.anyio
async def test_create_mcp_server_lists_odoo_resource_templates():
    mcp = create_mcp_server()

    templates = await mcp.list_resource_templates()

    template_uris = {template.uriTemplate for template in templates}
    assert "odoo://models/{model}/fields" in template_uris
    assert "odoo://records/{model}/{record_id}" in template_uris
    assert "odoo://domains/hr/companies/{company_id}" in template_uris
    assert "odoo://domains/hr/departments/{department_id}" in template_uris
    assert "odoo://domains/hr/payroll/runs/{run_id}" in template_uris
    assert "odoo://domains/finance/journals/{journal_id}" in template_uris
    assert "odoo://domains/hr/payroll/company/{company_id}/period/{year}/{month}" in template_uris


@pytest.mark.anyio
async def test_common_model_field_resource_reads_payroll_run_model():
    class FakeOdooClient:
        def __init__(self):
            self.requested_models = []

        def get_model_fields(self, model, raise_on_error=False, context=None):
            assert raise_on_error is True
            self.requested_models.append(model)
            return {"name": {"type": "char", "string": f"{model} name"}}

    fake_odoo = FakeOdooClient()
    mcp = FastMCP("test")
    register_resources(mcp, resolve_odoo_client=lambda ctx: fake_odoo)

    content = await mcp.read_resource("odoo://models/hr.payslip.run/fields")
    payload = json.loads(content[0].content)

    assert payload["model"] == "hr.payslip.run"
    assert fake_odoo.requested_models == ["hr.payslip.run"]
    assert payload["rate_limit"]["max_calls"] == 60


@pytest.mark.anyio
async def test_semantic_department_resource_reads_curated_domain_payload():
    class FakeOdooClient:
        def __init__(self):
            self.fields_calls = []
            self.read_calls = []

        def get_model_fields(self, model, raise_on_error=False, context=None):
            self.fields_calls.append(model)
            return {
                "id": {},
                "name": {},
                "company_id": {},
                "parent_id": {},
                "manager_id": {},
                "ignored": {},
            }

        def search_read(self, model, domain, fields=None, limit=None, order=None, raise_on_error=False, context=None):
            self.read_calls.append(
                {
                    "model": model,
                    "domain": domain,
                    "fields": fields,
                    "limit": limit,
                    "order": order,
                }
            )
            return [
                {
                    "id": 3,
                    "name": "Finance",
                    "company_id": [1, "Main"],
                    "parent_id": False,
                    "manager_id": [8, "Alice"],
                }
            ]

    fake_odoo = FakeOdooClient()
    mcp = FastMCP("test")
    register_resources(mcp, resolve_odoo_client=lambda ctx: fake_odoo)

    content = await mcp.read_resource("odoo://domains/hr/departments")
    payload = json.loads(content[0].content)

    assert payload["semantic_domain"] == "hr.departments"
    assert payload["model"] == "hr.department"
    assert payload["fields"] == ["id", "name", "company_id", "parent_id", "manager_id"]
    assert payload["records"][0]["name"] == "Finance"
    assert fake_odoo.fields_calls == ["hr.department"]
    assert fake_odoo.read_calls == [
        {
            "model": "hr.department",
            "domain": [],
            "fields": ["id", "name", "company_id", "parent_id", "manager_id"],
            "limit": 200,
            "order": "company_id asc, name asc",
        }
    ]


@pytest.mark.anyio
async def test_execute_method_recipe_resources_are_readable():
    mcp = create_mcp_server()

    index_content = await mcp.read_resource("odoo://guides/execute-method-recipes")
    index_payload = json.loads(index_content[0].content)

    assert index_payload["tool"] == "odoo_execute_method"
    assert index_payload["recipes"][0]["uri"] == "odoo://recipes/payroll-export/company-month"

    recipe_content = await mcp.read_resource("odoo://recipes/payroll-export/company-month")
    recipe_payload = json.loads(recipe_content[0].content)

    assert recipe_payload["recipe_id"] == "payroll_export_company_month"
    assert recipe_payload["steps"][0]["call"]["model"] == "res.company"
    assert recipe_payload["steps"][1]["call"]["model"] == "hr.payslip.run"
    assert recipe_payload["steps"][2]["call"]["method"] == "export_xlsx"
