# Copyright (c) 2025, KoriStu and contributors
# For license information, please see license.txt


"""
Technical Survey – List View Visibility (Fresh & Strict)

Vendor Executive / Vendor Manager:
- workflow_state == 'Assigned to Vendor'
- assigned_vendor == user's supplier
- ACTIVE ToDo exists (allocated_to = user)

No ToDo → document does not exist for them
"""

import frappe
from kaiten_erp.kaiten_erp.permissions.vendor_permissions import get_user_supplier

def get_permission_query_conditions(user=None):
    """
    List view filter for Technical Survey
    
    Vendor Manager: Can see documents in ANY workflow state if:
      - Active ToDo assigned to them
      - assigned_vendor matches their supplier company
    
    Vendor Executive: Can see documents ONLY if:
      - Active ToDo assigned to them
      - assigned_vendor matches their supplier company
      - workflow_state == 'Assigned to Vendor'
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
        return "`tabTechnical Survey`.name = ''"

    # Resolve supplier
    supplier = get_user_supplier(user)
    if not supplier:
        return "`tabTechnical Survey`.name = ''"

    # Get docs explicitly assigned via ToDo
    todos = frappe.db.sql(
        """
        SELECT DISTINCT reference_name
        FROM `tabToDo`
        WHERE reference_type = 'Technical Survey'
          AND allocated_to = %s
          AND status != 'Cancelled'
        """,
        (user,),
        as_dict=True,
    )

    doc_names = [t.reference_name for t in todos]
    if not doc_names:
        return "`tabTechnical Survey`.name = ''"

    doc_list = ", ".join(frappe.db.escape(d) for d in doc_names)

    # VENDOR MANAGER: See documents in ANY workflow state
    if is_vendor_manager:
        return f"""
            `tabTechnical Survey`.name IN ({doc_list})
            AND `tabTechnical Survey`.assigned_vendor = {frappe.db.escape(supplier)}
        """
    
    # VENDOR EXECUTIVE: See documents in ANY workflow state (enables rework flow)
    if is_vendor_executive:
        return f"""
            `tabTechnical Survey`.name IN ({doc_list})
            AND `tabTechnical Survey`.assigned_vendor = {frappe.db.escape(supplier)}
        """
    
    return "`tabTechnical Survey`.name = ''"

