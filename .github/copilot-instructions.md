# Kaiten ERP — Copilot Instructions

## Project Overview

**Kaiten ERP** is a custom Frappe v16 app (`kaiten_erp`) for solar installation project management built on ERPNext. It extends standard ERPNext DocTypes (Lead, Sales Order, Quotation, Delivery Note, etc.) with custom fields and adds custom DocTypes for a 6-stage **execution chain** workflow.

- **Bench directory:** `/home/lakshya/temp/dev-bench`
- **App directory:** `apps/kaiten_erp`
- **Site:** `dev-bench` (single-site setup)
- **Python:** ≥ 3.14 | **Frappe:** v16 | **Linting:** ruff + eslint + prettier
- **Formatting:** tabs for indent, double quotes, line-length 110

## Architecture

### Module Structure

```
kaiten_erp/
├── kaiten_erp/            # outer package (app root)
│   ├── hooks.py           # all hooks, fixtures, doc_events, permissions
│   ├── patches.txt        # migration patch registry
│   ├── modules.txt        # "Kaiten Erp"
│   ├── fixtures/          # exported JSON (Custom Field, Property Setter, Workflow, etc.)
│   ├── patches/           # one-off migration scripts
│   ├── public/            # JS client scripts & CSS
│   │   ├── js/            # per-doctype client scripts loaded via doctype_js in hooks.py
│   │   └── css/
│   └── kaiten_erp/        # inner module ("Kaiten Erp" module)
│       ├── api/           # whitelisted APIs & shared server logic
│       ├── cron_job/      # scheduler tasks
│       ├── doc_events/    # doc_events handlers (one file per doctype)
│       ├── doctype/       # custom DocType definitions (JSON + controller)
│       ├── permissions/   # has_permission & permission_query_conditions
│       └── workspace/     # desk workspace JSON definitions
```

### Execution Chain (core domain model)

The solar installation lifecycle flows through 6 stages — each is its own custom DocType:

```
Technical Survey → Structure Mounting → Project Installation → Meter Installation → Meter Commissioning → Verification Handover
```

All execution DocTypes:
- Link back to a **Job File** via `custom_job_file`
- Share a common `validate` + `on_update` pattern in `doc_events/execution_events.py`
- Use `api/execution_chain_todo.py` for ToDo creation on workflow state changes
- Use `api/execution_payment_validation.py` for payment checks before progression
- Have role-based permissions for **Vendor Manager**, **Vendor Executive**, **Vendor Head**
- Have workflow states managed via Frappe Workflows (exported as fixtures)

### Key Custom Roles

`Vendor Manager` · `Vendor Executive` · `Vendor Head` · `Sales Executive`

### Extended Standard DocTypes

Lead, Sales Order, Quotation, Sales Invoice, Delivery Note, Material Request, Stock Entry, Payment Entry, Supplier — all extended via custom fields (`module = "Kaiten Erp"`).

## Conventions

### Python

- **Doc events:** One file per doctype in `kaiten_erp/kaiten_erp/doc_events/`, named `{doctype_name}_events.py`. Register in `hooks.py → doc_events`.
- **APIs:** Shared logic in `kaiten_erp/kaiten_erp/api/`. Use `@frappe.whitelist()` for callable endpoints.
- **Permissions:** Per-doctype permission files in `kaiten_erp/kaiten_erp/permissions/`. Registered in `hooks.py → permission_query_conditions` and `has_permission`.
- **Patches:** Add file in `kaiten_erp/patches/`, register in `kaiten_erp/patches.txt` under `[post_model_sync]`.
- **DB queries:** Always use parameterized queries (`%s` placeholders) in `frappe.db.sql()`. Never use string interpolation.
- **ToDo creation:** Follow the pattern in `api/execution_chain_todo.py` — always check for duplicates, always set `role` field, always resolve `allocated_to` to an enabled User. See the `todo-creator` agent for details.

### JavaScript

- Client scripts live in `public/js/{doctype_name}.js` and are registered in `hooks.py → doctype_js`.
- Use Frappe client API (`frappe.call`, `cur_frm.set_value`, `frappe.ui.form.on`).

### Fixtures

- Exported via `bench export-fixtures` into `kaiten_erp/fixtures/`.
- Fixture filters are defined in `hooks.py → fixtures` list.
- Custom fields use `module = "Kaiten Erp"` filter.
- Property setters filter by the `DOCTYPES` list + extended standard DocTypes defined at the top of hooks.py.
- **Always run `bench export-fixtures` after UI changes to custom fields, property setters, workflows, or permissions.**

### Patches

- File goes in `kaiten_erp/patches/` as a standalone `.py` with an `execute()` function.
- Each patch is registered in `kaiten_erp/patches.txt` under `[post_model_sync]`.
- Patches run once per site during `bench migrate`.

## Build & Run Commands

