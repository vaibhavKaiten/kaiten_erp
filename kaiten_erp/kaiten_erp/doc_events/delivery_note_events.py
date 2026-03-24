# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Delivery Note event handlers for milestone-based invoicing
Validates advance payment and creates delivery milestone invoice
"""

import frappe
from frappe import _


def validate(doc, method=None):
    pass


def on_submit(doc, method=None):
    pass



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

    for item in doc.get("items") or []:
        if item.get("against_sales_order"):
            sales_order_name = item.against_sales_order
            break

    if not sales_order_name:
        # No SO linked — leave items untouched (direct Delivery Note)
        return

    # ── 2. Resolve Technical Survey ───────────────────────────────────────────
    technical_survey_name = frappe.db.get_value(
        "Sales Order", sales_order_name, "custom_technical_survey"
    )

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
