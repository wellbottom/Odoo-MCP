"""Structured prompt templates for payroll-related MCP guidance."""

from __future__ import annotations

from typing import Any

EXECUTE_METHOD_RECIPE_INDEX_URI = "odoo://guides/execute-method-recipes"
PAYROLL_EXPORT_COMPANY_MONTH_RECIPE_URI = (
    "odoo://recipes/payroll-export/company-month"
)


def build_execute_method_recipe_index() -> dict[str, Any]:
    return {
        "success": True,
        "version": 1,
        "tool": "odoo_execute_method",
        "recipes": [
            {
                "uri": PAYROLL_EXPORT_COMPANY_MONTH_RECIPE_URI,
                "intent": (
                    "Export one company's payroll batch for a requested month "
                    "by resolving the company, resolving hr.payslip.run, then "
                    "calling hr.payslip.run.export_xlsx."
                ),
                "trigger_examples": [
                    "xuat phieu luong cua cong ty A vao thang 3 nam 2026",
                    "xuat bang luong cong ty A thang 3/2026",
                    "export payroll for company A for March 2026",
                ],
            }
        ],
    }


def build_payroll_export_company_month_recipe() -> dict[str, Any]:
    return {
        "success": True,
        "recipe_id": "payroll_export_company_month",
        "tool": "odoo_execute_method",
        "summary": (
            "Resolve the company ID, resolve the payroll batch, then call "
            "hr.payslip.run.export_xlsx."
        ),
        "when_to_use": [
            "The user asks to export payroll or payslips for one company and one month.",
            "The request is phrased in natural language rather than explicit model and method names.",
        ],
        "extract_from_user_request": {
            "company_name": "Required unless the user already provided company_id.",
            "month": (
                "Required unless the user already provided run_id. Accept formats "
                "such as YYYY-MM, MM/YYYY, or 'thang M nam YYYY'."
            ),
            "optional_filters": [
                "khoi",
                "phong",
                "code",
                "name",
            ],
        },
        "steps": [
            {
                "step": 1,
                "purpose": "Resolve the company name to a res.company ID.",
                "call": {
                    "model": "res.company",
                    "method": "search_read",
                    "args_template": [
                        [
                            ["name", "ilike", "<company_name>"],
                        ]
                    ],
                    "kwargs_template": {
                        "fields": ["id", "name", "display_name"],
                        "limit": 5,
                    },
                },
                "selection_rule": (
                    "Choose the exact or best company match. If multiple plausible "
                    "companies remain, ask the user to clarify."
                ),
            },
            {
                "step": 2,
                "purpose": "Resolve the payroll batch for the requested month.",
                "call": {
                    "model": "hr.payslip.run",
                    "method": "search_read",
                    "args_template": [
                        [
                            ["company_id", "=", "<company_id>"],
                            ["date_start", "<=", "<month_end>"],
                            ["date_end", ">=", "<month_start>"],
                        ]
                    ],
                    "kwargs_template": {
                        "fields": [
                            "id",
                            "name",
                            "company_id",
                            "date_start",
                            "date_end",
                            "state",
                        ],
                        "limit": 10,
                        "order": "date_start desc, id desc",
                    },
                },
                "selection_rule": (
                    "Prefer an exact month match. If no run matches, report that. "
                    "If multiple runs match, ask the user which payroll batch to export."
                ),
            },
            {
                "step": 3,
                "purpose": "Export the XLSX from the resolved payroll batch.",
                "call": {
                    "model": "hr.payslip.run",
                    "method": "export_xlsx",
                    "args_template": [
                        "<run_id>",
                        1,
                        20,
                        False,
                        False,
                        False,
                        False,
                    ],
                    "kwargs_template": {},
                },
                "parameter_notes": {
                    "args_order": [
                        "run_id",
                        "page",
                        "records_per_page",
                        "khoi",
                        "phong",
                        "code",
                        "name",
                    ]
                },
            },
        ],
        "shortcuts": [
            "If company_id is already known, skip step 1.",
            "If run_id is already known, skip steps 1 and 2.",
            "If an Odoo URL already identifies an active hr.payslip.run, extract that run_id and skip step 2.",
        ],
        "result_handling": {
            "payload_location": "structuredContent.result",
            "fields_to_read": [
                "file_content",
                "file_name",
                "file_type",
            ],
            "note": (
                "odoo_execute_method returns the raw Odoo payload, not the embedded "
                "file-resource wrapper used by hrm_export_payroll_table."
            ),
        },
        "fallback": {
            "tool": "hrm_export_payroll_table",
            "when": (
                "Use only when the caller explicitly wants the convenience wrapper "
                "or embedded MCP file-resource delivery."
            ),
        },
        "examples": [
            {
                "user_request": "xuat phieu luong cua cong ty A vao thang 3 nam 2026",
                "call_sequence": [
                    {
                        "model": "res.company",
                        "method": "search_read",
                        "args": [[["name", "ilike", "Cong ty A"]]],
                        "kwargs": {
                            "fields": ["id", "name", "display_name"],
                            "limit": 5,
                        },
                    },
                    {
                        "model": "hr.payslip.run",
                        "method": "search_read",
                        "args": [[
                            ["company_id", "=", 7],
                            ["date_start", "<=", "2026-03-31"],
                            ["date_end", ">=", "2026-03-01"],
                        ]],
                        "kwargs": {
                            "fields": [
                                "id",
                                "name",
                                "company_id",
                                "date_start",
                                "date_end",
                                "state",
                            ],
                            "limit": 10,
                            "order": "date_start desc, id desc",
                        },
                    },
                    {
                        "model": "hr.payslip.run",
                        "method": "export_xlsx",
                        "args": [190, 1, 20, False, False, False, False],
                        "kwargs": {},
                    },
                ],
            }
        ],
    }
