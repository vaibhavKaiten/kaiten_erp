# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Delivery Note event handlers.
Phase-wise delivery: only items with remaining qty > 0 (survey qty minus
already-submitted DNs for the same SO) are added on before_insert.
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_remaining_ts_items(sales_order_name):
    """
    API called client-side on DN form load.
    Returns remaining Technical Survey items (survey qty minus submitted DNs).
    """
    if not sales_order_name:
        return []

    technical_survey_name = frappe.db.get_value(
        "Sales Order", sales_order_name, "custom_technical_survey"
    )
    if not technical_survey_name:
        return []

    technical_survey = frappe.get_doc("Technical Survey", technical_survey_name)
    if technical_survey.workflow_state != "Approved":
        frappe.throw(
            _(
                "Technical Survey {0} is not Approved (state: {1}). "
                "Please get it approved before creating a Delivery Note."
            ).format(technical_survey_name, technical_survey.workflow_state),
            title=_("Technical Survey Not Approved"),
        )

    survey_items = {}

    def _add(item_code, qty_raw, uom):
        if not item_code:
            return
        try:
            qty = float(qty_raw or 0)
        except (ValueError, TypeError):
            return
        if qty <= 0:
            return
        resolved_uom = uom or frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
        if item_code in survey_items:
            survey_items[item_code]["qty"] += qty
        else:
            survey_items[item_code] = {"qty": qty, "uom": resolved_uom}

    if technical_survey.panel:
        _add(
            technical_survey.panel,
            technical_survey.panel_qty_bom,
            frappe.db.get_value("Item", technical_survey.panel, "stock_uom"),
        )
    if technical_survey.inverter:
        _add(
            technical_survey.inverter,
            technical_survey.inverter_qty_bom,
            frappe.db.get_value("Item", technical_survey.inverter, "stock_uom"),
        )
    if technical_survey.battery:
        _add(
            technical_survey.battery,
            technical_survey.battery_qty_bom,
            frappe.db.get_value("Item", technical_survey.battery, "stock_uom"),
        )
    for row in technical_survey.get("table_vctx") or []:
        _add(row.item_code, row.qty, getattr(row, "uom", None))

    if not survey_items:
        return []

    delivered_rows = frappe.db.sql(
        """
        SELECT dni.item_code, SUM(dni.qty) AS delivered_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.docstatus = 1
          AND (
              dni.against_sales_order = %(so)s
              OR dn.custom_linked_sales_order = %(so)s
          )
        GROUP BY dni.item_code
        """,
        {"so": sales_order_name},
        as_dict=True,
    )
    delivered_map = {r.item_code: float(r.delivered_qty or 0) for r in delivered_rows}

    result = []
    for item_code, meta in survey_items.items():
        remaining = meta["qty"] - delivered_map.get(item_code, 0.0)
        if remaining > 0:
            result.append(
                {
                    "item_code": item_code,
                    "item_name": frappe.db.get_value("Item", item_code, "item_name") or item_code,
                    "qty": remaining,
                    "uom": meta["uom"],
                    "stock_uom": meta["uom"],
                }
            )
    return result


def validate(doc, method=None):
    pass


def on_submit(doc, method=None):
    pass


