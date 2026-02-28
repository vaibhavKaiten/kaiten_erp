# Copyright (c) 2026, Vaibhav and contributors
# For license information, please see license.txt


"""
Structure Mounting – List View Visibility

Vendor Executive / Vendor Manager:
- ACTIVE ToDo exists (allocated_to = user)
- assigned_vendor == user's supplier
"""

import frappe

from ...permissions.vendor_permissions import get_user_supplier


def get_permission_query_conditions(user=None):
    """
    List view filter for Structure Mounting

    Vendor Manager: Can see documents in ANY workflow state if:
      - Active ToDo assigned to them
      - assigned_vendor matches their supplier company

    Vendor Executive: Can see documents if:
      - Active ToDo assigned to them
      - assigned_vendor matches their supplier company
    """
    if not user:
        user = frappe.session.user

    roles = frappe.get_roles(user)

    # Internal users → see all
    if any(r in roles for r in ["System Manager", "Administrator", "Execution Manager"]):
        return None

    # Only vendor roles are allowed beyond this point
    is_vendor_manager = "Vendor Manager" in roles
    is_vendor_executive = "Vendor Executive" in roles

    if not (is_vendor_manager or is_vendor_executive):
        return "`tabStructure Mounting`.name = ''"

    # Resolve supplier
    supplier = get_user_supplier(user)
    if not supplier:
        return "`tabStructure Mounting`.name = ''"

    # Get docs explicitly assigned via ToDo
    todos = frappe.db.sql(
        """
        SELECT DISTINCT reference_name
        FROM `tabToDo`
        WHERE reference_type = 'Structure Mounting'
          AND allocated_to = %s
          AND status != 'Cancelled'
        """,
        (user,),
        as_dict=True,
    )

    doc_names = [t.reference_name for t in todos]
    if not doc_names:
        return "`tabStructure Mounting`.name = ''"

    doc_list = ", ".join(frappe.db.escape(d) for d in doc_names)

    # Both Vendor Manager and Vendor Executive: See documents with active ToDo
    if is_vendor_manager or is_vendor_executive:
        return f"""
            `tabStructure Mounting`.name IN ({doc_list})
            AND `tabStructure Mounting`.assigned_vendor = {frappe.db.escape(supplier)}
        """

    return "`tabStructure Mounting`.name = ''"