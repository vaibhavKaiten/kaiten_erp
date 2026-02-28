# Copyright (c) 2025, KaitenSoftware
# Material Request Validation for Kaiten Erp
# 
# ⚠️ NOTICE: The validate_material_request function has been DISABLED
# The hard lock preventing manual Material Request creation has been removed
# as per user requirement on 2026-01-10
# Hook registration in hooks.py has been commented out
# Blocks manual creation of Material Requests for Sales Order shortages

import frappe
from frappe import _


def validate_material_request(doc, method):
    """
    Validate Material Request before insert
    Block manual creation for SO shortages - must be auto-generated
    """
    # Skip if already auto-generated
    if doc.get("custom_auto_generated"):
        return
    
    # Skip if no items
    if not doc.items:
        return
    
    # Check if any items match pending shortage items from Sales Orders
    for item in doc.items:
        # Find if this item has pending shortages for any SO
        pending_shortages = frappe.db.exists(
            "Procurement Shortage Log",
            {
                "item_code": item.item_code,
                "status": ["in", ["Pending", "Partially Fulfilled"]]
            }
        )
        
        if pending_shortages:
            # Check if there's a Sales Order with Pending Procurement status
            # that needs this item
            so_with_shortage = frappe.db.sql("""
                SELECT DISTINCT psl.sales_order
                FROM `tabProcurement Shortage Log` psl
                INNER JOIN `tabSales Order` so ON so.name = psl.sales_order
                WHERE psl.item_code = %s
                AND psl.status IN ('Pending', 'Partially Fulfilled')
                AND so.custom_procurement_status = 'Pending Procurement'
                AND so.docstatus = 1
            """, (item.item_code,), as_dict=True)
            
            if so_with_shortage:
                so_list = ", ".join([s.sales_order for s in so_with_shortage[:3]])
                if len(so_with_shortage) > 3:
                    so_list += f" and {len(so_with_shortage) - 3} more"
                
                frappe.throw(
                    _(
                        "Cannot manually create Material Request for item {0}. "
                        "This item has pending shortages from Sales Order(s): {1}. "
                        "Material Requests for SO shortages are auto-generated during SO submission."
                    ).format(item.item_code, so_list),
                    title=_("Manual MR Not Allowed")
                )


def on_material_request_submit(doc, method):
    """
    Additional processing when Material Request is submitted
    """
    # Log for auto-generated MRs
    if doc.get("custom_auto_generated") and doc.get("custom_source_sales_order"):
        frappe.get_doc({
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Material Request",
            "reference_name": doc.name,
            "content": _(
                "Auto-generated Material Request submitted for Sales Order {0}. "
                "Customer: {1}"
            ).format(doc.custom_source_sales_order, doc.custom_source_customer or "N/A")
        }).insert(ignore_permissions=True)
