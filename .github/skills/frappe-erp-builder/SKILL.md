---
name: frappe-erp-builder
description: "Expert Frappe/ERPNext custom app builder. Use this skill whenever a user wants to build, configure, extend, or modify an ERPNext or Frappe-based ERP system. Triggers on any mention of: ERPNext, Frappe, custom app, DocType, workflow, bench, frappe-bench, India compliance, GST integration, custom fields, property setters, roles/permissions, print formats, server scripts, client scripts, naming series, child tables, fixtures, or building a business ERP. Also triggers when a user describes business logic (sales, procurement, HR, manufacturing, etc.) and wants it implemented in Frappe. This skill handles the FULL lifecycle: eliciting requirements, designing architecture, generating code, testing, migrating, and iterating. Always use this skill even for partial tasks like 'add a custom field to Sales Order' or 'set up workflow for Purchase Order'."
argument-hint: "Describe the business logic or ERP requirement you want to build"
---

# Frappe/ERPNext ERP Builder Skill

## Purpose
Guide the agent through building a complete, production-ready custom Frappe/ERPNext app from a plain-English business description. This covers everything: architecture, code generation, compliance (India GST), permissions, workflows, testing, and bench operations.

## Reference Files
Load these as needed during each phase:
- [DocType JSON Schema](./references/doctype-schema.md) — Full DocType JSON schema with all field options
- [Field Types Guide](./references/field-types.md) — Every field type with use cases and options
- [India Compliance](./references/india-compliance.md) — GST, TDS, e-Invoice, e-Waybill complete guide
- [hooks.py Reference](./references/hooks-reference.md) — All available hooks.py events and patterns

---

## Phase 0 — Requirement Elicitation

Before writing any code, **ask the user a structured set of questions**. Do NOT skip this even if the user gave a long description — gaps will cost time later.

### Required Questions (ask all at once, grouped):

**Business & Scope**
1. What industry/business type? (Manufacturing, Trading, Services, Retail, etc.)
2. Which ERPNext modules will you use? (Accounts, HR, Inventory, Manufacturing, CRM, Projects, etc.)
3. Is this India-based? (triggers India Compliance / GST setup)
4. Fresh install or extending existing ERPNext?
5. Frappe version? (v14, v15 — matters for API differences)

**Core Entities**
6. List the main business objects (e.g., "Sales Order, Delivery Note, Customer, Vendor, Item")
7. For each entity: what are the key fields? Any special validations?
8. Which DocTypes need child tables? (e.g., line items in an invoice)
9. Any Single DocTypes needed (global settings)?

**Workflows & States**
10. For each main DocType: what are the lifecycle states? (Draft → Submitted → Cancelled, or custom like Lead → Qualified → Won)
11. Who approves what? (defines workflow transitions + roles)
12. Any auto-actions on state change? (emails, stock updates, ledger entries)

**Permissions & Roles**
13. List all user roles needed (e.g., Sales Manager, Accounts User, Warehouse Staff)
14. For each role: which DocTypes can they Read / Write / Create / Delete / Submit / Cancel / Amend?
15. Any field-level restrictions? (e.g., price field hidden from warehouse staff)

**Integrations & Compliance**
16. India Compliance needed? (GST, TDS, e-Invoice, e-Waybill)
17. Any payment gateway, SMS, or third-party integrations?
18. Custom print formats needed? Which documents?

**Automation**
19. Any auto-naming rules? (e.g., "SO-YYYY-MM-####")
20. Notifications/alerts? (on submit, on status change, overdue reminders)
21. Any scheduled jobs? (nightly stock reports, auto-invoice generation)

Once answers are collected, proceed to Phase 1.

---

## Phase 1 — Architecture Design

### 1.1 App Scaffold
```bash
# From frappe-bench directory
bench new-app {app_name}
bench --site {site_name} install-app {app_name}
```

### 1.2 DocType Planning Matrix
Build this matrix before creating anything:

| DocType Name | Type | Submittable | Parent DocType (if child) | Naming Series | Key Fields | Linked To |
|---|---|---|---|---|---|---|

