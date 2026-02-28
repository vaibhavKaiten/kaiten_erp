"""
API functions for Lead Vendor Manager assignment
Handles filtering of Vendor Managers based on Territory
"""

import frappe
from frappe import _


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_vendor_managers_for_territory(doctype, txt, searchfield, start, page_len, filters):
    """
    Custom query to fetch Vendor Managers filtered by Territory
    
    Args:
        doctype: Target doctype (User)
        txt: Search text entered by user
        searchfield: Field to search in (typically 'name' or 'full_name')
        start: Pagination start
        page_len: Number of results per page
        filters: Dict containing 'territory' key
    
    Returns:
        List of tuples containing User records
    """
    
    territory = filters.get('territory')
    
    if not territory:
        frappe.msgprint(_("Please select a Territory first"))
        return []
    
    # Strict Query: ONLY show Users with "Vendor Manager" role who have 
    # explicit User Permission for the selected Territory
    # 
    # This ensures:
    # 1. User is enabled
    # 2. User has "Vendor Manager" role (via Has Role table)
    # 3. User has explicit User Permission for this specific Territory
    
    query = """
        SELECT DISTINCT 
            u.name,
            u.full_name,
            u.email
        FROM 
            `tabUser` u
        INNER JOIN 
            `tabHas Role` hr ON hr.parent = u.name AND hr.role = 'Vendor Manager'
        INNER JOIN 
            `tabUser Permission` up ON up.user = u.name 
            AND up.allow = 'Territory' 
            AND up.for_value = %(territory)s
        WHERE 
            u.enabled = 1
            AND (
                u.name LIKE %(txt)s 
                OR u.full_name LIKE %(txt)s 
                OR u.email LIKE %(txt)s
            )
        ORDER BY 
            u.full_name ASC
        LIMIT %(start)s, %(page_len)s
    """
    
    return frappe.db.sql(
        query,
        {
            'territory': territory,
            'txt': f"%{txt}%",
            'start': start,
            'page_len': page_len
        }
    )


# def validate_vendor_manager_territory(doc, method=None):
#     """
#     Server-side validation to ensure assigned Vendor Manager has access to the Lead's Territory
#     This hook should be added to Lead's validate event
    
#     Args:
#         doc: Lead document
#         method: Event method (validate)
#     """
    
#     if not doc.assign_vendor:
#         return
    
#     # Get territory from either custom or standard field
#     territory = doc.get('custom_territory_display') or doc.get('territory')
    
#     if not territory:
#         return
    
#     # Check if the assigned user is a Vendor Manager
#     has_role = frappe.db.exists(
#         "Has Role",
#         {
#             "parent": doc.assign_vendor,
#             "role": "Vendor Manager"
#         }
#     )
    
#     if not has_role:
#         frappe.throw(
#             _("User {0} does not have the 'Vendor Manager' role").format(
#                 frappe.bold(doc.assign_vendor)
#             )
#         )
    
#     # Check if user has permission for this territory
#     # STRICT: User MUST have explicit territory permission
#     has_territory_permission = frappe.db.exists(
#         "User Permission",
#         {
#             "user": doc.assign_vendor,
#             "allow": "Territory",
#             "for_value": territory
#         }
#     )
    
#     if not has_territory_permission:
#         frappe.throw(
#             _("Vendor Manager {0} is not assigned to Territory {1}. Please configure User Permissions for this user.").format(
#                 frappe.bold(doc.assign_vendor),
#                 frappe.bold(territory)
#             )
#         )

def validate_vendor_manager_territory(doc, method=None):
    """
    Validate that selected suppliers are allowed for the Lead's territory.
    This works on SUPPLIERS, not USERS.
    """

    territory = doc.get("custom_territory_display") or doc.get("territory")
    if not territory:
        return

    # Validate Technical Execution Vendor
    if doc.vendor_assign:
        _validate_supplier_territory(doc.vendor_assign, territory)

    # Validate Meter Execution Vendor
    if doc.meter_execution_vendor:
        _validate_supplier_territory(doc.meter_execution_vendor, territory)

def _validate_supplier_territory(supplier, territory):
    exists = frappe.db.exists(
        "Supplier Territory Child Table",
        {
            "parent": supplier,
            "territory": territory,
            "status": "Active"
        }
    )

    if not exists:
        frappe.throw(
            _("Supplier {0} is not Active in Territory {1}.").format(
                frappe.bold(supplier),
                frappe.bold(territory)
            )
        )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_suppliers_in_territory(doctype, txt, searchfield, start, page_len, filters):
    """
    Fetch Suppliers (Vendor Companies) filtered by Territory Child Table.
    Used for Lead > assign_vendor field.
    """
    territory = filters.get('territory')
    
    if not territory:
        return []
        
    query = """
        SELECT DISTINCT
            s.name,
            s.supplier_name
        FROM
            `tabSupplier` s
        INNER JOIN
            `tabSupplier Territory Child Table` child ON child.parent = s.name
        WHERE
            s.disabled = 0
            AND child.territory = %(territory)s
            AND child.status = 'Active'
            AND (
                s.name LIKE %(txt)s 
                OR s.supplier_name LIKE %(txt)s
            )
        ORDER BY
            s.supplier_name ASC
        LIMIT %(start)s, %(page_len)s
    """
    
    return frappe.db.sql(
        query,
        {
            'territory': territory,
            'txt': f"%{txt}%",
            'start': start,
            'page_len': page_len
        }
    )


