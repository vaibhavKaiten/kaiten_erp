import frappe


def on_submit(doc, method=None):
    """Create ToDo for Stock Managers to create Delivery Note after MR is submitted."""
    _create_delivery_note_todos(doc)


def _create_delivery_note_todos(doc):
    sales_order = doc.get("custom_source_sales_order")
    if not sales_order:
        return

    customer = doc.get("custom_source_customer") or ""
    customer_name = customer
    if customer:
        customer_name = (
            frappe.db.get_value("Customer", customer, "customer_name") or customer
        )

    k_number = ""
    job_file = frappe.db.get_value("Sales Order", sales_order, "custom_job_file")
    if job_file:
        k_number = frappe.db.get_value("Job File", job_file, "k_number") or ""

    desc_parts = [customer_name]
    if k_number:
        desc_parts[0] = f"{customer_name} ({k_number})"
    description = f"Create Delivery Note - {desc_parts[0]} | SO: {sales_order}"

    stock_managers = _get_stock_manager_users()
    if not stock_managers:
        return

    for user in stock_managers:
        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Delivery Note",
                "allocated_to": user,
                "status": "Open",
                "description": ["like", f"%| SO: {sales_order}%"],
            },
        )
        if existing:
            continue

        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": user,
                "reference_type": "Delivery Note",
                "description": description,
                "role": "Stock Manager",
                "priority": "Medium",
                "status": "Open",
            }
        )
        todo.flags.ignore_permissions = True
        todo.insert()


def _get_stock_manager_users():
    users = frappe.db.sql(
        """
        SELECT DISTINCT u.name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` hr ON hr.parent = u.name AND hr.parenttype = 'User'
        WHERE hr.role = 'Stock Manager'
          AND u.enabled = 1
          AND u.name NOT IN ('Administrator', 'Guest')
        """,
        as_dict=True,
    )
    return [u.name for u in users]
