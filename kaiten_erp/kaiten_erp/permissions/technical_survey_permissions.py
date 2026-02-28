"""
Technical Survey Permission Control
Restricts visibility so vendors can only see surveys assigned to their company
"""

import frappe

from kaiten_erp.kaiten_erp.permissions.vendor_permissions import get_user_supplier


# def get_permission_query_conditions(user):
#     """
#     Apply record-level filtering for Technical Survey list view
    
#     This function is called when fetching lists of Technical Survey documents.
#     It returns a SQL WHERE clause that filters the results based on user role.
    
#     Vendor permissions are now company-based:
#     - Vendor Manager: Can see ALL surveys assigned to their supplier company
#     - Vendor Executive: Can only see surveys explicitly assigned to them
    
#     Args:
#         user: User email (frappe.session.user)
    
#     Returns:
#         SQL WHERE clause or None (None = no restriction)
#     """
    
#     if not user:
#         user = frappe.session.user
    
#     # Skip restriction for Administrator
#     if user == "Administrator":
#         return None
    
#     # Get user roles (convert to lowercase for comparison)
#     user_roles = [role.lower() for role in frappe.get_roles(user)]
    
#     # Internal roles that can see all Technical Surveys (lowercase)
#     internal_roles = [
#         "system manager",
#         "project manager", 
#         "technical survey manager",
#         "installation manager",
#         "service head"
#     ]
    
#     # If user has any internal role, no restriction
#     if any(role in user_roles for role in internal_roles):
#         return None
    
#     # Vendor roles - use company-based filtering
#     vendor_manager_roles = ["vendor manager", "site visit vendor manager"]
#     vendor_exec_roles = ["vendor executive", "site visit vendor executive"]
    
#     # Get supplier company linked to this user via Contact
#     vendor_company = get_user_supplier(user)
    
#     frappe.logger().info(f"Permission check for user {user}: vendor_company = {vendor_company}")
    
#     if not vendor_company:
#         # User not linked to any supplier company - no access
#         frappe.logger().info(f"User {user} has no vendor company linked")
#         return "`tabTechnical Survey`.name = ''"
    
#     # Vendor Manager → all surveys assigned to their company (excluding Draft)
#     if any(r in user_roles for r in vendor_manager_roles):
#         query = (
#             f"`tabTechnical Survey`.assigned_vendor = "
#             f"{frappe.db.escape(vendor_company)} AND "
#             f"`tabTechnical Survey`.status != 'Draft'"
#         )
#         frappe.logger().info(f"Vendor Manager {user} query: {query}")
#         return query
    
#     # Vendor Executive → only surveys explicitly assigned to them (excluding Draft)
#     if any(r in user_roles for r in vendor_exec_roles):
#         query = (
#             f"`tabTechnical Survey`.assigned_internal_user = "
#             f"{frappe.db.escape(user)} AND "
#             f"`tabTechnical Survey`.assigned_vendor = "
#             f"{frappe.db.escape(vendor_company)} AND "
#             f"`tabTechnical Survey`.status != 'Draft'"
#         )
#         frappe.logger().info(f"Vendor Executive {user} query: {query}")
#         return query
    
#     # No matching vendor role - no access
#     frappe.logger().info(f"User {user} has no vendor role")
#     return "`tabTechnical Survey`.name = ''"



# def has_permission(doc, ptype, user):
#     """
#     Check if user has permission to access a specific Technical Survey document
    
#     This function is called when:
#     - Opening a document directly via URL
#     - Checking read/write/delete permissions
#     - Checking assignment permissions
    
#     Company-based permissions:
#     - Vendor Manager: Can access all surveys for their supplier company
#     - Vendor Executive: Can only access surveys explicitly assigned to them
    
#     Args:
#         doc: Technical Survey document or doctype string
#         ptype: Permission type ('read', 'write', 'submit', etc.)
#         user: User email (frappe.session.user)
    
#     Returns:
#         True if allowed, False if denied
#     """
    
#     if not user:
#         user = frappe.session.user
    
#     # Administrator always has access
#     if user == "Administrator":
#         return True
    
#     # Get user roles (lowercase for comparison)
#     user_roles = [role.lower() for role in frappe.get_roles(user)]
    
