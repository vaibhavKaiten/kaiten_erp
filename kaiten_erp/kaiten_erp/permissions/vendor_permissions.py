"""
Vendor Permission Utilities
Helper functions for vendor-based permission filtering
"""

import frappe


def get_user_supplier(user):
    """
    Get the Supplier company linked to a user via Contact and Dynamic Link
    
    In Frappe, portal users are linked to Suppliers through:
    Supplier → Contact → User (via Dynamic Link)
    
    Args:
        user (str): User email
    
    Returns:
        str: Supplier name or None if not found
    """
    if not user:
        return None
    
    # Get contact linked to this user
    contact = frappe.db.get_value("Contact", {"user": user}, "name")
    
    if not contact:
        return None
    
    # Get supplier linked to this contact via Dynamic Link
    supplier = frappe.db.get_value(
        "Dynamic Link",
        {
            "link_doctype": "Supplier",
            "parenttype": "Contact",
            "parent": contact
        },
        "link_name"
    )
    
    return supplier


def get_supplier_users(supplier, role=None):
    """
    Get all users linked to a specific Supplier company
    
    Args:
        supplier (str): Supplier name
        role (str, optional): Filter by specific role (e.g., 'Vendor Executive')
    
    Returns:
        list: List of user emails
    """
    if not supplier:
        return []
    
    # Get all contacts linked to this supplier
    contacts = frappe.db.sql("""
        SELECT dl.parent
        FROM `tabDynamic Link` dl
        WHERE dl.link_doctype = 'Supplier'
            AND dl.link_name = %(supplier)s
            AND dl.parenttype = 'Contact'
    """, {'supplier': supplier}, as_dict=True)
    
    contact_names = [c.parent for c in contacts]
    
    if not contact_names:
        return []
    
    # Get users from these contacts
    query = """
        SELECT DISTINCT c.user
        FROM `tabContact` c
        WHERE c.name IN %(contacts)s
            AND c.user IS NOT NULL
            AND c.user != ''
    """
    
    params = {'contacts': contact_names}
    
    # Add role filter if specified
    if role:
        query = """
            SELECT DISTINCT c.user
            FROM `tabContact` c
            INNER JOIN `tabHas Role` hr ON hr.parent = c.user
            WHERE c.name IN %(contacts)s
                AND c.user IS NOT NULL
                AND c.user != ''
                AND hr.role = %(role)s
        """
        params['role'] = role
    
    users = frappe.db.sql(query, params, as_dict=True)
    
    return [u.user for u in users if u.user]
