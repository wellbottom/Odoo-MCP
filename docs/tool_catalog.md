# MCP Tool Catalog

This server exposes two MCP tools by default:

- `odoo_execute_method`
- `hrm_export_payroll_table`

## Toolsets

| Toolset | Default | Tools |
| --- | --- | --- |
| `hrm` | Yes | `odoo_execute_method`, `hrm_export_payroll_table` |

`MCP_TOOLSETS=all` is accepted, but it still resolves to the single `hrm` toolset.

## Tool Selection

| Tool | Use when |
| --- | --- |
| `odoo_execute_method` | The caller explicitly wants to run a concrete Odoo `model` and `method`, or the client wants to decompose a natural-language workflow into explicit Odoo calls. |
| `hrm_export_payroll_table` | The caller wants the payroll-table export convenience wrapper, embedded file-resource delivery, or a company-plus-month payroll export without manually orchestrating the underlying Odoo calls. |

For a request like `xuat phieu luong cua cong ty A vao thang 3 nam 2026`, the explicit plan behind `odoo_execute_method` is usually:

- `res.company.search_read`
- `hr.payslip.run.search_read`
- `hr.payslip.run.export_xlsx`

If the client does not already know that call shape, read these resources first:

- `odoo://guides/execute-method-recipes`
- `odoo://recipes/payroll-export/company-month`

## Semantic Resources

Besides generic model resources, the server now exposes semantic URIs for common domains:

- `odoo://domains/hr/companies`
- `odoo://domains/hr/companies/{company_id}`
- `odoo://domains/hr/departments`
- `odoo://domains/hr/departments/{department_id}`
- `odoo://domains/hr/payroll/runs`
- `odoo://domains/hr/payroll/runs/{run_id}`
- `odoo://domains/hr/payroll/company/{company_id}/period/{year}/{month}`
- `odoo://domains/finance/journals`
- `odoo://domains/finance/journals/{journal_id}`

Use these when the client wants domain-oriented payloads instead of raw model browsing.

## File Delivery

`hrm_export_payroll_table` returns the XLSX payload to the MCP client as an embedded file resource by default. Structured metadata includes:

- `file_name`
- `file_type`
- `file_size_bytes`
- `file_path`
- `delivery: embedded_resource`

The server also writes a server-side copy to:

```text
data/export/<file_name>_run_<run_id>_page_<page>_<records_per_page>_<timestamp>.xlsx
```

## Observability

Every tool/resource call is subject to:

- temporary in-memory rate limiting
- audit logging with user, model, method, duration, status, and export metadata
- stable error categories for timeout, auth, authorization, protocol, connection, and remote application failures
