# Odoo Query Model Report

Generated at 2026-04-16 07:05:21 UTC

## Scope

- `src/odoo_mcp/tools/access.py`
- `src/odoo_mcp/tools/finance.py`
- `src/odoo_mcp/tools/hrm.py`

## Models

- Existing models resolved from Odoo metadata: 19
- Missing models referenced by code in this database: 4
  - `attendance`
  - `hr.attendance.daily`
  - `hr.daily.attendance`
  - `hr.payslip.worked_days`

## Relationships

Relationships below are live `fields_get` many2one/one2many/many2many links limited to fields explicitly requested by the code queries.

- `account.journal.company_id` -> `res.company` (N:1; Journal -> Company)
- `account.move.journal_id` -> `account.journal` (N:1; Journal Entry / Invoice -> Journal)
- `account.move.invoice_line_ids` -> `account.move.line` (1:N; Journal Entry / Invoice -> Journal Item)
- `account.move.company_id` -> `res.company` (N:1; Journal Entry / Invoice -> Company)
- `account.move.partner_id` -> `res.partner` (N:1; Journal Entry / Invoice -> Partner)
- `account.move.line.account_id` -> `account.account` (N:1; Journal Item -> Account)
- `account.payment.journal_id` -> `account.journal` (N:1; Payment -> Journal)
- `account.payment.reconciled_invoice_ids` -> `account.move` (M:N; Payment -> Journal Entry / Invoice)
- `account.payment.partner_id` -> `res.partner` (N:1; Payment -> Partner)
- `hr.attendance.employee_id` -> `hr.employee` (N:1; Attendance -> Employee)
- `hr.contract.department_id` -> `hr.department` (N:1; Contract -> Department)
- `hr.contract.khoi_id` -> `hr.department` (N:1; Contract -> Department)
- `hr.contract.phong_id` -> `hr.department` (N:1; Contract -> Department)
- `hr.contract.employee_id` -> `hr.employee` (N:1; Contract -> Employee)
- `hr.contract.company_id` -> `res.company` (N:1; Contract -> Company)
- `hr.department.parent_id` -> `hr.department` (N:1; Department -> Department)
- `hr.department.manager_id` -> `hr.employee` (N:1; Department -> Employee)
- `hr.department.company_id` -> `res.company` (N:1; Department -> Company)
- `hr.employee.department_id` -> `hr.department` (N:1; Employee -> Department)
- `hr.employee.coach_id` -> `hr.employee` (N:1; Employee -> Employee)
- `hr.employee.parent_id` -> `hr.employee` (N:1; Employee -> Employee)
- `hr.employee.company_id` -> `res.company` (N:1; Employee -> Company)
- `hr.employee.address_id` -> `res.partner` (N:1; Employee -> Partner)
- `hr.leave.employee_id` -> `hr.employee` (N:1; Leave -> Employee)
- `hr.leave.allocation.employee_id` -> `hr.employee` (N:1; Leave Allocation -> Employee)
- `hr.payslip.employee_id` -> `hr.employee` (N:1; Payslip -> Employee)
- `hr.payslip.company_id` -> `res.company` (N:1; Payslip -> Company)
- `hr.payslip.line.slip_id` -> `hr.payslip` (N:1; Payslip Line -> Payslip)
- `hr.payslip.line.salary_rule_id` -> `hr.salary.rule` (N:1; Payslip Line -> Salary Rule)
- `hr.work.entry.contract_id` -> `hr.contract` (N:1; Work Entry -> Contract)
- `hr.work.entry.employee_id` -> `hr.employee` (N:1; Work Entry -> Employee)
- `hr.work.entry.work_entry_type_id` -> `hr.work.entry.type` (N:1; Work Entry -> Work Entry Type)
- `res.company.parent_id` -> `res.company` (N:1; Company -> Company)
- `res.partner.child_ids` -> `res.partner` (1:N; Partner -> Partner)
- `res.users.company_id` -> `res.company` (N:1; User -> Company)
- `res.users.company_ids` -> `res.company` (M:N; User -> Company)

## Query Process

### `access.get_company_scope`

1. `read_records` on `res.users` ([src/odoo_mcp/tools/access.py:75]) - ok
2. `read_records` on `res.company` ([src/odoo_mcp/tools/access.py:88]) - ok

### `access.get_department_visibility`

1. `search_read` on `hr.department` ([src/odoo_mcp/tools/access.py:125]) - ok
2. `search_read` on `hr.department` ([src/odoo_mcp/tools/access.py:155]) - ok

### `access.get_access_scope`

1. `read_records` on `res.users` ([src/odoo_mcp/tools/access.py:75]) - ok
2. `read_records` on `res.company` ([src/odoo_mcp/tools/access.py:88]) - ok
3. `search_read` on `hr.department` ([src/odoo_mcp/tools/access.py:125]) - ok
4. `search_read` on `hr.department` ([src/odoo_mcp/tools/access.py:155]) - ok

### `finance.search_invoices`

1. `search_read` on `account.move` ([src/odoo_mcp/tools/finance.py:45]) - ok

### `finance.get_invoice`

1. `read_records` on `account.move` ([src/odoo_mcp/tools/finance.py:70]) - ok
2. `read_records` on `account.move.line` ([src/odoo_mcp/tools/finance.py:89]) - ok

### `finance.search_payments`

1. `search_read` on `account.payment` ([src/odoo_mcp/tools/finance.py:136]) - ok

### `finance.search_journal_entries`

1. `search_read` on `account.move` ([src/odoo_mcp/tools/finance.py:181]) - ok

### `finance.search_partners`

1. `search_read` on `res.partner` ([src/odoo_mcp/tools/finance.py:223]) - ok

### `finance.get_partner`

