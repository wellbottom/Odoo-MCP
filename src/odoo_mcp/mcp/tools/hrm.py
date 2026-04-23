"""Payroll table export logic for the MCP tool surface."""

from __future__ import annotations

import base64
import calendar
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ...server.client import OdooClient
from ...server.errors import error_to_payload

PAYROLL_RUN_MODEL = "hr.payslip.run"
PAYROLL_EXPORT_METHOD = "export_xlsx"
PAYROLL_RUN_SEARCH_FIELDS = ["id", "name", "company_id", "date_start", "date_end", "state"]
DEFAULT_EXPORT_DIR = Path("data/export")


def export_payroll_table(
    odoo: OdooClient,
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
) -> Dict[str, Any]:
    """
    Export the custom Odoo payroll table for one hr.payslip.run to XLSX.

    If run_id is not provided, company_id and stage are used to resolve the
    payroll batch. stage accepts values like "2026-03", "03/2026", or
    "thang 3 nam 2026".
    """
    base_payload = {"model": PAYROLL_RUN_MODEL, "method": PAYROLL_EXPORT_METHOD}

    if run_id is not None and run_id <= 0:
        return _validation_error("run_id must be a positive integer.", extra=base_payload)
    if page <= 0:
        return _validation_error("page must be a positive integer.", extra=base_payload)
    if records_per_page <= 0:
        return _validation_error(
            "records_per_page must be a positive integer.",
            extra=base_payload,
        )

    run_resolution: Dict[str, Any] = {"mode": "run_id", "run_id": run_id}
    if run_id is None:
        run_resolution = resolve_payroll_run(odoo, company_id=company_id, stage=stage)
        if not run_resolution.get("success"):
            return run_resolution
        run_id = int(run_resolution["run_id"])

    filters = {
        "khoi": khoi or False,
        "phong": phong or False,
        "code": code or False,
        "name": name or False,
    }

    try:
        result = odoo.execute_method(
            PAYROLL_RUN_MODEL,
            PAYROLL_EXPORT_METHOD,
            run_id,
            page,
            records_per_page,
            filters["khoi"],
            filters["phong"],
            filters["code"],
            filters["name"],
        )
        if not isinstance(result, dict):
            return {
                **base_payload,
                "success": False,
                "error": "hr.payslip.run.export_xlsx returned an unexpected payload.",
                "error_category": "unexpected_response",
                "retryable": False,
                "result_type": type(result).__name__,
            }

        file_content = result.get("file_content")
        if not file_content:
            return {
                **base_payload,
                "success": False,
                "error": "hr.payslip.run.export_xlsx did not return file_content.",
                "error_category": "unexpected_response",
                "retryable": False,
                "result_keys": sorted(result.keys()),
            }

        file_bytes = base64.b64decode(file_content)
        file_name = _safe_export_file_name(
            result.get("file_name"),
            default=f"payroll_table_run_{run_id}.xlsx",
        )
        export_path = (
            Path(output_path)
            if output_path
            else _default_export_path(
                file_name=file_name,
                run_id=run_id,
                page=page,
                records_per_page=records_per_page,
            )
        )
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_bytes(file_bytes)

        payload: Dict[str, Any] = {
            **base_payload,
            "success": True,
            "delivery": "client_payload",
            "server_saved": True,
            "file_path": str(export_path),
            "saved_file_name": export_path.name,
            "file_name": file_name,
            "file_type": result.get("file_type"),
            "file_size_bytes": len(file_bytes),
            "run_id": run_id,
            "company_id": company_id,
            "stage": stage,
            "run_resolution": run_resolution,
            "page": page,
            "records_per_page": records_per_page,
            "filters": filters,
            "client_download_instructions": (
                "Save file_content_base64 as file_name on the client machine. "
                "The MCP server does not know the client's local filesystem."
            ),
        }
        if include_file_content:
            payload["file_content_base64"] = file_content
            payload["encoding"] = "base64"
        return payload
    except Exception as exc:
        if _is_payroll_run_access_error(exc):
            return {
                **base_payload,
                "success": False,
                "error": (
                    "Cannot export payroll table because the authenticated Odoo "
                    "user is not allowed to access hr.payslip.run in this call."
                ),
                "error_category": "authorization_error",
                "retryable": False,
                "original_error": str(exc),
                "company_id": company_id,
                "stage": stage,
                "run_id": run_id,
            }
        return error_to_payload(
            exc,
            model=PAYROLL_RUN_MODEL,
            method=PAYROLL_EXPORT_METHOD,
            operation="payroll export",
        )


