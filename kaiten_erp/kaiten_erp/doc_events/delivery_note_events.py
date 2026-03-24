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
    is_self_funding_order,
)


def validate(doc, method=None):
    """
    Validate Delivery Note before submission
    Block submission if advance invoice is not paid (self-funding orders only)
    """
    # Get linked Sales Order
    sales_order = get_linked_sales_order(doc)

    if not sales_order:
        # If no Sales Order linked, allow submission (may be a direct Delivery Note)
        return

    # Only enforce payment gate for self-funding orders
    if not is_self_funding_order(sales_order):
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
    # """
    # Create delivery milestone invoice when Delivery Note is submitted
    # Only applies to self-funding orders.
    # """
    # # Get linked Sales Order
    # sales_order = get_linked_sales_order(doc)

    # if not sales_order:
    #     frappe.msgprint(
    #         _(
    #             "No Sales Order linked to this Delivery Note. Delivery milestone invoice will not be created."
    #         ),
    #         alert=True,
    #         indicator="orange",
    #     )
    #     return

    # # Only create delivery invoice for self-funding orders
    # if not is_self_funding_order(sales_order):
    #     return

    # # Check if delivery invoice already exists
    # existing_delivery_invoice = get_milestone_invoice(sales_order, "delivery")

    # if existing_delivery_invoice:
    #     frappe.msgprint(
    #         _("Delivery invoice already exists: {0}").format(existing_delivery_invoice),
    #         alert=True,
    #         indicator="orange",
    #     )
    #     return

    # # Get Sales Order document to get grand total and payment terms
    # so_doc = frappe.get_doc("Sales Order", sales_order)

    # # Calculate delivery amount from Payment Terms Template (second tranche)
    # delivery_amount = so_doc.grand_total  # Default to full amount
    # delivery_percentage = 0

    # if so_doc.payment_terms_template:
    #     # Get the second payment term (Delivery/On Delivery)
    #     payment_terms = frappe.get_all(
    #         "Payment Terms Template Detail",
    #         filters={"parent": so_doc.payment_terms_template},
    #         fields=["invoice_portion", "description"],
    #         order_by="idx asc",
    #         limit=2,  # Get first 2 terms
    #     )

    #     # Use the second term if it exists
    #     if payment_terms and len(payment_terms) >= 2:
    #         delivery_percentage = flt(payment_terms[1].invoice_portion)
    #         delivery_amount = (so_doc.grand_total * delivery_percentage) / 100

    #         frappe.logger().info(
    #             f"Delivery invoice for SO {sales_order}: {delivery_percentage}% of {so_doc.grand_total} = {delivery_amount}"
    #         )
    #     elif payment_terms and len(payment_terms) == 1:
    #         # If only one term exists, use remaining amount
    #         first_percentage = flt(payment_terms[0].invoice_portion)
    #         delivery_percentage = 100 - first_percentage
    #         delivery_amount = (so_doc.grand_total * delivery_percentage) / 100

    # # Create invoice item for delivery milestone
    # items = [
    #     {
    #         "item_code": "Delivery Payment",
    #         "item_name": "Delivery Payment",
    #         "description": _(
    #             "Delivery payment ({0}%) for Sales Order {1} via Delivery Note {2}"
    #         ).format(delivery_percentage or 100, sales_order, doc.name),
    #         "qty": 1,
    #         "uom": "Nos",
    #         "rate": delivery_amount,
    #         "amount": delivery_amount,
    #     }
    # ]

    # # Create the invoice
    # try:
    #     invoice = create_milestone_invoice(
    #         doc,
    #         "Delivery",
    #         items,
    #         description=_(
    #             "Payment required before installation activities. Amount: {0}% of total"
    #         ).format(delivery_percentage or 100),
    #     )

    #     # Update Sales Order with delivery invoice reference
    #     frappe.db.set_value(
    #         "Sales Order",
    #         sales_order,
    #         "custom_delivery_invoice",
    #         invoice.name,
    #         update_modified=False,
    #     )

    #     # Assign To-Do to Accounts Managers
    #     assign_todo_to_accounts_managers(
    #         invoice,
    #         "Delivery Payment",
    #         description=_(
    #             "Customer: {0}, Sales Order: {1}, Delivery Amount ({2}%): {3}"
    #         ).format(
    #             doc.customer,
    #             sales_order,
    #             delivery_percentage or 100,
    #             frappe.utils.fmt_money(delivery_amount, currency=so_doc.currency),
    #         ),
    #     )

    #     frappe.db.commit()

    # except Exception as e:
    #     frappe.log_error(
    #         frappe.get_traceback(),
    #         _("Failed to create delivery invoice for Delivery Note {0}").format(
    #             doc.name
    #         ),
    #     )
    #     frappe.msgprint(
    #         _("Failed to create delivery invoice: {0}").format(str(e)),
    #         alert=True,
    #         indicator="red",
    #     )


