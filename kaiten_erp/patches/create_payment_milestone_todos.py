"""
Patch: create_payment_milestone_todos
Retroactively create Accounts Manager ToDos for all existing submitted Sales Orders
that have Payment Milestone rows with amount > 0 and status != 'Paid'.
"""

import frappe
from frappe import _


def execute():
    managers = frappe.get_all(
        "Has Role",
        filters={"role": "Accounts Manager", "parenttype": "User"},
        pluck="parent",
    )
    active_managers = [
        u for u in managers if frappe.db.get_value("User", u, "enabled")
    ]
    if not active_managers:
        frappe.logger().warning(
            "create_payment_milestone_todos: No active Accounts Manager users found; skipping."
        )
        return

    # Find all Payment Milestone rows on submitted Sales Orders
    milestones = frappe.db.sql(
        """
        SELECT
            pm.name AS milestone_name,
            pm.parent AS sales_order,
            pm.milestone,
            pm.amount
        FROM `tabPayment Milestone` pm
        INNER JOIN `tabSales Order` so ON so.name = pm.parent
        WHERE so.docstatus = 1
          AND pm.amount > 0
          AND (pm.status IS NULL OR pm.status != 'Paid')
        """,
        as_dict=True,
    )

    created = 0
    for row in milestones:
        so = frappe.db.get_value(
            "Sales Order",
            row.sales_order,
            ["customer_name", "customer"],
            as_dict=True,
        )
        customer_name = (so and (so.customer_name or so.customer)) or row.sales_order
        amount_fmt = frappe.utils.fmt_money(row.amount, currency="INR")
        description = _(
            "Create Sales Invoice & Payment Entry of {0} for {1} – {2} milestone"
        ).format(amount_fmt, customer_name, row.milestone)

        for user in active_managers:
            # Skip if an open ToDo for this milestone already exists for this user
            existing = frappe.db.exists(
                "ToDo",
                {
                    "reference_type": "Sales Order",
                    "reference_name": row.sales_order,
                    "allocated_to": user,
                    "role": "Accounts Manager",
                    "status": "Open",
                    "description": ["like", f"%{row.milestone} milestone%"],
                },
            )
            if existing:
                continue

            frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": "Sales Order",
                    "reference_name": row.sales_order,
                    "description": description,
                    "role": "Accounts Manager",
                    "date": frappe.utils.nowdate(),
                    "priority": "Medium",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
            created += 1

    frappe.db.commit()
    frappe.logger().info(
        f"create_payment_milestone_todos: Created {created} Accounts Manager ToDo(s)."
    )
