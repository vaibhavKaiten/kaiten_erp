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


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_active_sales_managers_for_territory(doctype, txt, searchfield, start, page_len, filters):
    """
    Custom query for the custom_active_sales_manager Link field on Lead.

    Returns Sales Persons who have the Lead's Territory in their
    custom_sales_territory child table with status = 'Active'.

    Args:
        doctype  : 'Sales Person' (target doctype of the Link field)
        txt      : search text entered by the user
        searchfield: field to search in (name / sales_person_name)
        start    : pagination offset
        page_len : number of results to return
        filters  : dict containing 'territory' key

    Returns:
        list of tuples – each tuple is (name, sales_person_name)
    """
    territory = (filters or {}).get("territory")

    if not territory:
        return []

    query = """
        SELECT DISTINCT
            sp.name,
            sp.sales_person_name
        FROM
            `tabSales Person` sp
        INNER JOIN
            `tabSales Person Territory Child Table` sptct
            ON  sptct.parent      = sp.name
            AND sptct.parenttype  = 'Sales Person'
            AND sptct.territory   = %(territory)s
            AND sptct.status      = 'Active'
        WHERE
            (
                sp.name               LIKE %(txt)s
                OR sp.sales_person_name LIKE %(txt)s
            )
        ORDER BY
            sp.sales_person_name ASC
        LIMIT %(start)s, %(page_len)s
    """

    return frappe.db.sql(
        query,
        {
            "territory": territory,
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        }
    )
