"""
Project Installation Permission Control
Uses Frappe's ToDo assignment system (same as Structure Mounting)
Only users assigned via "Assign To" can access documents
"""

import frappe
from frappe import _


def get_permission_query_conditions(user):
    """
    Permission query to filter Project Installation list for Vendor Managers and Vendor Executives
    
    - Vendor Managers: see documents where assigned_vendor = their company AND status = 'Assigned to Vendor'
    - Vendor Executives: see documents explicitly assigned to them (via Frappe's "Assign To" / ToDo system)
    - Internal admins: see all documents
    """
    if not user:
        user = frappe.session.user

    # Allow all access for System Manager, Administrator, Execution Manager, etc.
    internal_roles = [
        "System Manager",
        "Administrator",
        "Execution Manager",
       
    ]
    
    if any(role in frappe.get_roles(user) for role in internal_roles):
        return None
    
    roles = frappe.get_roles(user)
    conditions = []
    
    # Vendor Manager: see documents for their vendor company in "Assigned to Vendor" state
    if "Vendor Manager" in roles:
        vendor_companies = frappe.db.sql("""
            SELECT DISTINCT dl.link_name
            FROM `tabContact` c
            INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name
            WHERE c.user = %s
                AND dl.link_doctype = 'Supplier'
                AND dl.parenttype = 'Contact'
        """, (user,), as_dict=True)
        
        if vendor_companies:
            vendor_names = [vc.link_name for vc in vendor_companies]
            conditions.append(
                "(`tabProject Installation`.assigned_vendor IN ({}) AND `tabProject Installation`.status = 'Assigned to Vendor')".format(
                    ", ".join([frappe.db.escape(v) for v in vendor_names])
                )
            )
    
    # Vendor Executive: see documents explicitly assigned to them via "Assign To" (ToDo system) and for their vendor company
    if "Vendor Executive" in roles:
        assigned_docs = frappe.db.sql("""
            SELECT DISTINCT reference_name
            FROM `tabToDo`
            WHERE reference_type = 'Project Installation'
                AND allocated_to = %s
                AND status != 'Cancelled'
        """, (user,), as_dict=True)
        
        if assigned_docs:
            doc_names = [d.reference_name for d in assigned_docs]
            conditions.append(
                "`tabProject Installation`.name IN ({})".format(
                    ", ".join([frappe.db.escape(s) for s in doc_names])
                )
            )
    
    # Combine conditions with OR
    if conditions:
        return " OR ".join([f"({cond})" for cond in conditions])
    
    # If user has neither role or no conditions matched, show nothing
    return "`tabProject Installation`.name = ''"


def has_permission(doc, ptype, user):
    """
    Check if user has permission to access a specific Project Installation document
    
    Access granted if:
    1. User is an internal admin, OR
    2. User is a Vendor Manager with the vendor company assigned to the document, OR
    3. User has an active ToDo assigned to this document
    
    Args:
        doc: Project Installation document or doctype string
        ptype: Permission type ('read', 'write', 'submit', etc.)
        user: User email (frappe.session.user)
    
    Returns:
        True if allowed, False if denied
    """
    
    if not user:
        user = frappe.session.user


    roles = frappe.get_roles(user)


    # System-level access
    if any(r in roles for r in ["Administrator", "Execution Manager"]):
        return True
    
    # If doc is a string (doctype name), we can't check assignment
    # Allow at doctype level, individual docs will be filtered by query conditions
    if isinstance(doc, str):
        return True
    
    
    # Check Vendor Manager access
    if "Vendor Manager" in roles:
        vendor_companies = frappe.db.sql("""
            SELECT DISTINCT dl.link_name
            FROM `tabContact` c
            INNER JOIN `tabDynamic Link` dl ON dl.parent = c.name
            WHERE c.user = %s
                AND dl.link_doctype = 'Supplier'
                AND dl.parenttype = 'Contact'
        """, (user,), as_dict=True)
        
        vendor_names = [vc.link_name for vc in vendor_companies] if vendor_companies else []
        doc_vendor = doc.get("assigned_vendor") if hasattr(doc, 'get') else getattr(doc, 'assigned_vendor', None)
        
        if doc_vendor in vendor_names and doc.status == 'Assigned to Vendor':
            frappe.logger().info(f"Vendor Manager {user} has access to {doc.name}")
            return True
    
    # Check Vendor Executive access - must have active ToDo assignment
    if "Vendor Executive" in roles :
        # 1. Must have active ToDo
        has_todo = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Project Installation",
                "reference_name": doc.name,
                "allocated_to": user,
                "status": ["!=", "Cancelled"],
            },
        )
        if not has_todo:
            return False


        # 2. Supplier must match
        if doc.assigned_vendor not in vendor_names:
            return False


        # 3. Correct workflow state
        if doc.workflow_state != "Assigned to Vendor":
            return False
    
        return True
    # return False
        # todo_exists = frappe.db.sql("""
        #     SELECT name
        #     FROM `tabToDo`
        #     WHERE reference_type = 'Project Installation'
        #         AND reference_name = %s
        #         AND allocated_to = %s
        #         AND status != 'Cancelled'
        #     LIMIT 1
        # """, (doc.name, user), as_dict=True)
        
        # if todo_exists:
        #     frappe.logger().info(f"Vendor Executive {user} has ToDo assignment for {doc.name} - granting access")
        #     return True
    
    # No access
    frappe.logger().info(f"User {user} denied access to {doc.name} - no assignment found")
    frappe.msgprint(
        _("You do not have permission to access this Project Installation. "
          "Only assigned users can access this document."),
        indicator="orange",
        raise_exception=True
    )
    return False


def on_trash(doc, method=None):
    """
    Prevent vendors from deleting Project Installation documents
    Only allow internal roles to delete
    """
    user = frappe.session.user
    
    if user == "Administrator":
        return
    
    user_roles = [role.lower() for role in frappe.get_roles(user)]
    
    # Only these roles can delete (lowercase)
    can_delete_roles = [
        "system manager",
        "project manager",
        
    ]
    
    if not any(role in user_roles for role in can_delete_roles):
        frappe.throw(
            _("You do not have permission to delete Project Installation documents."),
            frappe.PermissionError
        )
