# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Execution Workflow Payment Validation
Validates payment milestones before allowing execution document submission
"""

import frappe
from frappe import _
from kaiten_erp.kaiten_erp.api.milestone_invoice_manager import (
    check_payment_status,
    get_milestone_invoice,
)


def validate_installation_payment(doc, method=None):
    """
    Validate that delivery payment is received before allowing installation activities
    Called for Meter Installation, Project Installation, and related execution DocTypes

    Args:
        doc: Execution document (Meter Installation, Project Installation, etc.)
        method: Hook method (not used)
    """
    # Get linked Sales Order
    sales_order = get_linked_sales_order_from_execution_doc(doc)

    if not sales_order:
        # If no Sales Order linked, allow submission (may be standalone execution)
        return

    # Check if delivery invoice exists
    delivery_invoice = get_milestone_invoice(sales_order, "delivery")

    if not delivery_invoice:
        frappe.throw(
            _(
                "Cannot submit {0}. Delivery invoice not yet created for Sales Order {1}"
            ).format(doc.doctype, sales_order),
            title=_("Delivery Invoice Required"),
        )

    # Check if delivery invoice is paid
    if not check_payment_status(delivery_invoice):
        frappe.throw(
            _(
                "Cannot submit {0}. Delivery payment not received for Sales Invoice {1}. Please collect payment before proceeding with installation activities."
            ).format(doc.doctype, delivery_invoice),
            title=_("Payment Required"),
        )


def validate_verification_payment(doc, method=None):
    """
    Validate that final payment is received before allowing verification and closure
    Called for Verification Handover and related DocTypes

    Args:
        doc: Verification document
        method: Hook method (not used)
    """
    # Get linked Sales Order
    sales_order = get_linked_sales_order_from_execution_doc(doc)

    if not sales_order:
        # If no Sales Order linked, allow submission
        return

    # Check if final invoice exists
    final_invoice = get_milestone_invoice(sales_order, "final")

    if not final_invoice:
        frappe.throw(
            _(
                "Cannot submit {0}. Final invoice not yet created for Sales Order {1}. Please ensure Meter Commissioning is approved."
            ).format(doc.doctype, sales_order),
            title=_("Final Invoice Required"),
        )

    # Check if final invoice is paid
    if not check_payment_status(final_invoice):
        frappe.throw(
            _(
                "Cannot submit {0}. Final payment not received for Sales Invoice {1}. Please collect payment before proceeding with verification and closure."
            ).format(doc.doctype, final_invoice),
            title=_("Payment Required"),
        )


def get_linked_sales_order_from_execution_doc(doc):
    """
    Get linked Sales Order from execution document
    Tries multiple methods to find the Sales Order

    Args:
        doc: Execution document

    Returns:
        str: Sales Order name or None
    """
    # Method 1: Check custom field
    if hasattr(doc, "custom_linked_sales_order") and doc.custom_linked_sales_order:
        return doc.custom_linked_sales_order

    # Method 2: Check custom_sales_order field (if exists)
    if hasattr(doc, "custom_sales_order") and doc.custom_sales_order:
        return doc.custom_sales_order

    # Method 3: Try to find via Job File
    if hasattr(doc, "custom_job_file") and doc.custom_job_file:
        job_file = doc.custom_job_file
        sales_order = frappe.db.get_value("Job File", job_file, "sales_order")
        if sales_order:
            return sales_order

    # Method 4: Try to find via Technical Survey
    if hasattr(doc, "custom_technical_survey") and doc.custom_technical_survey:
        technical_survey = doc.custom_technical_survey
        # Find Sales Order linked to this Technical Survey
        sales_order = frappe.db.get_value(
            "Sales Order",
            {"custom_technical_survey": technical_survey, "docstatus": 1},
            "name",
        )
        if sales_order:
            return sales_order

    # Method 5: Try to find via customer
    if hasattr(doc, "customer") and doc.customer:
        # This is a fallback - get the most recent submitted Sales Order for this customer
        # This may not be accurate if customer has multiple orders
        sales_order = frappe.db.get_value(
            "Sales Order",
            {"customer": doc.customer, "docstatus": 1},
            "name",
            order_by="creation desc",
        )
        if sales_order:
            return sales_order

    return None
