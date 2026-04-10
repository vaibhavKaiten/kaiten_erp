# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Job File – Document-level Permission Check

Sales Manager: allowed to read/write a specific Job File only if they are
the Sales Manager assigned on the linked Lead
(Lead.custom_active_sales_manager → Sales Person → Employee → user_id = user).

All other roles fall through to Frappe's default permission logic (return None).
"""

import frappe


def _get_assigned_sm_user(job_file_doc):
    """Return the User email of the Sales Manager assigned to this Job File via its Lead.

    Lookup chain:
      1. Sales Person.employee → Employee.user_id  (primary)
      2. Sales Person.sales_person_name = User.full_name  (fallback when Employee has no user_id)
    """
    lead_name = job_file_doc.get("lead") if not isinstance(job_file_doc, str) else None
    if not lead_name:
        return None

    sales_person = frappe.db.get_value("Lead", lead_name, "custom_active_sales_manager")
    if not sales_person:
        return None

    sp_data = frappe.db.get_value("Sales Person", sales_person, ["employee", "sales_person_name"], as_dict=True)
    if not sp_data:
        return None

    # Primary: Employee → user_id
    if sp_data.employee:
        uid = frappe.db.get_value("Employee", sp_data.employee, "user_id")
        if uid:
            return uid

    # Fallback: match sales_person_name against User.full_name
    if sp_data.sales_person_name:
        uid = frappe.db.get_value("User", {"full_name": sp_data.sales_person_name, "enabled": 1}, "name")
        return uid

    return None


def has_permission(doc, ptype=None, user=None):
    if not user:
        user = frappe.session.user

    roles = frappe.get_roles(user)

    # Admin / internal users → full access
    if any(r in roles for r in ["System Manager", "Administrator", "Execution Manager"]):
        return True

    # Sales Manager: allow only if they are the assigned SM for this Job File's Lead
    if "Sales Manager" in roles:
        if isinstance(doc, str):
            # Called with just the doc name — fetch the lead field
            lead_name = frappe.db.get_value("Job File", doc, "lead")
            if not lead_name:
                return False
            # Build a lightweight proxy for _get_assigned_sm_user
            class _Proxy:
                def get(self, key):
                    return lead_name if key == "lead" else None
            assigned_user = _get_assigned_sm_user(_Proxy())
        else:
            assigned_user = _get_assigned_sm_user(doc)

        return assigned_user == user

    # All other roles → fall through to Frappe default checks
    return None