def resolve_payroll_run(
    odoo: OdooClient,
    *,
    company_id: Optional[int],
    stage: Optional[str],
) -> Dict[str, Any]:
    base_payload = {"model": PAYROLL_RUN_MODEL, "method": PAYROLL_EXPORT_METHOD}

    if company_id is None or company_id <= 0:
        return _validation_error(
            "company_id must be provided when run_id is not provided.",
            extra=base_payload,
        )

    stage_period = parse_payroll_stage(stage)
    if not stage_period.get("success"):
        return stage_period

    try:
        fields = odoo.get_model_fields(PAYROLL_RUN_MODEL, raise_on_error=True)
        available_fields = set(fields.keys())
        if "company_id" not in available_fields:
            return {
                **base_payload,
                "success": False,
                "error": "hr.payslip.run does not expose company_id; cannot resolve run by company.",
                "error_category": "unsupported_model_shape",
                "retryable": False,
            }

        search_fields = [
            field for field in PAYROLL_RUN_SEARCH_FIELDS if field in available_fields
        ]
        records = _search_payroll_runs_for_period(
            odoo,
            company_id=company_id,
            stage_period=stage_period,
            available_fields=available_fields,
            search_fields=search_fields,
        )
        if not records:
            return {
                **base_payload,
                "success": False,
                "error": "No payroll batch found for company_id and stage.",
                "error_category": "not_found",
                "retryable": False,
                "company_id": company_id,
                "stage": stage,
                "stage_period": stage_period,
            }

        best_matches = _filter_exact_month_records(records, stage_period)
        if len(best_matches) == 1:
            record = best_matches[0]
        elif len(records) == 1:
            record = records[0]
        else:
            return {
                **base_payload,
                "success": False,
                "error": "Multiple payroll batches found for company_id and stage.",
                "error_category": "multiple_matches",
                "retryable": False,
                "company_id": company_id,
                "stage": stage,
                "stage_period": stage_period,
                "matching_runs": records,
            }

        return {
            **base_payload,
            "success": True,
            "mode": "company_stage",
            "run_id": record["id"],
            "company_id": company_id,
            "stage": stage,
            "stage_period": stage_period,
            "payroll_run": record,
        }
    except Exception as exc:
        if _is_payroll_run_access_error(exc):
            return {
                **base_payload,
                "success": False,
                "error": (
                    "Cannot resolve payroll batch from company_id and stage because "
                    "the authenticated Odoo user cannot read hr.payslip.run records. "
                    "Direct export by run_id may still work because it calls "
                    "hr.payslip.run.export_xlsx without searching batches first."
                ),
                "error_category": "authorization_error",
                "retryable": False,
                "original_error": str(exc),
                "company_id": company_id,
                "stage": stage,
                "stage_period": stage_period,
                "fallback": (
                    "Provide run_id, or add an Odoo-side export method that "
                    "resolves company/stage with appropriate permissions."
                ),
            }
        payload = error_to_payload(
            exc,
            model=PAYROLL_RUN_MODEL,
            method=PAYROLL_EXPORT_METHOD,
            operation="payroll run resolution",
        )
        payload["company_id"] = company_id
        payload["stage"] = stage
        payload["stage_period"] = stage_period
        return payload