def populate_items_from_technical_survey(doc, method=None):
    """
    Before-insert hook: replace Delivery Note items with the BOM from the
    Technical Survey linked to the source Sales Order.

    Runs exactly once — on document creation — because `before_insert`
    does not fire on subsequent saves.
    """
    # ── 1. Resolve Sales Order ────────────────────────────────────────────────
    # ERPNext has already populated doc.items from the SO at this point;
    # read the SO reference before we potentially clear the table.
    sales_order_name = None
    item_debug = [(item.get("item_code"), item.get("against_sales_order")) for item in doc.get("items") or []]
    frappe.log_error(f"[DN TS Populate] items at before_insert: {item_debug}", "DN TS Debug")

    for item in doc.get("items") or []:
        if item.get("against_sales_order"):
            sales_order_name = item.against_sales_order
            break

    frappe.log_error(f"[DN TS Populate] sales_order_name resolved: {sales_order_name}", "DN TS Debug")

    if not sales_order_name:
        # No SO linked — leave items untouched (direct Delivery Note)
        return

    # ── 2. Resolve Technical Survey ───────────────────────────────────────────
    technical_survey_name = frappe.db.get_value(
        "Sales Order", sales_order_name, "custom_technical_survey"
    )
    frappe.log_error(f"[DN TS Populate] technical_survey_name: {technical_survey_name}", "DN TS Debug")

    if not technical_survey_name:
        # SO has no Technical Survey — leave items untouched
        return

    # ── 3. Load Technical Survey doc ──────────────────────────────────────────
    technical_survey = frappe.get_doc("Technical Survey", technical_survey_name)

    # ── 4. Approved-state guard ───────────────────────────────────────────────
    if technical_survey.workflow_state != "Approved":
        doc.set("items", [])
        frappe.msgprint(
            _(
                "Technical Survey {0} is not Approved (current state: {1}). "
                "Delivery Note items have been cleared. "
                "Please get the Technical Survey approved before creating a Delivery Note."
            ).format(technical_survey_name, technical_survey.workflow_state),
            title=_("Technical Survey Not Approved"),
            indicator="red",
        )
        return

    # ── 5. Full replacement — clear whatever ERPNext pulled from the SO ────────
    doc.set("items", [])

    # ── 6. Default warehouse ──────────────────────────────────────────────────
    _warehouse = doc.set_warehouse or None

    # ── 7. Collect items from Technical Survey system configuration ───────────
    collected_items = []

    # Panel
    if technical_survey.panel and technical_survey.panel_qty_bom:
        try:
            qty = float(technical_survey.panel_qty_bom)
            if qty > 0:
                collected_items.append(
                    {
                        "item_code": technical_survey.panel,
                        "qty": qty,
                        "uom": frappe.db.get_value(
                            "Item", technical_survey.panel, "stock_uom"
                        ) or "Nos",
                        "warehouse": _warehouse,
                    }
                )
        except (ValueError, TypeError):
            frappe.log_error(
                f"Invalid panel_qty_bom in Technical Survey {technical_survey_name}: "
                f"{technical_survey.panel_qty_bom}",
                "Delivery Note item population",
            )

    # Inverter
    if technical_survey.inverter and technical_survey.inverter_qty_bom:
        try:
            qty = float(technical_survey.inverter_qty_bom)
            if qty > 0:
                collected_items.append(
                    {
                        "item_code": technical_survey.inverter,
                        "qty": qty,
                        "uom": frappe.db.get_value(
                            "Item", technical_survey.inverter, "stock_uom"
                        ) or "Nos",
                        "warehouse": _warehouse,
                    }
                )
        except (ValueError, TypeError):
            frappe.log_error(
                f"Invalid inverter_qty_bom in Technical Survey {technical_survey_name}: "
                f"{technical_survey.inverter_qty_bom}",
                "Delivery Note item population",
            )

    # Battery
    if technical_survey.battery and technical_survey.battery_qty_bom:
        try:
            qty = float(technical_survey.battery_qty_bom)
            if qty > 0:
                collected_items.append(
                    {
                        "item_code": technical_survey.battery,
                        "qty": qty,
                        "uom": frappe.db.get_value(
                            "Item", technical_survey.battery, "stock_uom"
                        ) or "Nos",
                        "warehouse": _warehouse,
                    }
                )
        except (ValueError, TypeError):
            frappe.log_error(
                f"Invalid battery_qty_bom in Technical Survey {technical_survey_name}: "
                f"{technical_survey.battery_qty_bom}",
                "Delivery Note item population",
            )

    # BOM items from table_vctx child table
    for bom_row in technical_survey.get("table_vctx") or []:
        if not (bom_row.item_code and bom_row.qty):
            continue
        try:
            qty = float(bom_row.qty)
            if qty > 0:
                collected_items.append(
                    {
                        "item_code": bom_row.item_code,
                        "qty": qty,
                        "uom": getattr(bom_row, "uom", None) or "Nos",
                        "warehouse": getattr(bom_row, "warehouse", None) or _warehouse,
                    }
                )
        except (ValueError, TypeError):
            frappe.log_error(
                f"Invalid qty for item {bom_row.item_code} in Technical Survey "
                f"{technical_survey_name}: {bom_row.qty}",
                "Delivery Note item population",
            )

    # ── 8. Guard: nothing to add ──────────────────────────────────────────────
    if not collected_items:
        frappe.msgprint(
            _(
                "Technical Survey {0} has no items configured in it's System Configuration. "
                "Delivery Note items table is empty."
            ).format(technical_survey_name),
            title=_("No Items in Technical Survey"),
            indicator="orange",
        )
        return

    # ── 9. Append items (no against_sales_order — pure TS-sourced rows) ───────
    for item_data in collected_items:
        doc.append("items", item_data)

    frappe.msgprint(
        _(
            "Delivery Note items populated from Technical Survey {0} ({1} items)."
        ).format(technical_survey_name, len(collected_items)),
        alert=True,
        indicator="green",
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