@frappe.whitelist()
def get_technical_vendors(doctype, txt, searchfield, start, page_len, filters):
    territory = filters.get("territory")

    if not territory:
        return []

    return frappe.db.sql("""
        SELECT DISTINCT
            s.name, s.supplier_name
        FROM
            `tabSupplier` s
        INNER JOIN
            `tabSupplier Territory Child Table` st
            ON st.parent = s.name
        WHERE
            s.disabled = 0
            AND st.territory = %s
            AND st.status = 'Active'
            AND s.supplier_group IN (
                'Structure and Project Installation Vendor',
                'Solar Installation Vendor'
            )
            AND (
                s.name LIKE %s
                OR s.supplier_name LIKE %s
            )
        ORDER BY s.supplier_name
        LIMIT %s OFFSET %s
    """, (
        territory,
        f"%{txt}%",
        f"%{txt}%",
        page_len,
        start
    ))

    
@frappe.whitelist()
def get_meter_vendors(doctype, txt, searchfield, start, page_len, filters):
    territory = filters.get("territory")

    if not territory:
        return []

    return frappe.db.sql("""
        SELECT DISTINCT
            s.name, s.supplier_name
        FROM
            `tabSupplier` s
        INNER JOIN
            `tabSupplier Territory Child Table` st
            ON st.parent = s.name
        WHERE
            s.disabled = 0
            AND st.territory = %s
            AND st.status = 'Active'
            AND s.supplier_group IN (
                'Meter Installation & Commissioning Vendor',
                'Solar Installation Vendor'
            )
            AND (
                s.name LIKE %s
                OR s.supplier_name LIKE %s
            )
        ORDER BY s.supplier_name
        LIMIT %s OFFSET %s
    """, (
        territory,
        f"%{txt}%",
        f"%{txt}%",
        page_len,
        start
    ))


@frappe.whitelist()
def initiate_survey_for_vendor(survey_name):
    """
    Initiate Technical Survey for vendor company visibility
    
    This changes the status from Draft to Assigned, making it visible to
    the vendor manager based on the assigned_vendor field.
    
    Args:
        survey_name (str): Name of the Technical Survey document
    
    Returns:
        dict: Success/error response
    """
    try:
        # Validate permissions
        if not (frappe.has_permission("Technical Survey", "write") and 
                (frappe.session.user == "Administrator" or 
                 "System Manager" in frappe.get_roles())):
            return {
                "success": False,
                "error": _("You do not have permission to initiate Technical Survey")
            }
        
        # Get Technical Survey document
        survey = frappe.get_doc("Technical Survey", survey_name)
        
        # Store the assigned_vendor before any changes
        original_vendor = survey.assigned_vendor
        
        frappe.logger().info(f"Initiating survey {survey_name}, assigned_vendor before: {original_vendor}")
        
        # Check if vendor is assigned
        if not original_vendor:
            return {
                "success": False,
                "error": _("No vendor is assigned to this Technical Survey. Please run 'Initiate Job' first.")
            }
        
        # Check if already initiated (status is not Draft)
        if survey.status != "Draft":
            return {
                "success": False,
                "error": _("Technical Survey is already initiated with status: {0}").format(survey.status)
            }
        
        # Change status from Draft to Assigned
        # Also update workflow_state to keep it synchronized with status
        survey.status = "Assigned to Vendor"
        survey.workflow_state = "Assigned to Vendor"
        
        # Ensure assigned_vendor is preserved
        survey.assigned_vendor = original_vendor
        
        # Save with flags to skip certain validations if needed
        survey.flags.ignore_validate = False
        survey.flags.ignore_mandatory = False
        survey.save(ignore_permissions=True)
        
        # Verify the vendor is still assigned after save
        survey.reload()
        frappe.logger().info(f"Survey {survey_name} after save, assigned_vendor: {survey.assigned_vendor}")
        
        if not survey.assigned_vendor:
            frappe.logger().error(f"assigned_vendor was cleared during save for survey {survey_name}")
            # Force set it again
            frappe.db.set_value("Technical Survey", survey_name, "assigned_vendor", original_vendor, update_modified=False)
        
        frappe.db.commit()
        
        return {
            "success": True,
            "vendor_company": original_vendor,
            "message": _("Technical Survey initiated for vendor {0}. Status changed to Assigned to Vendor.").format(
                original_vendor
            )
        }
        
    except Exception as e:
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"Error initiating Technical Survey {survey_name}"
        )
        return {
            "success": False,
            "error": _("Error initiating survey: {0}").format(str(e))
        }
