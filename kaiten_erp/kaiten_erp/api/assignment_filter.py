"""
Custom Assignment Filter API
Provides methods to filter users for assignment based on vendor and role
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_vendor_executives(vendor):
    """
    Get all users who:
    1. Are linked to the specified vendor (Supplier)
    2. Have the role "Vendor Executive"
    
    Args:
        vendor (str): Name of the Supplier/Vendor
        
    Returns:
        list: List of user email addresses
    """
    if not vendor:
        frappe.throw(_("Vendor is required"))
    
    # Verify vendor exists
    if not frappe.db.exists("Supplier", vendor):
        frappe.throw(_("Vendor {0} does not exist").format(vendor))
    
    # Get all users linked to this vendor through Contact
    # First, get contacts linked to the supplier
    contacts = frappe.get_all(
        "Dynamic Link",
        filters={
            "link_doctype": "Supplier",
            "link_name": vendor,
            "parenttype": "Contact"
        },
        fields=["parent"]
    )
    
    contact_names = [c.parent for c in contacts]
    
    if not contact_names:
        return []
    
    # Get users from these contacts
    users_from_contacts = frappe.get_all(
        "Contact",
        filters={
            "name": ["in", contact_names],
            "user": ["is", "set"]
        },
        fields=["user"]
    )
    
    user_emails = [u.user for u in users_from_contacts if u.user]
    
    if not user_emails:
        return []
    
    # Filter users who have "Vendor Executive" role
    vendor_executives = []
    
    for user_email in user_emails:
        # Check if user has "Vendor Executive" role
        has_role = frappe.db.exists(
            "Has Role",
            {
                "parent": user_email,
                "role": "Vendor Executive",
                "parenttype": "User"
            }
        )
        
        if has_role:
            vendor_executives.append(user_email)
    
    return vendor_executives


@frappe.whitelist()
def get_vendor_executive_details(vendor):
    """
    Get detailed information about vendor executives
    
    Args:
        vendor (str): Name of the Supplier/Vendor
        
    Returns:
        list: List of dicts with user details (email, full_name)
    """
    user_emails = get_vendor_executives(vendor)
    
    if not user_emails:
        return []
    
    users = frappe.get_all(
        "User",
        filters={
            "email": ["in", user_emails],
            "enabled": 1
        },
        fields=["email", "full_name", "user_image"]
    )
    
    return users