#     # Internal roles have full access (lowercase)
#     internal_roles = [
#         "system manager",
#         "project manager",
#         "technical survey manager",
#         "installation manager",
#         "service head"
#     ]
    
#     if any(role in user_roles for role in internal_roles):
#         return True
    
#     # Vendor roles - check company-based access
#     vendor_manager_roles = ["vendor manager", "site visit vendor manager"]
#     vendor_exec_roles = ["vendor executive", "site visit vendor executive"]
    
#     if any(role in user_roles for role in vendor_manager_roles + vendor_exec_roles):
#         # If doc is a string (doctype name), we can't check assignment
#         # Allow at doctype level, individual docs will be filtered by query conditions
#         if isinstance(doc, str):
#             return True
        
#         # Get user's supplier company
#         vendor_company = get_user_supplier(user)
        
#         if not vendor_company:
#             frappe.msgprint(
#                 _("You do not have permission to access Technical Surveys. "
#                   "Your user account is not linked to any vendor company."),
#                 indicator="red",
#                 raise_exception=True
#             )
#             return False
        
#         # Check if document is assigned to user's company
#         doc_vendor_company = doc.get("assigned_vendor") if hasattr(doc, 'get') else getattr(doc, 'assigned_vendor', None)
        
#         if doc_vendor_company != vendor_company:
#             frappe.msgprint(
#                 _("You do not have permission to access this Technical Survey. "
#                   "It is assigned to {0}, but you belong to {1}.").format(
#                     doc_vendor_company or "another vendor", vendor_company
#                 ),
#                 indicator="red",
#                 raise_exception=True
#             )
#             return False
        
#         # Vendor Manager → can access all company surveys
#         if any(r in user_roles for r in vendor_manager_roles):
#             return True
        
#         # Vendor Executive → only if explicitly assigned
#         # IMPORTANT: When checking permissions for assignment (ptype='read'),
#         # we need to be lenient to allow Vendor Managers to assign tasks
#         # to executives who don't have the document assigned yet.
#         if any(r in user_roles for r in vendor_exec_roles):
#             assigned_executive = doc.get("assigned_internal_user") if hasattr(doc, 'get') else getattr(doc, 'assigned_internal_user', None)
            
#             # Allow if user is the assigned executive
#             if assigned_executive == user:
#                 return True
            
#             # Check if this is an assignment operation being performed by a Vendor Manager
#             # by looking at the frappe.form_dict or frappe.call context
#             # If a Vendor Manager is viewing the doc to assign it, allow read access
#             current_user = frappe.session.user
#             current_user_roles = [role.lower() for role in frappe.get_roles(current_user)]
            
#             # If the current session user (who triggered this check) is a Vendor Manager
#             # from the same company, allow the permission check to pass
#             # This enables assignment functionality
#             if any(r in current_user_roles for r in vendor_manager_roles):
#                 current_user_vendor = get_user_supplier(current_user)
#                 if current_user_vendor == vendor_company:
#                     # Vendor Manager from same company can assign - allow
#                     return True
            
#             # If we reach here, the executive is not assigned and no manager override applies
#             frappe.msgprint(
#                 _("This Technical Survey has not been assigned to you yet. "
#                   "Please contact your Vendor Manager to get this survey assigned."),
#                 indicator="orange",
#                 raise_exception=True
#             )
#             return False
    
#     # No matching role - deny access
#     return False



def _has_active_todo(user, docname):
    return frappe.db.exists(
        "ToDo",
        {
            "reference_type": "Technical Survey",
            "reference_name": docname,
            "allocated_to": user,
            "status": ["!=", "Cancelled"],
        },
    )


def has_permission(doc, ptype=None, user=None):
    """
    Document-level permission check for Technical Survey
    
    Both Vendor Manager and Vendor Executive MUST have an active ToDo to access document.
    Once they have a ToDo:
      - Vendor Manager: Full CRUD permissions (read, write, export, share, print, etc.)
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

    # Once ToDo exists, allow all CRUD operations for both VM and VE
    if ptype in ("read", "write", "save", "submit", "cancel", "amend", "export", "share", "print"):
        return True

    return False
