# DocType JSON Schema Reference

## Complete DocType JSON Structure

```json
{
  "doctype": "DocType",
  "name": "My DocType",
  "module": "My Module",
  "custom": 0,

  // Type flags
  "istable": 0,              // 1 = child table
  "issingle": 0,             // 1 = single (global settings)
  "is_tree": 0,              // 1 = tree/hierarchical
  "is_virtual": 0,           // 1 = no DB table

  // Behavior
  "is_submittable": 1,       // Enable Submit/Cancel/Amend
  "track_changes": 1,        // Audit log
  "track_views": 0,
  "track_seen": 0,

  // Naming
  "autoname": "naming_series:",   // or "hash", "field:fieldname", "Prompt", "format:{field1}-{field2}"
  "title_field": "title",         // Field shown as document title
  "search_fields": "customer,status",
  "sort_field": "modified",
  "sort_order": "DESC",

  // UI
  "image_field": "image",
  "timeline_field": "customer",   // Groups timeline entries by this
  "max_attachments": 10,

  "fields": [ /* see Field Object Schema */ ],
  "permissions": [ /* see Permissions Object Schema */ ]
}
```

## Field Object Schema

```json
{
  "fieldname": "customer",          // snake_case, unique within DocType
  "label": "Customer",              // Display label
  "fieldtype": "Link",              // See field types reference
  "options": "Customer",            // For Link: target DocType; for Select: newline-separated options; for Table: child DocType name

  // Validation
  "reqd": 0,                        // 1 = mandatory
  "unique": 0,                      // 1 = unique across all records
  "no_copy": 0,                     // 1 = don't copy when duplicating
  "allow_bulk_edit": 0,

  // Display
  "in_list_view": 1,                // Show in list view columns
  "in_standard_filter": 1,          // Show in filter bar
  "in_global_search": 0,            // Include in global search
  "bold": 0,
  "hidden": 0,
  "read_only": 0,
  "print_hide": 0,                  // Hide in print format
  "report_hide": 0,
  "search_index": 0,                // Add DB index for faster search

  // Permissions
  "permlevel": 0,                   // 0=default, 1+ = restricted access level

  // Defaults & Fetch
  "default": "",                    // Default value
  "fetch_from": "customer.customer_name",  // Auto-fetch value from linked doc
  "fetch_if_empty": 1,

  // Descriptions
  "description": "Help text shown below field",
  "placeholder": "Enter value...",

  // Conditional display
  "depends_on": "eval:doc.is_active == 1",   // JS expression

  // For Section/Column Breaks
  "collapsible": 0,                 // 1 = section is collapsible
  "collapsible_depends_on": ""
}
```

## Permissions Object Schema

```json
{
  "role": "Sales User",
  "permlevel": 0,
  "read": 1,
  "write": 1,
  "create": 1,
  "delete": 0,
  "submit": 0,
  "cancel": 0,
  "amend": 0,
  "report": 1,
  "import": 0,
  "export": 1,
  "print": 1,
  "email": 1,
  "share": 1,
  "if_owner": 0            // 1 = permission only applies to own records
}
```

## Naming Series Tokens

| Token | Result |
|-------|--------|
| `.YYYY.` | 4-digit year (2024) |
| `.YY.` | 2-digit year (24) |
| `.MM.` | 2-digit month (01-12) |
| `.DD.` | 2-digit day |
| `.####` | 4-digit auto-increment |
| `.#####` | 5-digit auto-increment |
| `{fieldname}` | Value from that field |

Example: `SO-.YYYY.-.MM.-.####` → `SO-2024-01-0001`

## DocType Controller Events (Python)

```
before_insert → validate → before_save → on_update (save)
before_submit → on_submit
before_cancel → on_cancel
before_update_after_submit → on_update_after_submit
before_trash → on_trash
after_delete
```

## Common frappe.db Patterns

```python
# Get a document
doc = frappe.get_doc("Sales Order", "SO-0001")

# Get a single value
val = frappe.db.get_value("Customer", customer_name, "credit_limit")

# Get multiple values
vals = frappe.db.get_value("Customer", customer_name, ["credit_limit", "payment_terms"])

# SQL query (always use parameterized queries)
rows = frappe.db.sql("""
    SELECT name, total FROM `tabSales Order`
    WHERE status = %s AND company = %s
""", ("Submitted", company), as_dict=True)

# Check exists
if frappe.db.exists("Customer", customer_name):
    ...

# Set value directly (no controller)
frappe.db.set_value("Sales Order", "SO-0001", "status", "Closed")

# Create new doc
new_doc = frappe.new_doc("Payment Entry")
new_doc.payment_type = "Receive"
new_doc.insert()
```
