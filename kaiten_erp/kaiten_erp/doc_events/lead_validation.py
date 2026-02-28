import frappe

def validate_vendors(doc):
    """
    Validate vendor assignments on Lead.
    Vendors are OPTIONAL but if provided, must be valid Suppliers.
    """
    # Resolve territory from multiple possible fields (priority order)
    territory = doc.get('custom_territory_display')
    
    
    
    # Validate vendor_assign (Technical Execution) - OPTIONAL
    if doc.vendor_assign:
        validate_vendor(
            doc.vendor_assign,
            territory,
            [
                "Structure and Project Installation Vendor",
                "Solar Installation Vendor"
            ],
            "Technical Execution Vendor"
        )
    
    # Validate meter_execution_vendor - OPTIONAL
    if doc.meter_execution_vendor:
        validate_vendor(
            doc.meter_execution_vendor,
            territory,
            [
                "Meter Installation & Commissioning Vendor",
                "Solar Installation Vendor"
            ],
            "Meter Execution Vendor"
        )


def validate_vendor(vendor, territory, allowed_groups, label):
    """
    Validate that vendor is a valid Supplier with correct group and territory.
    Assumes vendor is already a Supplier ID (not email).
    
    Args:
        vendor: Supplier name/ID
        territory: Territory name
        allowed_groups: List of allowed supplier groups
        label: Field label for error messages
    """
    if not vendor:
        return  # Optional field
    
    # Safety check: Ensure vendor exists as Supplier
    if not frappe.db.exists("Supplier", vendor):
        frappe.throw(
            f"{label} '{vendor}' is not a valid Supplier. Please select from the dropdown."
        )
    
    supplier = frappe.get_doc("Supplier", vendor)
    
    # Validate supplier group
    if supplier.supplier_group not in allowed_groups:
        frappe.throw(
            f"{vendor} is not allowed as {label}. "
            f"Supplier must belong to one of: {', '.join(allowed_groups)}"
        )
    
    # Validate territory assignment
    active_territory = frappe.db.exists(
        "Supplier Territory Child Table",
        {
            "parent": vendor,
            "territory": territory,
            "status": "Active"
        }
    )
    
    if not active_territory:
        frappe.throw(
            f"{vendor} is not active for territory {territory}. "
            f"Please assign this territory to the supplier or select a different vendor."
        )
