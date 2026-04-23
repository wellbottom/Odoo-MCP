"""MCP resources exposed by the Odoo server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mcp.server.fastmcp import Context, FastMCP

from ...server.observability import execute_observed_call
from ..prompt_templates.payroll import (
    EXECUTE_METHOD_RECIPE_INDEX_URI,
    PAYROLL_EXPORT_COMPANY_MONTH_RECIPE_URI,
    build_execute_method_recipe_index,
    build_payroll_export_company_month_recipe,
)
from ..tools import hrm

ResolveOdooClient = Callable[[Context], Any]

JSON_MIME_TYPE = "application/json"

COMMON_MODELS: dict[str, str] = {
    "hr.payslip.run": "Payroll batch fields",
    "res.company": "Company fields",
    "hr.department": "Department fields",
    "account.journal": "Finance journal fields",
}


@dataclass(frozen=True, slots=True)
class SemanticCollection:
    uri: str
    name: str
    title: str
    description: str
    semantic_domain: str
    model: str
    fields: tuple[str, ...]
    order: str
    limit: int
    domain: tuple[tuple[str, str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticRecord:
    uri: str
    name: str
    title: str
    description: str
    semantic_domain: str
    model: str
    fields: tuple[str, ...]
    param_name: str


SEMANTIC_COLLECTIONS: tuple[SemanticCollection, ...] = (
    SemanticCollection(
        uri="odoo://domains/hr/companies",
        name="odoo_domain_hr_companies",
        title="HR Companies",
        description="Business-friendly company list used in HR and payroll flows.",
        semantic_domain="hr.companies",
        model="res.company",
        fields=("id", "name", "currency_id", "partner_id"),
        order="name asc",
        limit=200,
    ),
    SemanticCollection(
        uri="odoo://domains/hr/departments",
        name="odoo_domain_hr_departments",
        title="HR Departments",
        description="Business-friendly department catalog for HR flows.",
        semantic_domain="hr.departments",
        model="hr.department",
        fields=("id", "name", "company_id", "parent_id", "manager_id"),
        order="company_id asc, name asc",
        limit=200,
    ),
    SemanticCollection(
        uri="odoo://domains/hr/payroll/runs",
        name="odoo_domain_hr_payroll_runs",
        title="Payroll Runs",
        description="Recent payroll batches for HR payroll workflows.",
        semantic_domain="hr.payroll.runs",
        model="hr.payslip.run",
        fields=("id", "name", "company_id", "date_start", "date_end", "state"),
        order="date_start desc, id desc",
        limit=50,
    ),
    SemanticCollection(
        uri="odoo://domains/finance/journals",
        name="odoo_domain_finance_journals",
        title="Finance Journals",
        description="Business-friendly accounting journal list for finance workflows.",
        semantic_domain="finance.journals",
        model="account.journal",
        fields=("id", "name", "code", "type", "company_id", "active"),
        order="company_id asc, code asc",
        limit=200,
    ),
)

SEMANTIC_RECORDS: tuple[SemanticRecord, ...] = (
    SemanticRecord(
        uri="odoo://domains/hr/companies/{company_id}",
        name="odoo_domain_hr_company",
        title="HR Company",
        description="One company with stable HR-oriented fields.",
        semantic_domain="hr.companies",
        model="res.company",
        fields=("id", "name", "currency_id", "partner_id"),
        param_name="company_id",
    ),
    SemanticRecord(
        uri="odoo://domains/hr/departments/{department_id}",
        name="odoo_domain_hr_department",
        title="HR Department",
        description="One department with stable HR-oriented fields.",
        semantic_domain="hr.departments",
        model="hr.department",
        fields=("id", "name", "company_id", "parent_id", "manager_id"),
        param_name="department_id",
    ),
    SemanticRecord(
        uri="odoo://domains/hr/payroll/runs/{run_id}",
        name="odoo_domain_hr_payroll_run",
        title="Payroll Run",
        description="One payroll batch with stable payroll-oriented fields.",
        semantic_domain="hr.payroll.runs",
        model="hr.payslip.run",
        fields=("id", "name", "company_id", "date_start", "date_end", "state"),
        param_name="run_id",
    ),
    SemanticRecord(
        uri="odoo://domains/finance/journals/{journal_id}",
        name="odoo_domain_finance_journal",
        title="Finance Journal",
        description="One accounting journal with stable finance-oriented fields.",
        semantic_domain="finance.journals",
        model="account.journal",
        fields=("id", "name", "code", "type", "company_id", "active"),
        param_name="journal_id",
    ),
)


def register_resources(
    mcp: FastMCP,
    *,
    resolve_odoo_client: ResolveOdooClient,
) -> None:
    """Register read-only Odoo resources for MCP clients."""

    def get_odoo_client():
        return resolve_odoo_client(mcp.get_context())

    def observed_payload(
        *,
        resource_name: str,
        model: str,
        method: str,
        loader: Callable[[Any], dict[str, Any]],
    ) -> dict[str, Any]:
        ctx = mcp.get_context()
        odoo_client = get_odoo_client()
        return execute_observed_call(
            ctx,
            odoo_client=odoo_client,
            surface="resource",
            surface_name=resource_name,
            model=model,
            method=method,
            operation=lambda: loader(odoo_client),
        )

    def model_fields_payload(model: str) -> dict[str, Any]:
        return observed_payload(
            resource_name=f"odoo://models/{model}/fields",
            model=model,
            method="fields_get",
            loader=lambda odoo_client: {
                "success": True,
                "model": model,
                "fields": odoo_client.get_model_fields(model, raise_on_error=True),
            },
        )

    @mcp.resource(
        "odoo://server/info",
        name="odoo_server_info",
        title="Odoo Server Info",
        description="Authenticated Odoo server, user, and version metadata.",
        mime_type=JSON_MIME_TYPE,
    )
    def odoo_server_info() -> dict[str, Any]:
        return observed_payload(
            resource_name="odoo://server/info",
            model="odoo.server",
            method="version",
            loader=lambda odoo_client: {
                "success": True,
                "server": {
                    "url": odoo_client.url,
                    "database": odoo_client.db,
                    "username": odoo_client.username,
                    "uid": odoo_client.uid,
                    "version": odoo_client._common.version(),
                },
            },
        )

    @mcp.resource(
        "odoo://models",
        name="odoo_models",
        title="Odoo Models",
        description="All Odoo models visible to the authenticated user.",
        mime_type=JSON_MIME_TYPE,
    )
    def odoo_models() -> dict[str, Any]:
        return observed_payload(
            resource_name="odoo://models",
            model="ir.model",
            method="list_models",
            loader=lambda odoo_client: {
                "success": True,
                "models": odoo_client.get_models(),
            },
        )

    @mcp.resource(
        EXECUTE_METHOD_RECIPE_INDEX_URI,
        name="odoo_execute_method_recipe_index",
        title="Execute Method Recipes",
        description=(
            "Structured recipes that tell AI clients which model, method, args, "
            "and kwargs to use with odoo_execute_method for common workflows."
        ),
        mime_type=JSON_MIME_TYPE,
    )
    def odoo_execute_method_recipe_index() -> dict[str, Any]:
        return build_execute_method_recipe_index()

    @mcp.resource(
        PAYROLL_EXPORT_COMPANY_MONTH_RECIPE_URI,
        name="odoo_recipe_payroll_export_company_month",
        title="Payroll Export by Company and Month",
        description=(
            "Concrete odoo_execute_method call plan for natural-language payroll "
            "export requests that mention one company and one month."
        ),
        mime_type=JSON_MIME_TYPE,
    )
    def payroll_export_company_month_recipe() -> dict[str, Any]:
        return build_payroll_export_company_month_recipe()

    def make_common_model_fields_resource(model: str) -> Callable[[], dict[str, Any]]:
        def common_model_fields() -> dict[str, Any]:
            return model_fields_payload(model)

        return common_model_fields

    for model, title in COMMON_MODELS.items():
        resource_name = f"odoo_model_{model.replace('.', '_')}_fields"
        resource_uri = f"odoo://models/{model}/fields"
        mcp.resource(
            resource_uri,
            name=resource_name,
            title=title,
            description=f"Field definitions for the Odoo {model} model.",
            mime_type=JSON_MIME_TYPE,
        )(make_common_model_fields_resource(model))

    @mcp.resource(
        "odoo://models/{model}/fields",
        name="odoo_model_fields",
        title="Odoo Model Fields",
        description="Field definitions for any Odoo model visible to the authenticated user.",
        mime_type=JSON_MIME_TYPE,
    )
    def odoo_model_fields(model: str) -> dict[str, Any]:
        return model_fields_payload(model)

    @mcp.resource(
        "odoo://records/{model}/{record_id}",
        name="odoo_record",
        title="Odoo Record",
        description="Read one Odoo record by model and record ID.",
        mime_type=JSON_MIME_TYPE,
    )
    def odoo_record(model: str, record_id: int) -> dict[str, Any]:
        return observed_payload(
            resource_name=f"odoo://records/{model}/{record_id}",
            model=model,
            method="read",
            loader=lambda odoo_client: _record_payload(odoo_client, model=model, record_id=record_id),
        )

    for spec in SEMANTIC_COLLECTIONS:
        def build_collection_resource(collection: SemanticCollection = spec) -> Callable[[], dict[str, Any]]:
            def semantic_collection() -> dict[str, Any]:
                return observed_payload(
                    resource_name=collection.uri,
                    model=collection.model,
                    method="search_read",
                    loader=lambda odoo_client: _semantic_collection_payload(
                        odoo_client,
                        spec=collection,
                    ),
                )

            return semantic_collection

        mcp.resource(
            spec.uri,
            name=spec.name,
            title=spec.title,
            description=spec.description,
            mime_type=JSON_MIME_TYPE,
        )(build_collection_resource())

    company_record = next(spec for spec in SEMANTIC_RECORDS if spec.param_name == "company_id")

    @mcp.resource(
        company_record.uri,
        name=company_record.name,
        title=company_record.title,
        description=company_record.description,
        mime_type=JSON_MIME_TYPE,
    )
    def company_resource(company_id: int) -> dict[str, Any]:
        return observed_payload(
            resource_name=f"odoo://domains/hr/companies/{company_id}",
            model=company_record.model,
            method="read",
            loader=lambda odoo_client: _semantic_record_payload(
                odoo_client,
                spec=company_record,
                record_id=company_id,
            ),
        )

    department_record = next(
        spec for spec in SEMANTIC_RECORDS if spec.param_name == "department_id"
    )

    @mcp.resource(
        department_record.uri,
        name=department_record.name,
        title=department_record.title,
        description=department_record.description,
        mime_type=JSON_MIME_TYPE,
    )
    def department_resource(department_id: int) -> dict[str, Any]:
        return observed_payload(
            resource_name=f"odoo://domains/hr/departments/{department_id}",
            model=department_record.model,
            method="read",
            loader=lambda odoo_client: _semantic_record_payload(
                odoo_client,
                spec=department_record,
                record_id=department_id,
            ),
        )

    payroll_run_record = next(spec for spec in SEMANTIC_RECORDS if spec.param_name == "run_id")

    @mcp.resource(
        payroll_run_record.uri,
        name=payroll_run_record.name,
        title=payroll_run_record.title,
        description=payroll_run_record.description,
        mime_type=JSON_MIME_TYPE,
    )
    def payroll_run_resource(run_id: int) -> dict[str, Any]:
        return observed_payload(
            resource_name=f"odoo://domains/hr/payroll/runs/{run_id}",
            model=payroll_run_record.model,
            method="read",
            loader=lambda odoo_client: _semantic_record_payload(
                odoo_client,
                spec=payroll_run_record,
                record_id=run_id,
            ),
        )

    journal_record = next(spec for spec in SEMANTIC_RECORDS if spec.param_name == "journal_id")

    @mcp.resource(
        journal_record.uri,
        name=journal_record.name,
        title=journal_record.title,
        description=journal_record.description,
        mime_type=JSON_MIME_TYPE,
    )
    def journal_resource(journal_id: int) -> dict[str, Any]:
        return observed_payload(
            resource_name=f"odoo://domains/finance/journals/{journal_id}",
            model=journal_record.model,
            method="read",
            loader=lambda odoo_client: _semantic_record_payload(
                odoo_client,
                spec=journal_record,
                record_id=journal_id,
            ),
        )

    @mcp.resource(
        "odoo://domains/hr/payroll/company/{company_id}/period/{year}/{month}",
        name="odoo_domain_hr_payroll_company_period",
        title="Payroll Run by Company and Period",
        description="Resolve the payroll batch for one company and one month.",
        mime_type=JSON_MIME_TYPE,
    )
    def payroll_run_for_company_period(company_id: int, year: int, month: int) -> dict[str, Any]:
        stage = f"{year}-{month:02d}"
        return observed_payload(
            resource_name=(
                f"odoo://domains/hr/payroll/company/{company_id}/period/{year}/{month}"
            ),
            model="hr.payslip.run",
            method="resolve_company_period",
            loader=lambda odoo_client: _payroll_company_period_payload(
                odoo_client,
                company_id=company_id,
                stage=stage,
            ),
        )


def _record_payload(odoo_client: Any, *, model: str, record_id: int) -> dict[str, Any]:
    records = odoo_client.read_records(
        model,
        [record_id],
        raise_on_error=True,
    )
    if not records:
        return {
            "success": False,
            "error": f"Record {record_id} was not found in {model}.",
            "error_category": "not_found",
            "retryable": False,
            "model": model,
            "method": "read",
        }
    return {"success": True, "model": model, "record": records[0]}


def _semantic_collection_payload(odoo_client: Any, *, spec: SemanticCollection) -> dict[str, Any]:
    fields = _resolve_supported_fields(odoo_client, model=spec.model, preferred_fields=spec.fields)
    records = odoo_client.search_read(
        spec.model,
        list(spec.domain),
        fields=fields or None,
        limit=spec.limit,
        order=spec.order,
        raise_on_error=True,
    )
    return {
        "success": True,
        "semantic_domain": spec.semantic_domain,
        "model": spec.model,
        "records": records,
        "fields": fields,
        "limit": spec.limit,
        "order": spec.order,
    }


def _semantic_record_payload(
    odoo_client: Any,
    *,
    spec: SemanticRecord,
    record_id: int,
) -> dict[str, Any]:
    fields = _resolve_supported_fields(odoo_client, model=spec.model, preferred_fields=spec.fields)
    records = odoo_client.read_records(
        spec.model,
        [record_id],
        fields=fields or None,
        raise_on_error=True,
    )
    if not records:
        return {
            "success": False,
            "semantic_domain": spec.semantic_domain,
            "model": spec.model,
            "error": f"Record {record_id} was not found in {spec.model}.",
            "error_category": "not_found",
            "retryable": False,
        }
    return {
        "success": True,
        "semantic_domain": spec.semantic_domain,
        "model": spec.model,
        "record": records[0],
        "fields": fields,
    }


def _payroll_company_period_payload(
    odoo_client: Any,
    *,
    company_id: int,
    stage: str,
) -> dict[str, Any]:
    payload = hrm.resolve_payroll_run(
        odoo_client,
        company_id=company_id,
        stage=stage,
    )
    payload["semantic_domain"] = "hr.payroll.runs"
    return payload


def _resolve_supported_fields(
    odoo_client: Any,
    *,
    model: str,
    preferred_fields: tuple[str, ...],
) -> list[str]:
    available_fields = odoo_client.get_model_fields(model, raise_on_error=True)
    return [field_name for field_name in preferred_fields if field_name in available_fields]