def parse_payroll_stage(stage: Optional[str]) -> Dict[str, Any]:
    base_payload = {"model": PAYROLL_RUN_MODEL, "method": PAYROLL_EXPORT_METHOD}

    if not stage or not stage.strip():
        return _validation_error(
            "stage must be provided when run_id is not provided.",
            extra=base_payload,
        )

    normalized = _normalize_text(stage)
    year = None
    month = None

    for pattern in (
        r"\b(?P<year>\d{4})[-/\.](?P<month>\d{1,2})\b",
        r"\b(?P<month>\d{1,2})[-/\.](?P<year>\d{4})\b",
        r"\bthang\s*(?P<month>\d{1,2})\s*(?:nam)?\s*(?P<year>\d{4})\b",
    ):
        match = re.search(pattern, normalized)
        if match:
            year = int(match.group("year"))
            month = int(match.group("month"))
            break

    if year is None or month is None:
        return _validation_error(
            "stage must identify a month and year, for example '2026-03', "
            "'03/2026', or 'thang 3 nam 2026'.",
            extra=base_payload,
        )

    if month < 1 or month > 12:
        return _validation_error(
            "stage month must be between 1 and 12.",
            extra=base_payload,
        )

    _, last_day = calendar.monthrange(year, month)
    start_date = date(year, month, 1).isoformat()
    end_date = date(year, month, last_day).isoformat()
    return {
        **base_payload,
        "success": True,
        "year": year,
        "month": month,
        "date_start": start_date,
        "date_end": end_date,
        "display": f"{year}-{month:02d}",
    }


def _search_payroll_runs_for_period(
    odoo: OdooClient,
    *,
    company_id: int,
    stage_period: Dict[str, Any],
    available_fields: set[str],
    search_fields: list[str],
) -> list[Dict[str, Any]]:
    base_domain = [("company_id", "=", company_id)]
    if {"date_start", "date_end"}.issubset(available_fields):
        domain = [
            *base_domain,
            ("date_start", "<=", stage_period["date_end"]),
            ("date_end", ">=", stage_period["date_start"]),
        ]
        return odoo.search_read(
            PAYROLL_RUN_MODEL,
            domain,
            fields=search_fields,
            limit=10,
            order="date_start desc, id desc",
            raise_on_error=True,
        )

    if "name" not in available_fields:
        return []

    for label in _stage_name_variants(stage_period):
        records = odoo.search_read(
            PAYROLL_RUN_MODEL,
            [*base_domain, ("name", "ilike", label)],
            fields=search_fields,
            limit=10,
            order="id desc",
            raise_on_error=True,
        )
        if records:
            return records

    return []


def _filter_exact_month_records(
    records: list[Dict[str, Any]],
    stage_period: Dict[str, Any],
) -> list[Dict[str, Any]]:
    exact = []
    for record in records:
        date_start = record.get("date_start")
        date_end = record.get("date_end")
        if date_start == stage_period["date_start"] and date_end == stage_period["date_end"]:
            exact.append(record)
    return exact


def _stage_name_variants(stage_period: Dict[str, Any]) -> list[str]:
    year = stage_period["year"]
    month = stage_period["month"]
    return [
        f"{year}-{month:02d}",
        f"{month:02d}/{year}",
        f"{month}/{year}",
        f"{month:02d}-{year}",
        f"{month}-{year}",
        f"thang {month} nam {year}",
    ]


def _normalize_text(value: str) -> str:
    without_accents = unicodedata.normalize("NFKD", value)
    ascii_text = without_accents.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_text.lower().strip().split())


def _safe_export_file_name(value: Any, *, default: str) -> str:
    file_name = Path(str(value or default)).name.strip()
    file_name = file_name.replace("/", "_").replace("\\", "_")
    if not file_name:
        file_name = default
    if not file_name.lower().endswith(".xlsx"):
        file_name = f"{file_name}.xlsx"
    return file_name


def _default_export_path(
    *,
    file_name: str,
    run_id: int,
    page: int,
    records_per_page: int,
) -> Path:
    file_path = Path(file_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = file_path.stem
    suffix = file_path.suffix or ".xlsx"
    saved_file_name = (
        f"{stem}_run_{run_id}_page_{page}_{records_per_page}_{timestamp}{suffix}"
    )
    return DEFAULT_EXPORT_DIR / saved_file_name


def _validation_error(message: str, *, extra: dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = {
        "success": False,
        "error": message,
        "error_category": "validation_error",
        "retryable": False,
    }
    if extra:
        payload.update(extra)
    return payload


def _is_payroll_run_access_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return ("hr.payslip.run" in message and "not allowed to access" in message) or (
        "payslip batches" in message and "payroll/officer" in message
    )