**DocType Types:**
- `Document` — standard records
- `Child Table` — embedded rows inside a parent
- `Single` — one global record (settings)
- `Tree` — hierarchical (Chart of Accounts, Territory)
- `Virtual` — no DB table, computed on-the-fly

### 1.3 Module Structure
```
{app_name}/
├── {app_name}/
│   ├── {module_name}/
│   │   ├── doctype/
│   │   │   └── {doctype_name}/
│   │   │       ├── {doctype_name}.json   ← DocType definition
│   │   │       ├── {doctype_name}.py     ← Server-side controller
│   │   │       ├── {doctype_name}.js     ← Client-side controller
│   │   │       └── test_{doctype_name}.py
│   │   └── __init__.py
│   ├── hooks.py
│   ├── config/
│   │   ├── desktop.py
│   │   └── docs.py
│   └── fixtures/         ← exported config (roles, custom fields, workflows)
```

---

## Phase 2 — DocType Creation

Read [DocType JSON Schema](./references/doctype-schema.md) and [Field Types Guide](./references/field-types.md) before generating code.

Key rules:
- `istable: 1` for child tables
- `is_submittable: 1` for documents that need Submit/Cancel
- `track_changes: 1` for audit trail
- `autoname` options: `"naming_series:"`, `"field:fieldname"`, `"hash"`, `"Prompt"`

### 2.1 Controller (Python) Template
```python
import frappe
from frappe.model.document import Document
from frappe import _

class {DocTypeName}(Document):

    def validate(self):
        """Runs on Save (draft). Put validations here."""
        self.validate_mandatory_fields()
        self.calculate_totals()

    def before_submit(self):
        """Runs before Submit. Raise exceptions to block."""
        if not self.items:
            frappe.throw(_("Cannot submit without items"))

    def on_submit(self):
        """Runs after Submit. Make ledger entries, stock moves, etc."""
        self.update_stock()
        self.make_gl_entries()

    def on_cancel(self):
        """Reverse on_submit effects."""
        self.cancel_gl_entries()

    def on_trash(self):
        """Before deletion."""
        pass

    def validate_mandatory_fields(self):
        pass

    def calculate_totals(self):
        self.total = sum(row.amount for row in self.items)
```

### 2.2 Client Script Template (JS)
```javascript
frappe.ui.form.on('{DocType Name}', {
    refresh(frm) {
        if (frm.doc.status === 'Approved') {
            frm.add_custom_button(__('Create Invoice'), () => {
                frm.call('make_invoice').then(r => {
                    if (r.message) frappe.set_route('Form', 'Sales Invoice', r.message);
                });
            }, __('Create'));
        }
    },

    onload(frm) {
        frm.set_query('warehouse', () => ({
            filters: { company: frm.doc.company }
        }));
    },

    quantity(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, 'amount', row.quantity * row.rate);
        frm.refresh_field('items');
    }
});

frappe.ui.form.on('{Child DocType Name}', {
    rate(frm, cdt, cdn) {
        // recalculate row total
    }
});
```

---

## Phase 3 — Workflows

### Workflow JSON Structure
```json
{
  "doctype": "Workflow",
  "name": "{DocType} Approval",
  "document_type": "{DocType Name}",
  "is_active": 1,
  "states": [
    {"state": "Draft",     "doc_status": "0", "style": ""},
    {"state": "Pending",   "doc_status": "0", "style": "orange"},
    {"state": "Approved",  "doc_status": "1", "style": "green"},
    {"state": "Rejected",  "doc_status": "2", "style": "red"}
  ],
  "transitions": [
    {
      "state": "Draft",
      "action": "Submit for Approval",
      "next_state": "Pending",
      "allowed": "Sales User",
      "allow_self_approval": 1
    },
    {
      "state": "Pending",
      "action": "Approve",
      "next_state": "Approved",
      "allowed": "Sales Manager",
      "condition": "doc.total <= 100000"
    },
    {
      "state": "Pending",
      "action": "Reject",
      "next_state": "Rejected",
      "allowed": "Sales Manager"
    }
  ]
}
```

Rules:
- `doc_status: "0"` = Draft/Saved, `"1"` = Submitted, `"2"` = Cancelled
- `condition` supports Python expressions using `doc.fieldname`
- Workflow overrides the standard Submit button — user sees action buttons instead