1. `read_records` on `res.partner` ([src/odoo_mcp/tools/finance.py:242]) - ok

### `finance.get_account_balance`

1. `read_records` on `account.account` ([src/odoo_mcp/tools/finance.py:282]) - ok
2. `search_read` on `account.account` ([src/odoo_mcp/tools/finance.py:289]) - ok
3. `search_read` on `account.move.line` ([src/odoo_mcp/tools/finance.py:311]) - ok

### `finance.list_journals`

1. `search_read` on `account.journal` ([src/odoo_mcp/tools/finance.py:341]) - ok

### `hrm.search_employees`

1. `search_read` on `hr.employee` ([src/odoo_mcp/tools/hrm.py:646]) - ok

### `hrm.get_employee`

1. `read_records` on `hr.employee` ([src/odoo_mcp/tools/hrm.py:677]) - ok

### `hrm.list_departments`

1. `search_read` on `hr.department` ([src/odoo_mcp/tools/hrm.py:700]) - ok

### `hrm.get_employee_contracts`

1. `search_read` on `hr.contract` ([src/odoo_mcp/tools/hrm.py:729]) - ok

### `hrm.search_leaves`

1. `search_read` on `hr.leave` ([src/odoo_mcp/tools/hrm.py:767]) - ok

### `hrm.get_leave_allocation`

1. `search_read` on `hr.leave.allocation` ([src/odoo_mcp/tools/hrm.py:795]) - ok

### `hrm.search_attendance`

1. `search_read` on `hr.attendance` ([src/odoo_mcp/tools/hrm.py:834]) - ok

### `hrm.summarize_attendance_work_days_by_type`

1. `search_read` on `hr.employee` ([src/odoo_mcp/tools/hrm.py:879]) - ok
2. `search_read` on `hr.contract` ([src/odoo_mcp/tools/hrm.py:431]) - ok
3. `search_read` on `hr.attendance` ([src/odoo_mcp/tools/hrm.py:935]) - ok
4. `search_read` on `hr.attendance.daily` ([src/odoo_mcp/tools/hrm.py:935]) - missing in db
5. `search_read` on `hr.daily.attendance` ([src/odoo_mcp/tools/hrm.py:935]) - missing in db
6. `search_read` on `attendance` ([src/odoo_mcp/tools/hrm.py:935]) - missing in db

### `hrm.search_payslips`

1. `get_model_fields` on `hr.payslip` ([src/odoo_mcp/tools/hrm.py:1038]) - ok
2. `search_read` on `hr.payslip` ([src/odoo_mcp/tools/hrm.py:1042]) - ok

### `hrm.list_work_entry_types`

1. `search_read` on `hr.work.entry.type` ([src/odoo_mcp/tools/hrm.py:1061]) - ok

### `hrm.get_work_entries`

1. `search_read` on `hr.work.entry` ([src/odoo_mcp/tools/hrm.py:1110]) - ok

### `hrm.get_payslip_worked_days`

1. `search_read` on `hr.payslip.worked_days` ([src/odoo_mcp/tools/hrm.py:1136]) - missing in db

### `hrm.get_payslip_lines`

1. `search_read` on `hr.payslip` ([src/odoo_mcp/tools/hrm.py:1179]) - ok
2. `search_read` on `hr.payslip.line` ([src/odoo_mcp/tools/hrm.py:1200]) - ok

### `hrm.build_payslip_excel_export_context`

1. `search_read` on `hr.payslip` ([src/odoo_mcp/tools/hrm.py:1251]) - ok
2. `search_read` on `hr.payslip.line` ([src/odoo_mcp/tools/hrm.py:1261]) - ok
3. `search_read` on `hr.contract` ([src/odoo_mcp/tools/hrm.py:368]) - ok
4. `read_records` on `hr.employee` ([src/odoo_mcp/tools/hrm.py:584]) - ok
5. `search_read` on `hr.attendance` ([src/odoo_mcp/tools/hrm.py:543]) - ok
6. `search_read` on `hr.attendance.daily` ([src/odoo_mcp/tools/hrm.py:543]) - missing in db
7. `search_read` on `hr.daily.attendance` ([src/odoo_mcp/tools/hrm.py:543]) - missing in db
8. `search_read` on `attendance` ([src/odoo_mcp/tools/hrm.py:543]) - missing in db

### `hrm.export_payslip_lines_excel`

1. `search_read` on `hr.payslip` ([src/odoo_mcp/tools/hrm.py:1251]) - ok
2. `search_read` on `hr.payslip.line` ([src/odoo_mcp/tools/hrm.py:1261]) - ok
3. `search_read` on `hr.contract` ([src/odoo_mcp/tools/hrm.py:368]) - ok
4. `read_records` on `hr.employee` ([src/odoo_mcp/tools/hrm.py:584]) - ok
5. `search_read` on `hr.attendance` ([src/odoo_mcp/tools/hrm.py:543]) - ok
6. `search_read` on `hr.attendance.daily` ([src/odoo_mcp/tools/hrm.py:543]) - missing in db
7. `search_read` on `hr.daily.attendance` ([src/odoo_mcp/tools/hrm.py:543]) - missing in db
8. `search_read` on `attendance` ([src/odoo_mcp/tools/hrm.py:543]) - missing in db

### `hrm.list_salary_rules`

1. `search_read` on `hr.salary.rule` ([src/odoo_mcp/tools/hrm.py:1440]) - ok

### `hrm.get_daily_attendance`

1. `search_read` on `hr.employee` ([src/odoo_mcp/tools/hrm.py:1516]) - ok
2. `search_read` on `hr.attendance.daily` ([src/odoo_mcp/tools/hrm.py:1537]) - missing in db
3. `search_read` on `hr.daily.attendance` ([src/odoo_mcp/tools/hrm.py:1555]) - missing in db
