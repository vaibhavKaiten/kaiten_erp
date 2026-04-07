# hooks.py Reference — All Available Hooks

## Core hooks.py Structure

```python
app_name = "my_app"
app_title = "My App"
app_publisher = "My Company"
app_description = "Custom ERP for My Business"
app_email = "dev@mycompany.com"
app_license = "MIT"

app_version = "1.0.0"
required_apps = ["erpnext"]   # dependencies
```

---

## DocType Events (Override or extend controllers)

```python
doc_events = {
    "Sales Order": {
        "on_submit": "myapp.overrides.sales_order.on_submit",
        "on_cancel": "myapp.overrides.sales_order.on_cancel",
        "validate": "myapp.overrides.sales_order.validate",
        "before_save": "myapp.overrides.sales_order.before_save",
    },
    "Payment Entry": {
        "on_submit": "myapp.overrides.payment.on_submit",
    },
    "*": {
        # Applies to ALL doctypes
        "after_insert": "myapp.hooks_handler.after_any_insert"
    }
}
```

Available events: `before_insert`, `after_insert`, `validate`, `before_save`, `on_update`, `before_submit`, `on_submit`, `before_cancel`, `on_cancel`, `on_update_after_submit`, `before_trash`, `on_trash`, `after_delete`, `before_rename`, `after_rename`

---

## Override Classes (Replace standard controller)

```python
override_doctype_class = {
    "Sales Order": "myapp.overrides.CustomSalesOrder",
}
```

```python
# myapp/overrides.py
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder

class CustomSalesOrder(SalesOrder):
    def validate(self):
        super().validate()
        self.custom_validate()

    def custom_validate(self):
        if self.custom_field > 1000:
            frappe.throw("Custom Field cannot exceed 1000")
```

---

## Scheduled Tasks

```python
scheduler_events = {
    "all": [
        "myapp.tasks.all"              # Every ~5 minutes
    ],
    "hourly": [
        "myapp.tasks.hourly"
    ],
    "daily": [
        "myapp.tasks.daily"
    ],
    "weekly": [
        "myapp.tasks.weekly"
    ],
    "monthly": [
        "myapp.tasks.monthly"
    ],
    "cron": {
        "0 9 * * 1-5": [               # 9am Mon-Fri
            "myapp.tasks.morning_report"
        ],
        "*/30 * * * *": [              # Every 30 mins
            "myapp.tasks.sync_data"
        ]
    },
    "hourly_long": ["myapp.tasks.hourly_long"],
    "daily_long": ["myapp.tasks.daily_long"],
}
```

---

## Fixtures (Config to export/import)

```python
fixtures = [
    # Export all records of these doctypes
    "Role",
    "Workflow",
    "Custom Field",
    "Property Setter",
    "Notification",

    # Export with filters
    {
        "dt": "Print Format",
        "filters": [["module", "=", "My Module"]]
    },
    {
        "dt": "Report",
        "filters": [["is_standard", "=", "No"], ["module", "=", "My Module"]]
    },
    {
        "dt": "Custom Field",
        "filters": [["dt", "in", ["Sales Order", "Purchase Order"]]]
    }
]
```

---

## Boot Session Data

```python
boot_session = "myapp.startup.boot_session"

# myapp/startup.py
def boot_session(bootinfo):
    bootinfo.my_app_settings = frappe.get_doc("My App Settings")
```

---

## Website / Portal Hooks

```python
website_route_rules = [
    {"from_route": "/orders", "to_route": "Sales Order"},
]

website_generators = ["My Web Page"]  # DocTypes with web page generation

portal_menu_items = [
    {"title": "My Orders", "route": "/orders", "reference_doctype": "Sales Order"}
]
```

---

## Permission Hooks

```python
permission_query_conditions = {
    "Sales Order": "myapp.permissions.get_permission_query",
}

has_permission = {
    "Sales Order": "myapp.permissions.has_permission",
}
```

```python
# myapp/permissions.py
def get_permission_query(user):
    """Add extra WHERE conditions to list view queries"""
    if frappe.session.user == "Administrator":
        return ""
    return f"`tabSales Order`.`territory` = '{get_user_territory(user)}'"

def has_permission(doc, user):
    """Return True/False for document-level access"""
    return doc.owner == user or frappe.has_role("Sales Manager", user)
```

---

## Jinja Templates (Custom Filters/Methods)

```python
jinja = {
    "methods": ["myapp.utils.jinja_methods"],
    "filters": ["myapp.utils.jinja_filters"]
}

# myapp/utils.py
def format_indian_number(value):
    """Format number in Indian system (lakhs, crores)"""
    ...

def jinja_methods():
    return {"format_indian": format_indian_number}
```

---

## After Install / Migrate Hooks

```python
after_install = "myapp.setup.install.after_install"
after_migrate = "myapp.setup.install.after_migrate"

# myapp/setup/install.py
def after_install():
    create_default_roles()
    create_default_templates()
    setup_naming_series()
```

---

## Notification Hooks

```python
notifications = [
    {
        "source": "ToDo",
        "targets": [
            {"target": "user", "field": "owner"}
        ]
    }
]
```

Or use the Notification DocType (UI-based) which is more common.

---

## Override Whitelisted Methods

```python
override_whitelisted_methods = {
    "erpnext.controllers.accounts_controller.get_taxes_and_charges":
        "myapp.overrides.get_taxes_and_charges"
}
```

---

## App Includes (CSS/JS)

```python
# Loaded on every desk page
app_include_css = "/assets/myapp/css/custom.css"
app_include_js = "/assets/myapp/js/custom.js"

# Loaded on website pages
web_include_css = "/assets/myapp/css/web.css"
web_include_js = "/assets/myapp/js/web.js"
```

---

## Useful frappe API Calls in Hooks/Controllers

```python
# Permissions
frappe.has_role("Sales Manager", user)
frappe.only_for("System Manager")    # Raises PermissionError if not

# Email
frappe.sendmail(
    recipients=["user@example.com"],
    subject="Subject",
    message="HTML body",
    reference_doctype="Sales Order",
    reference_name="SO-0001"
)

# Notifications (bell icon)
frappe.publish_realtime(
    event="eval_js",
    message="frappe.msgprint('New order received!')",
    user="user@example.com"
)

# Background jobs
frappe.enqueue(
    "myapp.tasks.heavy_task",
    queue="long",
    timeout=600,
    doc_name=self.name
)

# Translations
frappe._("English text")

# Throw / Msgprint
frappe.throw(_("Error message"), frappe.ValidationError)
frappe.msgprint(_("Info message"), indicator="green")
```