---

## Phase 4 — Permissions

### Role-Based Permissions in DocType JSON
```json
"permissions": [
    {
        "role": "Sales User",
        "read": 1, "write": 1, "create": 1, "delete": 0,
        "submit": 0, "cancel": 0, "amend": 0,
        "report": 1, "import": 0, "export": 1, "print": 1, "email": 1
    },
    {
        "role": "Sales Manager",
        "read": 1, "write": 1, "create": 1, "delete": 1,
        "submit": 1, "cancel": 1, "amend": 1,
        "report": 1, "import": 1, "export": 1, "print": 1, "email": 1
    }
]
```

### User Permissions (Row-level)
```python
frappe.get_doc({
    "doctype": "User Permission",
    "user": "user@example.com",
    "allow": "Company",
    "for_value": "My Company Ltd"
}).insert()
```

### Field-Level Permissions
Use **Property Setters** or `permlevel` on fields:
```json
{"fieldname": "base_rate", "permlevel": 1}
```
Then assign permlevel 1 permissions only to Manager roles.

---

## Phase 5 — Custom Fields & Property Setters

### Custom Fields (extending standard DocTypes)
```python
frappe.get_doc({
    "doctype": "Custom Field",
    "dt": "Sales Order",
    "fieldname": "custom_po_ref",
    "label": "Customer PO Reference",
    "fieldtype": "Data",
    "insert_after": "customer",
    "in_list_view": 1,
    "in_standard_filter": 1
}).insert()
```

### Property Setters (override existing field properties)
```python
frappe.get_doc({
    "doctype": "Property Setter",
    "doc_type": "Sales Order",
    "field_name": "delivery_date",
    "property": "reqd",
    "value": "1",
    "property_type": "Check"
}).insert()
```

Common properties: `hidden`, `reqd`, `read_only`, `default`, `options`, `label`, `description`

### Export as Fixtures
```python
# hooks.py
fixtures = [
    "Custom Field",
    "Property Setter",
    "Workflow",
    "Role",
    {"dt": "Print Format", "filters": [["module", "=", "Your Module"]]},
]
```
Then: `bench --site {site} export-fixtures`

---

## Phase 6 — India Compliance (GST)

Read [India Compliance Reference](./references/india-compliance.md) for the full GST setup guide.

Quick Setup:
```bash
bench get-app india_compliance
bench --site {site} install-app india_compliance
bench --site {site} migrate
```

Key configurations: GSTIN on Company, HSN/SAC codes on Items, GST Tax Templates, GST Category on Customer/Supplier, e-Invoice setup, e-Waybill auto-generation.

---

## Phase 7 — Naming Series

```python
# In DocType JSON
"autoname": "naming_series:",
"fields": [
    {
        "fieldname": "naming_series",
        "fieldtype": "Select",
        "options": "SO-.YYYY.-.MM.-.####\nSALES-.####",
        "default": "SO-.YYYY.-.MM.-.####"
    }
]
```

Tokens: `.YYYY.` (year), `.MM.` (month), `.DD.` (day), `.####` (auto-increment), `{fieldname}` (field value)

---

## Phase 8 — Server Scripts & Scheduled Jobs

### Server Script (no-deploy automation)
```python
# Via Frappe UI: Server Script > "DocType Event"
if doc.total > 500000:
    doc.requires_approval = 1
    frappe.sendmail(
        recipients=["cfo@company.com"],
        subject=f"High Value Order {doc.name}",
        message=f"Order {doc.name} for {doc.total} requires your approval"
    )
```

### Scheduled Job in hooks.py
```python
scheduler_events = {
    "daily": ["myapp.tasks.daily_tasks"],
    "weekly": ["myapp.tasks.weekly_report"],
    "cron": {
        "0 9 * * 1-5": ["myapp.tasks.morning_digest"]
    }
}
```

---

## Phase 9 — Print Formats

