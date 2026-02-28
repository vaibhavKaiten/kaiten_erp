# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Delivery Note event handlers for milestone-based invoicing
Validates advance payment and creates delivery milestone invoice
"""

import frappe
from frappe import _
from frappe.utils import flt
from kaiten_erp.kaiten_erp.api.milestone_invoice_manager import (
    create_milestone_invoice,
    check_payment_status,
    get_milestone_invoice,
    assign_todo_to_accounts_managers,
)


def validate(doc, method=None):
    """
    Validate Delivery Note before submission
    Block submission if advance invoice is not paid
    """
    # Get linked Sales Order
    sales_order = get_linked_sales_order(doc)

    if not sales_order:
        # If no Sales Order linked, allow submission (may be a direct Delivery Note)
        return

    # Check if advance invoice exists
    advance_invoice = get_milestone_invoice(sales_order, "advance")

    if not advance_invoice:
        frappe.throw(
            _(
                "Cannot submit Delivery Note. Advance invoice not yet created for Sales Order {0}"
            ).format(sales_order)
        )

    # Check if advance invoice is paid
    if not check_payment_status(advance_invoice):
        frappe.throw(
            _(
                "Cannot submit Delivery Note. Advance payment not received for Sales Invoice {0}. Please collect payment before proceeding with delivery."
            ).format(advance_invoice),
            title=_("Payment Required"),
        )


def on_submit(doc, method=None):
    """
    Create delivery milestone invoice when Delivery Note is submitted
    """
    # Get linked Sales Order
    sales_order = get_linked_sales_order(doc)

    if not sales_order:
        frappe.msgprint(
            _(
                "No Sales Order linked to this Delivery Note. Delivery milestone invoice will not be created."
            ),
            alert=True,
            indicator="orange",
        )
        return

    # Check if delivery invoice already exists
    existing_delivery_invoice = get_milestone_invoice(sales_order, "delivery")

    if existing_delivery_invoice:
        frappe.msgprint(
            _("Delivery invoice already exists: {0}").format(existing_delivery_invoice),
            alert=True,
            indicator="orange",
        )
        return

    # Get Sales Order document to get grand total and payment terms
    so_doc = frappe.get_doc("Sales Order", sales_order)

    # Calculate delivery amount from Payment Terms Template (second tranche)
    delivery_amount = so_doc.grand_total  # Default to full amount
    delivery_percentage = 0

    if so_doc.payment_terms_template:
        # Get the second payment term (Delivery/On Delivery)
        payment_terms = frappe.get_all(
            "Payment Terms Template Detail",
            filters={"parent": so_doc.payment_terms_template},
            fields=["invoice_portion", "description"],
            order_by="idx asc",
            limit=2,  # Get first 2 terms
        )

        # Use the second term if it exists
        if payment_terms and len(payment_terms) >= 2:
            delivery_percentage = flt(payment_terms[1].invoice_portion)
            delivery_amount = (so_doc.grand_total * delivery_percentage) / 100

            frappe.logger().info(
                f"Delivery invoice for SO {sales_order}: {delivery_percentage}% of {so_doc.grand_total} = {delivery_amount}"
            )
        elif payment_terms and len(payment_terms) == 1:
            # If only one term exists, use remaining amount
            first_percentage = flt(payment_terms[0].invoice_portion)
            delivery_percentage = 100 - first_percentage
            delivery_amount = (so_doc.grand_total * delivery_percentage) / 100

    # Create invoice item for delivery milestone
    items = [
        {
            "item_code": "Delivery Payment",
            "item_name": "Delivery Payment",
            "description": _(
                "Delivery payment ({0}%) for Sales Order {1} via Delivery Note {2}"
            ).format(delivery_percentage or 100, sales_order, doc.name),
            "qty": 1,
            "uom": "Nos",
            "rate": delivery_amount,
            "amount": delivery_amount,
        }
    ]

    # Create the invoice
    try:
        invoice = create_milestone_invoice(
            doc,
            "Delivery",
            items,
            description=_(
                "Payment required before installation activities. Amount: {0}% of total"
            ).format(delivery_percentage or 100),
        )

        # Update Sales Order with delivery invoice reference
        frappe.db.set_value(
            "Sales Order",
            sales_order,
            "custom_delivery_invoice",
            invoice.name,
            update_modified=False,
        )

        # Assign To-Do to Accounts Managers
        assign_todo_to_accounts_managers(
            invoice,
            "Delivery Payment",
            description=_(
                "Customer: {0}, Sales Order: {1}, Delivery Amount ({2}%): {3}"
            ).format(
                doc.customer,
                sales_order,
                delivery_percentage or 100,
                frappe.utils.fmt_money(delivery_amount, currency=so_doc.currency),
            ),
        )

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            _("Failed to create delivery invoice for Delivery Note {0}").format(
                doc.name
            ),
        )
        frappe.msgprint(
            _("Failed to create delivery invoice: {0}").format(str(e)),
            alert=True,
            indicator="red",
        )


def get_linked_sales_order(delivery_note):
    """
    Get linked Sales Order from Delivery Note

    Args:
        delivery_note: Delivery Note document

    Returns:
        str: Sales Order name or None
    """
    # First check custom field
    if (
        hasattr(delivery_note, "custom_linked_sales_order")
        and delivery_note.custom_linked_sales_order
    ):
        return delivery_note.custom_linked_sales_order

    # Try to get from items
    if delivery_note.items and len(delivery_note.items) > 0:
        for item in delivery_note.items:
            if hasattr(item, "against_sales_order") and item.against_sales_order:
                # Store in custom field for future reference
                if hasattr(delivery_note, "custom_linked_sales_order"):
                    frappe.db.set_value(
                        "Delivery Note",
                        delivery_note.name,
                        "custom_linked_sales_order",
                        item.against_sales_order,
                        update_modified=False,
                    )
                return item.against_sales_order

    return None