def populate_items_from_technical_survey(doc, method=None):
    """
    Before-insert hook: replace Delivery Note items with REMAINING BOM qty
    from the Approved Technical Survey linked to the source Sales Order.

    Phase-wise delivery logic:
      Survey Qty    = qty defined in the Approved Technical Survey
      Delivered Qty = SUM(qty) from submitted (docstatus=1) DN Items
                      where against_sales_order = current SO
      Remaining Qty = Survey Qty - Delivered Qty

    Items with Remaining Qty <= 0 are excluded.
    Runs exactly once per document (before_insert does not fire on re-save).
    """
    # ── 1. Resolve Sales Order ────────────────────────────────────────────────
    sales_order_name = None
    for item in doc.get("items") or []:
        if item.get("against_sales_order"):
            sales_order_name = item.against_sales_order
            break

    if not sales_order_name:
        return  # Direct DN — leave untouched

    # ── 2. Resolve Technical Survey ───────────────────────────────────────────
    technical_survey_name = frappe.db.get_value(
        "Sales Order", sales_order_name, "custom_technical_survey"
    )
    if not technical_survey_name:
        return  # No TS linked on SO — leave untouched

    # ── 3. Load and validate Technical Survey state ───────────────────────────
    technical_survey = frappe.get_doc("Technical Survey", technical_survey_name)

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

    # ── 4. Build survey qty map: item_code → {qty, uom, warehouse} ────────────
    _warehouse = doc.set_warehouse or None
    survey_items = {}  # { item_code: {qty, uom, warehouse} }

    def _add(item_code, qty_raw, uom, warehouse):
        if not item_code:
            return
        try:
            qty = float(qty_raw or 0)
        except (ValueError, TypeError):
            return
        if qty <= 0:
            return
        resolved_uom = uom or frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
        resolved_wh = warehouse or _warehouse
        if item_code in survey_items:
            survey_items[item_code]["qty"] += qty
        else:
            survey_items[item_code] = {"qty": qty, "uom": resolved_uom, "warehouse": resolved_wh}

    # Main component fields — fetch stock_uom from Item master
    if technical_survey.panel:
        _add(
            technical_survey.panel,
            technical_survey.panel_qty_bom,
            frappe.db.get_value("Item", technical_survey.panel, "stock_uom"),
            _warehouse,
        )
    if technical_survey.inverter:
        _add(
            technical_survey.inverter,
            technical_survey.inverter_qty_bom,
            frappe.db.get_value("Item", technical_survey.inverter, "stock_uom"),
            _warehouse,
        )
    if technical_survey.battery:
        _add(
            technical_survey.battery,
            technical_survey.battery_qty_bom,
            frappe.db.get_value("Item", technical_survey.battery, "stock_uom"),
            _warehouse,
        )

    # BOM child table (table_vctx)
    for row in technical_survey.get("table_vctx") or []:
        _add(
            row.item_code,
            row.qty,
            getattr(row, "uom", None),
            getattr(row, "warehouse", None),
        )

    if not survey_items:
        doc.set("items", [])
        frappe.msgprint(
            _("Technical Survey {0} has no items in its System Configuration.").format(
                technical_survey_name
            ),
            title=_("No Items in Technical Survey"),
            indicator="orange",
        )
        return

    # ── 5. Build delivered qty map from submitted DNs ─────────────────────────
    # Match by against_sales_order on item rows OR by custom_linked_sales_order
    # on the DN header (our before_insert hook creates items that may not have
    # against_sales_order set on older DNs).
    delivered_rows = frappe.db.sql(
        """
        SELECT dni.item_code, SUM(dni.qty) AS delivered_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.docstatus = 1
          AND (
              dni.against_sales_order = %(so)s
              OR dn.custom_linked_sales_order = %(so)s
          )
        GROUP BY dni.item_code
        """,
        {"so": sales_order_name},
        as_dict=True,
    )
    delivered_map = {row.item_code: float(row.delivered_qty or 0) for row in delivered_rows}

    # ── 6. Compute remaining qty and build filtered list ──────────────────────
    remaining_items = []
    for item_code, meta in survey_items.items():
        already_delivered = delivered_map.get(item_code, 0.0)
        remaining = meta["qty"] - already_delivered
        if remaining > 0:
            remaining_items.append(
                {
                    "item_code": item_code,
                    "qty": remaining,
                    "uom": meta["uom"],
                    "warehouse": meta["warehouse"],
                }
            )

    # ── 7. Replace items table ────────────────────────────────────────────────
    doc.set("items", [])

    if not remaining_items:
        frappe.msgprint(
            _(
                "All items from Technical Survey {0} have already been fully delivered "
                "for Sales Order {1}. No items to add to this Delivery Note."
            ).format(technical_survey_name, sales_order_name),
            title=_("All Items Already Delivered"),
            indicator="orange",
        )
        return

    # ── 8. Ensure custom_linked_sales_order is set on DN header ─────────────
    # We do NOT set against_sales_order / so_detail on item rows because our
    # items are BOM components from the Technical Survey — they don't exist as
    # individual Sales Order Item rows.  ERPNext validate requires both fields
    # together, but the SO typically has only the parent BOM item (e.g.
    # "Solar System 2") while the TS explodes it into components (panel,
    # inverter, clamps, etc.).  Instead we track the SO link on the DN header
    # via custom_linked_sales_order.
    if hasattr(doc, "custom_linked_sales_order") and not doc.custom_linked_sales_order:
        doc.custom_linked_sales_order = sales_order_name

    # ── 9. Append remaining items ─────────────────────────────────────────────
    for item_data in remaining_items:
        doc.append("items", item_data)

    frappe.msgprint(
        _(
            "Delivery Note items populated from Technical Survey {0}. "
            "{1} item(s) with remaining quantity."
        ).format(technical_survey_name, len(remaining_items)),
        alert=True,
        indicator="green",
    )


def get_linked_sales_order(delivery_note):
    """Get linked Sales Order name from a Delivery Note document."""
    if (
        hasattr(delivery_note, "custom_linked_sales_order")
        and delivery_note.custom_linked_sales_order
    ):
        return delivery_note.custom_linked_sales_order

    for item in delivery_note.items or []:
        if hasattr(item, "against_sales_order") and item.against_sales_order:
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