### Jinja2 HTML Print Format
```html
<div class="print-format">
    <h2>{{ doc.name }}</h2>
    <table class="table table-bordered">
        <thead>
            <tr><th>Item</th><th>Qty</th><th>Rate</th><th>Amount</th></tr>
        </thead>
        <tbody>
        {% for row in doc.items %}
            <tr>
                <td>{{ row.item_name }}</td>
                <td>{{ row.qty }}</td>
                <td>{{ frappe.format(row.rate, 'Currency') }}</td>
                <td>{{ frappe.format(row.amount, 'Currency') }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    <p><strong>Total: {{ frappe.format(doc.total, 'Currency') }}</strong></p>
</div>
```

---

## Phase 10 — Bench Commands Reference

### Essential commands
```bash
bench --site {site} migrate          # After DocType/schema changes
bench build                          # Build JS/CSS assets
bench --site {site} clear-cache      # After config changes
bench restart                        # Restart workers
bench --site {site} console          # Interactive Python console
bench --site {site} export-fixtures  # Export fixtures
bench --site {site} backup --with-files
bench --site {site} enable-scheduler
```

### When to run what
| Action | Command |
|---|---|
| Added/changed a DocType | `migrate` then `clear-cache` |
| Changed hooks.py | `restart` |
| Changed JS/CSS | `build` then hard-refresh browser |
| Changed Python | `restart` (or auto-reload in dev) |
| Added fixtures | `export-fixtures` then commit |
| Permission issues | `clear-cache` |
| Scheduler not running | `enable-scheduler`, then `restart` |

---

## Phase 11 — Testing

### Run tests
```bash
bench --site {site} run-tests --app {app_name}
bench --site {site} run-tests --doctype "{DocType Name}"
```

### Test file template
```python
import frappe
import unittest
from frappe.tests.utils import FrappeTestCase

class Test{DocTypeName}(FrappeTestCase):

    def test_creation(self):
        doc = frappe.get_doc({
            "doctype": "{DocType Name}",
            "field1": "value1",
        })
        doc.insert()
        self.assertEqual(doc.status, "Draft")

    def test_validation(self):
        doc = frappe.get_doc({"doctype": "{DocType Name}"})
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_submit_flow(self):
        doc = make_test_doc()
        doc.submit()
        self.assertEqual(doc.docstatus, 1)
        doc.cancel()
        self.assertEqual(doc.docstatus, 2)

def make_test_doc():
    return frappe.get_doc({...}).insert()
```

### What to test
- [ ] DocType creates without error
- [ ] Mandatory field validation works
- [ ] Custom validations raise correct errors
- [ ] Submit sets correct status and docstatus
- [ ] Cancel reverses all on_submit effects
- [ ] Permissions: user without role cannot access
- [ ] Workflow transitions work correctly
- [ ] Calculated fields are correct
- [ ] Naming series generates correctly
- [ ] GST fields populate correctly (if India Compliance)

---

## Phase 12 — Iterative Modification Protocol

When user requests changes to existing code:

1. **Identify impact scope**: Which DocTypes, controllers, fixtures are affected?
2. **Check for data migrations needed**: Adding non-nullable fields? Changing field types?
3. **Update in correct order**:
   - DocType JSON first
   - Python controller
   - JS controller
   - Fixtures
   - Run `migrate` → `clear-cache` → `restart`
4. **Test after each change**

### MariaDB direct access (use carefully)
```bash
bench --site {site} mariadb

-- Check table structure
DESCRIBE `tab{DocType Name}`;

-- Check data
SELECT name, status, total FROM `tabSales Order` LIMIT 10;
```

> Never modify schema directly in production. Use DocType + migrate instead. Direct SQL is only for debugging or emergency data fixes.

---

## Execution Checklist

For every new ERP build, verify:

- [ ] App created and installed on site
- [ ] All DocTypes created with correct types
- [ ] Child tables linked to parents
- [ ] Naming series configured
- [ ] All roles created
- [ ] Permissions set on every DocType for every role
- [ ] Workflows created for submittable DocTypes
- [ ] Custom fields added to standard DocTypes
- [ ] Property Setters applied
- [ ] India Compliance installed and GSTIN configured (if applicable)
- [ ] Print formats created for customer-facing docs
- [ ] Notifications set up
- [ ] Fixtures exported and committed to git
- [ ] All tests passing
- [ ] `bench migrate` run cleanly
- [ ] Cache cleared
- [ ] End-to-end flow tested manually
