# Copyright (c) 2025, KaitenSoftware and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime


class ProcurementShortageLog(Document):
    def validate(self):
        """Validate the shortage log entry"""
        self.validate_qty()
        self.update_status()
    
    def validate_qty(self):
        """Ensure shortage qty is valid"""
        if self.shortage_qty and self.shortage_qty < 0:
            frappe.throw(_("Shortage Qty cannot be negative"))
        
        if self.required_qty and self.available_qty is not None:
            calculated_shortage = self.required_qty - self.available_qty
            if calculated_shortage < 0:
                calculated_shortage = 0
            # Allow small floating point differences
            if abs(self.shortage_qty - calculated_shortage) > 0.001:
                self.shortage_qty = calculated_shortage
    
    def update_status(self):
        """Update status based on fulfilled qty"""
        if not self.fulfilled_qty:
            self.fulfilled_qty = 0
        
        if self.fulfilled_qty >= self.shortage_qty:
            self.status = "Fulfilled"
            if not self.fulfilled_date:
                self.fulfilled_date = nowdate()
        elif self.fulfilled_qty > 0:
            self.status = "Partially Fulfilled"
        else:
            self.status = "Pending"
    
    def fulfill(self, qty, purchase_receipt=None, purchase_order=None):
        """Mark shortage as fulfilled (partially or fully)"""
        self.fulfilled_qty = (self.fulfilled_qty or 0) + qty
        
        if purchase_receipt:
            self.purchase_receipt = purchase_receipt
        if purchase_order:
            self.purchase_order = purchase_order
        
        self.update_status()
        self.save(ignore_permissions=True)
        
        _log_shortage_action(
            self.name,
            "Fulfilled" if self.status == "Fulfilled" else "Partially Fulfilled",
            f"Fulfilled {qty} units. PR: {purchase_receipt or 'N/A'}"
        )


def _log_shortage_action(docname, action, details=""):
    """Log shortage action as comment for audit"""
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Procurement Shortage Log",
        "reference_name": docname,
        "content": _("{0}: {1}").format(action, details) if details else action
    }).insert(ignore_permissions=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def create_shortage_log(data):
    """
    Create a new Procurement Shortage Log entry
    
    Args:
        data: dict with keys:
            - sales_order
            - material_request
            - technical_survey (optional)
            - customer
            - project (optional)
            - item_code
            - warehouse
            - required_qty
            - available_qty
            - shortage_qty
    """
    log = frappe.get_doc({
        "doctype": "Procurement Shortage Log",
        "sales_order": data.get("sales_order"),
        "material_request": data.get("material_request"),
        "technical_survey": data.get("technical_survey"),
        "customer": data.get("customer"),
        "project": data.get("project"),
        "item_code": data.get("item_code"),
        "warehouse": data.get("warehouse"),
        "required_qty": data.get("required_qty"),
        "available_qty": data.get("available_qty"),
        "shortage_qty": data.get("shortage_qty"),
        "log_timestamp": now_datetime(),
        "status": "Pending"
    })
    
    log.insert(ignore_permissions=True)
    
    _log_shortage_action(
        log.name,
        "Created",
        f"Shortage of {log.shortage_qty} units of {log.item_code} for SO {log.sales_order}"
    )
    
    return log


def get_pending_shortages_for_sales_order(sales_order):
    """Get all pending shortage logs for a Sales Order"""
    return frappe.get_all(
        "Procurement Shortage Log",
        filters={
            "sales_order": sales_order,
            "status": ["in", ["Pending", "Partially Fulfilled"]]
        },
        fields=["name", "item_code", "warehouse", "shortage_qty", "fulfilled_qty"]
    )


def get_shortage_summary_for_sales_order(sales_order):
    """Get summary of shortages for a Sales Order"""
    shortages = frappe.get_all(
        "Procurement Shortage Log",
        filters={"sales_order": sales_order},
        fields=["item_code", "warehouse", "shortage_qty", "fulfilled_qty", "status"]
    )
    
    return {
        "total_items": len(shortages),
        "shortages": shortages,
        "status_summary": {
            "pending": len([s for s in shortages if s.status == "Pending"]),
            "partially_fulfilled": len([s for s in shortages if s.status == "Partially Fulfilled"]),
            "fulfilled": len([s for s in shortages if s.status == "Fulfilled"])
        }
    }
