# Copyright (c) 2025, KaitenSoftware and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime


class StockReservationLog(Document):
    def validate(self):
        """Validate the reservation log entry"""
        self.validate_qty()
        self.set_status()
    
    def validate_qty(self):
        """Ensure reserved qty does not exceed required qty"""
        if self.reserved_qty and self.required_qty:
            if self.reserved_qty > self.required_qty:
                frappe.throw(
                    _("Reserved Qty ({0}) cannot exceed Required Qty ({1})").format(
                        self.reserved_qty, self.required_qty
                    )
                )
    
    def set_status(self):
        """Set status based on quantities"""
        if self.status in ["Released", "Cancelled"]:
            return
        
        if not self.reserved_qty or self.reserved_qty == 0:
            self.status = "Cancelled"
        elif self.consumed_qty >= self.reserved_qty:
            self.status = "Consumed"
        elif self.consumed_qty > 0:
            self.status = "Partially Consumed"
        elif self.reserved_qty < self.required_qty:
            self.status = "Partially Reserved"
        else:
            self.status = "Reserved"
    
    def release(self, reason="Admin Override"):
        """Release this reservation"""
        self.status = "Released"
        self.released_date = nowdate()
        self.release_reason = reason
        self.save(ignore_permissions=True)
        
        # Log the release
        _log_reservation_action(
            self.name,
            "Released",
            f"Reservation released. Reason: {reason}"
        )
    
    def consume(self, qty, delivery_note=None):
        """Consume reserved stock (on delivery)"""
        self.consumed_qty = (self.consumed_qty or 0) + qty
        if delivery_note:
            self.delivery_note = delivery_note
        
        if self.consumed_qty >= self.reserved_qty:
            self.status = "Consumed"
            self.released_date = nowdate()
            self.release_reason = "Delivery Completed"
        else:
            self.status = "Partially Consumed"
        
        self.save(ignore_permissions=True)
        
        _log_reservation_action(
            self.name,
            "Consumed",
            f"Consumed {qty} units. Delivery: {delivery_note or 'N/A'}"
        )


def _log_reservation_action(docname, action, details=""):
    """Log reservation action as comment for audit"""
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Stock Reservation Log",
        "reference_name": docname,
        "content": _("{0}: {1}").format(action, details) if details else action
    }).insert(ignore_permissions=True)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_reserved_qty(item_code, warehouse):
    """
    Get total reserved quantity for an item in a warehouse
    This is used to calculate available stock
    """
    reserved = frappe.db.sql("""
        SELECT COALESCE(SUM(reserved_qty - consumed_qty), 0) as reserved
        FROM `tabStock Reservation Log`
        WHERE item_code = %s 
        AND warehouse = %s
        AND status IN ('Reserved', 'Partially Reserved', 'Partially Consumed')
    """, (item_code, warehouse), as_dict=True)
    
    return reserved[0].reserved if reserved else 0


def get_available_qty(item_code, warehouse):
    """
    Get available quantity (actual stock minus reserved)
    """
    from erpnext.stock.utils import get_stock_balance
    
    actual_qty = get_stock_balance(item_code, warehouse) or 0
    reserved_qty = get_reserved_qty(item_code, warehouse)
    
    return actual_qty - reserved_qty


def create_reservation_log(data):
    """
    Create a new Stock Reservation Log entry
    
    Args:
        data: dict with keys:
            - sales_order
            - sales_order_item
            - quotation (optional)
            - technical_survey (optional)
            - bom (optional)
            - customer
            - item_code
            - warehouse
            - required_qty
            - reserved_qty
    """
    log = frappe.get_doc({
        "doctype": "Stock Reservation Log",
        "sales_order": data.get("sales_order"),
        "sales_order_item": data.get("sales_order_item"),
        "quotation": data.get("quotation"),
        "technical_survey": data.get("technical_survey"),
        "bom": data.get("bom"),
        "customer": data.get("customer"),
        "item_code": data.get("item_code"),
        "warehouse": data.get("warehouse"),
        "required_qty": data.get("required_qty"),
        "reserved_qty": data.get("reserved_qty"),
        "available_qty_at_reservation": data.get("available_qty", 0),
        "reservation_date": nowdate(),
        "status": "Reserved"
    })
    
    log.insert(ignore_permissions=True)
    
    _log_reservation_action(
        log.name,
        "Created",
        f"Reserved {log.reserved_qty} units of {log.item_code} for SO {log.sales_order}"
    )
    
    return log


def release_reservations_for_sales_order(sales_order, reason="Sales Order Cancelled"):
    """
    Release all reservations linked to a Sales Order
    """
    reservations = frappe.get_all(
        "Stock Reservation Log",
        filters={
            "sales_order": sales_order,
            "status": ["in", ["Reserved", "Partially Reserved", "Partially Consumed"]]
        },
        pluck="name"
    )
    
    for reservation_name in reservations:
        doc = frappe.get_doc("Stock Reservation Log", reservation_name)
        doc.release(reason)
    
    return len(reservations)
