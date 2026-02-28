# Copyright (c) 2025, KoriStu and contributors
# For license information, please see license.txt

import frappe


def _has_active_todo(user, docname):
    return frappe.db.exists(
        "ToDo",
        {
            "reference_type": "Structure Mounting",
            "reference_name": docname,
            "allocated_to": user,
            "status": ["!=", "Cancelled"],
        },
    )


def has_permission(doc, ptype=None, user=None):
    """
    Document-level permission check for Structure Mounting
    
    Both Vendor Manager and Vendor Executive MUST have an active ToDo to access document.
    Once they have a ToDo:
      - Vendor Manager: Full CRUD permissions in ANY workflow state
      - Vendor Executive: Full CRUD permissions (read, write, export, share, print, etc.)
    """
    if not user:
        user = frappe.session.user

    roles = frappe.get_roles(user)

    # Internal users → full access
    if any(r in roles for r in ["System Manager", "Administrator", "Execution Manager"]):
        return True

    if isinstance(doc, str):
        return True

    is_vendor_user = any(r in roles for r in ["Vendor Executive", "Vendor Manager"])
    if not is_vendor_user:
        return False

    # MUST have active ToDo assigned
    if not _has_active_todo(user, doc.name):
        return False

    # Resolve supplier(s) for user
    vendor_companies = frappe.db.sql("""
        SELECT DISTINCT dl.link_name
        FROM `tabContact` c
        INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name
        WHERE c.user = %s
          AND dl.link_doctype = 'Supplier'
          AND dl.parenttype = 'Contact'
    """, (user,), as_dict=True)

    vendor_names = [v.link_name for v in vendor_companies]
    
    # No supplier mapping → no access
    if not vendor_names:
        return False
    
    # Supplier must match
    if doc.assigned_vendor not in vendor_names:
        return False

    # Once ToDo exists and supplier matches, allow all CRUD operations
    if ptype in ("read", "write", "save", "submit", "cancel", "amend", "export", "share", "print"):
        return True

    return False
