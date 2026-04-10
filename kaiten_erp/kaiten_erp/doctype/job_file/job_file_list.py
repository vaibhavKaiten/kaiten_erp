# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Job File – List View Visibility

Sales Manager: can only see Job Files where they are the Sales Manager
assigned on the linked Lead (Lead.custom_active_sales_manager → Sales Person
→ Employee → user_id = current user).

All other roles (System Manager, Administrator, Execution Manager, etc.)
see all records (default Frappe behavior).
"""

import frappe


def get_permission_query_conditions(user=None):
    if not user:
        user = frappe.session.user

    roles = frappe.get_roles(user)

    # Internal / admin users → see all
    if any(r in roles for r in ["System Manager", "Administrator", "Execution Manager"]):
        return None

    # Sales Manager: restrict to Job Files assigned to them via Lead
    if "Sales Manager" in roles:
        user_full_name = frappe.db.get_value("User", user, "full_name") or ""

        result = frappe.db.sql(
            """
            SELECT DISTINCT jf.name
            FROM `tabJob File` jf
            INNER JOIN `tabLead` l         ON l.name   = jf.lead
            INNER JOIN `tabSales Person` sp ON sp.name = l.custom_active_sales_manager
            LEFT  JOIN `tabEmployee` e     ON e.name   = sp.employee
            WHERE e.user_id = %(user)s
               OR (e.user_id IS NULL AND sp.sales_person_name = %(full_name)s)
            """,
            {"user": user, "full_name": user_full_name},
            as_dict=True,
        )

        doc_names = [r.name for r in result]
        if not doc_names:
            return "`tabJob File`.name = ''"

        doc_list = ", ".join(frappe.db.escape(d) for d in doc_names)
        return f"`tabJob File`.name IN ({doc_list})"

    # All other roles → default Frappe permission logic
    return None
