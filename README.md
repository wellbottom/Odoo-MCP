# Odoo MCP Server

MCP server for Odoo over XML-RPC. It exposes a generic Odoo method tool, a payroll export tool, and a small set of semantic resources for HR and finance workflows.

## What It Adds

- Streamable HTTP MCP endpoint at `/mcp`
- Per-request Odoo Basic Auth
- Temporary in-memory rate limiting per user and tool/resource surface
- JSONL audit log for each tool/resource call with user, model, method, timing, status, and export metadata
- Timeout, retry, redirect, and error classification at the XML-RPC client layer
- Semantic resources for HR companies, departments, payroll runs, and finance journals
- Native HTTPS support for the MCP listener

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp odoo_config.json.example odoo_config.json
cp .env.example .env
```

## Configuration

Required:

- `ODOO_URL`
- `ODOO_DB`

Usually required for local fallback mode:

- `ODOO_USERNAME`
- `ODOO_PASSWORD`

Reliability knobs:

- `ODOO_TIMEOUT`
- `ODOO_RETRY_ATTEMPTS`
- `ODOO_RETRY_BACKOFF_SECONDS`
- `ODOO_RETRY_BACKOFF_MAX_SECONDS`
- `ODOO_MAX_REDIRECTS`
- `ODOO_VERIFY_SSL`

MCP server knobs:

- `MCP_HOST`
- `MCP_PORT`
- `MCP_LOG_LEVEL`
- `MCP_TOOLSETS`
- `MCP_RATE_LIMIT_ENABLED`
- `MCP_RATE_LIMIT_MAX_CALLS`
- `MCP_RATE_LIMIT_WINDOW_SECONDS`
- `MCP_AUDIT_LOG_PATH`

Optional native HTTPS:

- `MCP_SSL_CERTFILE`
- `MCP_SSL_KEYFILE`
- `MCP_SSL_KEYFILE_PASSWORD`

Example TLS setup:

```bash
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout certs/dev.key \
  -out certs/dev.crt \
  -days 365 \
  -subj "/CN=localhost"

export MCP_SSL_CERTFILE="$(pwd)/certs/dev.crt"
export MCP_SSL_KEYFILE="$(pwd)/certs/dev.key"
```

## Run

```bash
python run_server.py
```

Default listener:

```text
http://localhost:6969
```

If TLS is configured:

```text
https://localhost:6969
```

## Endpoints

- `GET /healthz`
- `GET /mcp/health`
- `GET /mcp/config`
- `POST /mcp`

`/mcp` requires HTTP Basic Auth. The username/password are forwarded to Odoo for that request.

## Tools

- `odoo_execute_method`
  Use when the caller already knows the target Odoo `model` and `method`, or when the client wants to explicitly decompose a workflow into Odoo calls.
- `hrm_export_payroll_table`
  Convenience wrapper for payroll-table export. It accepts `run_id` directly, or resolves the payroll batch from `company_id` plus `stage` such as `2026-03`, `03/2026`, or `thang 3 nam 2026`.

## Resources

Generic resources:

- `odoo://server/info`
- `odoo://models`
- `odoo://models/{model}/fields`
- `odoo://records/{model}/{record_id}`

Recipe resources:

- `odoo://guides/execute-method-recipes`
- `odoo://recipes/payroll-export/company-month`

Semantic resources:

- `odoo://domains/hr/companies`
- `odoo://domains/hr/companies/{company_id}`
- `odoo://domains/hr/departments`
- `odoo://domains/hr/departments/{department_id}`
- `odoo://domains/hr/payroll/runs`
- `odoo://domains/hr/payroll/runs/{run_id}`
- `odoo://domains/hr/payroll/company/{company_id}/period/{year}/{month}`
- `odoo://domains/finance/journals`
- `odoo://domains/finance/journals/{journal_id}`

## Export Delivery

`hrm_export_payroll_table` returns the XLSX as an embedded MCP file resource by default. It also saves a server-side copy under:

```text
data/export/<file_name>_run_<run_id>_page_<page>_<records_per_page>_<timestamp>.xlsx
```

If needed, `include_file_content` keeps the base64 fallback in structured content, and `output_path` overrides the server-side save path.

## Observability And Reliability

- Rate limiting is temporary and in-memory.
- Audit logs are written as JSONL to `logs/odoo_audit.jsonl` by default.
- Retry is applied only to transient transport and retryable upstream HTTP failures.
- Authentication, authorization, timeout, connection, protocol, and remote application failures are classified into stable error categories.

## Testing

```bash
pytest
```

Current suite: `40 passed`.

## Related Doc

See [docs/tool_catalog.md](docs/tool_catalog.md) for tool and resource selection guidance.
