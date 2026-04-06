"""
Patch: create_payment_milestone_todos
Retroactively create Accounts Manager ToDos for all existing submitted Sales Orders
that have Payment Milestone rows with amount > 0 and status != 'Paid'.

Uses the same description format and helper functions as sales_order_events.py so
that the on_update_after_submit logic can correctly detect and update these todos.
"""

import frappe


def execute():
    from kaiten_erp.kaiten_erp.doc_events.sales_order_events import (
        _get_accounts_manager_users,
        _milestone_todo_description,
    )

    managers = _get_accounts_manager_users()
    if not managers:
        frappe.logger().warning(
            "create_payment_milestone_todos: No active Accounts Manager users found; skipping."
        )
        return

    # Find all unpaid Payment Milestone rows on submitted Sales Orders
    milestones = frappe.db.sql(
        """
        SELECT
            pm.name  AS row_name,
            pm.parent AS sales_order,
            pm.milestone,
            pm.amount,
            so.customer,
            so.customer_name,
            so.custom_job_file
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
        customer_name = row.customer_name or row.customer or row.sales_order
        k_number = ""
        if row.custom_job_file:
            k_number = frappe.db.get_value("Job File", row.custom_job_file, "k_number") or ""

        description = _milestone_todo_description(
            row.sales_order, row.milestone, float(row.amount), customer_name, k_number
        )

        for user in managers:
            # Skip if an open ToDo for this milestone already exists for this user
            existing = frappe.db.exists(
                "ToDo",
                {
                    "reference_type": "Sales Order",
                    "reference_name": row.sales_order,
                    "allocated_to": user,
                    "role": "Accounts Manager",
                    "status": "Open",
                    "description": ["like", f"% - {row.milestone} %"],
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
                    "priority": "Medium",
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
            created += 1

    frappe.db.commit()
    frappe.logger().info(
        f"create_payment_milestone_todos: Created {created} Accounts Manager ToDo(s)."
    )