```bash
# From bench directory: /home/lakshya/temp/dev-bench

bench start                          # start dev server
bench migrate                        # run migrations + patches
bench --site dev-bench clear-cache   # clear after permission/config changes
bench export-fixtures                # export fixtures to JSON (run from app dir)
bench build                          # rebuild JS/CSS assets
bench restart                        # restart workers (production)
bench console                        # interactive Python shell with frappe context
```

### Typical change workflow

1. Edit DocType JSON / Python / JS files
2. `bench migrate` (syncs schema + runs new patches)
3. `bench --site dev-bench clear-cache`
4. If fixtures changed: `cd apps/kaiten_erp && bench export-fixtures`
5. Test in browser

## Pitfalls & Gotchas

- **Double module nesting:** The inner module path is `kaiten_erp.kaiten_erp.{subpackage}` (app name = module name). Don't forget the double `kaiten_erp`.
- **Fixture ordering:** DocType fixtures must export before Property Setter fixtures that reference them. The `DOCTYPES` list at the top of hooks.py controls which DocTypes' property setters are exported.
- **Custom field naming:** Frappe auto-prefixes custom fields with `custom_`. When referencing in code, always use `custom_` prefix (e.g., `doc.custom_job_file`).
- **Workflow + doc_events:** Workflow state transitions trigger `on_update`. The execution chain uses this to `create_next_stage()` and manage ToDos.
- **Permission layers:** Both `has_permission` (per-doc check) and `permission_query_conditions` (list filter SQL) must be implemented for each restricted DocType.
- **Payment validation:** `execution_payment_validation.py` blocks execution stage progression if payments are incomplete — runs during `validate`.

## Custom DocTypes

### Execution Chain DocTypes
`Technical Survey` · `Structure Mounting` · `Project Installation` · `Meter Installation` · `Meter Commissioning` · `Verification Handover`

### Supporting DocTypes
`Job File` · `Payment Milestone` · `Procurement Consolidation` · `Procurement Shortage Log` · `Stock Reservation Log` · `Location Log` · `Photo Log` · `Discom Master` · `Discom Linked Customer` · `Payment Milestone Template`

### Child Tables
`Supplier Territory Child Table` · `Payment Control Child Table` · `Job Execution Child Table` · `Revisist Log Child Table` · `Material Line Child Table` · `Consolidated Procurement Item` · `Sales Person Territory Child Table` · `Tax Bifurcation Child Table`

## Key API Modules

| File | Purpose |
|---|---|
| `api/execution_actions.py` | `create_next_stage()` — auto-creates next execution DocType |
| `api/execution_chain_todo.py` | ToDo creation/close on execution workflow transitions |
| `api/execution_payment_validation.py` | Blocks stage progression if payments incomplete |
| `api/execution_workflow.py` | Workflow state management helpers |
| `api/job_file_workflow.py` | Job File workflow transitions |
| `api/bom_stock_reservation.py` | Stock reservation on Sales Order submit/cancel |
| `api/profitability.py` | Profitability calculations for quotations |
| `api/sales_order_bom.py` | BOM management for Sales Orders |
| `api/milestone_invoice_manager.py` | Payment milestone invoice operations |
| `api/gps.py` | GPS/location tracking for field operations |
| `api/supplier_portal.py` | Supplier-facing portal APIs |

## Doc Events Registry

Key event handlers registered in `hooks.py → doc_events`:

- **Lead:** `on_update` → `lead_events`
- **Job File:** `on_update`, `on_trash` → `JobFile_events`
- **Sales Order:** `validate`, `on_update`, `on_submit`, `on_update_after_submit`, `on_cancel` → `sales_order_events` + `bom_stock_reservation`
- **Quotation:** `validate`, `on_update`, `on_submit`, `on_update_after_submit` → `quotation_events`
- **Sales Invoice:** `before_insert`, `validate`, `on_submit`, `on_cancel` → `sales_invoice_events`
- **Delivery Note:** `before_insert`, `on_submit`, `on_cancel` → `delivery_note_events`
- **Payment Entry:** `on_submit`, `on_cancel` → `payment_entry_events`
- **Execution DocTypes:** `validate` → `execution_events` + payment validation; `on_update` → `execution_events` + `execution_chain_todo`

## Scheduler

Backups run via cron at 9, 12, 15, 18, 21 hours daily (`cron_job/hourly_backup.py`).

## Related Customizations

- **Skill:** `frappe-erp-builder` — Full ERP build lifecycle (elicitation → architecture → code → test). See `.github/skills/frappe-erp-builder/SKILL.md`.
- **Agent:** `frappe-erp-builder` — Frappe/ERPNext builder and configurator. See `.github/agents/frappe-erp-builder.agent.md`.
- **Agent:** `todo-creator` — Specialized for Frappe ToDo creation patterns. See `.github/agents/todo-creator.agent.md`.
- **Repo memory:** `project_installation_structure.md` — Detailed field map for Project Installation DocType


For more deep context read file [DeepContext][deepContextReference]

[deepContextReference]: ../Skills/DEEP_CONTEXT.md