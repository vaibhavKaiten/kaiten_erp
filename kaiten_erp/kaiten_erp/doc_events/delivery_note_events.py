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

    so = frappe.db.get_value(
        "Sales Order",
        sales_order_name,
        ["custom_technical_survey", "selling_price_list", "currency"],
        as_dict=True,
    )
    if not so:
        return []

    technical_survey_name = so.custom_technical_survey
    selling_price_list = so.selling_price_list

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

    # Get valuation rates from Bin (stock reconciliation)
    valuation_rate_map = _get_valuation_rate_map(list(survey_items.keys()))

    delivered_rows = frappe.db.sql(
        """
        SELECT dni.item_code, SUM(dni.qty) AS delivered_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.docstatus = 1
          AND (
              dni.against_sales_order = %(so)s
              OR dn.against_sales_order = %(so)s
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
            rate = valuation_rate_map.get(item_code, 0.0)
            result.append(
                {
                    "item_code": item_code,
                    "item_name": frappe.db.get_value("Item", item_code, "item_name") or item_code,
                    "qty": remaining,
                    "uom": meta["uom"],
                    "stock_uom": meta["uom"],
                    "rate": rate,
                    "price_list_rate": rate,
                }
            )
    return result


def _get_valuation_rate_map(item_codes):
    """
    Return {item_code: valuation_rate} from tabBin (stock reconciliation rates).
    Takes the MAX non-zero valuation_rate across all warehouses per item.
    Falls back to 0 if no stock entry exists.
    """
    if not item_codes:
        return {}
    placeholders = ", ".join(["%s"] * len(item_codes))
    rows = frappe.db.sql(
        f"""SELECT item_code, MAX(valuation_rate) AS valuation_rate
            FROM `tabBin`
            WHERE item_code IN ({placeholders}) AND valuation_rate > 0
            GROUP BY item_code""",
        item_codes,
        as_dict=True,
    )
    return {r.item_code: float(r.valuation_rate or 0) for r in rows}


def validate(doc, method=None):
    pass


def on_submit(doc, method=None):
    """Close Stock Manager todos, sync SO delivery %, and trigger SF chain todos."""
    _close_delivery_note_todos(doc)
    _sync_so_delivery_percent(doc)
    _sf_create_structure_mounting_vh_todo(doc)
    _sf_check_remaining_delivery_and_create_pi_todo(doc)


def on_cancel(doc, method=None):
    """Re-sync SO delivery % when Delivery Note is cancelled."""
    _sync_so_delivery_percent(doc)


def _close_delivery_note_todos(doc):
    sales_orders = set()
    for item in doc.get("items") or []:
        if item.get("against_sales_order"):
            sales_orders.add(item.against_sales_order)

    if not sales_orders:
        return

    for so in sales_orders:
        todos = frappe.db.get_all(
            "ToDo",
            filters={
                "reference_type": "Delivery Note",
                "status": "Open",
                "description": ["like", f"%| SO: {so}%"],
            },
            fields=["name"],
        )
        for todo in todos:
            frappe.db.set_value(
                "ToDo", todo.name, "status", "Closed", update_modified=False
            )


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

    # ── 4. Build valuation rate map from tabBin (stock reconciliation) ─────────
    # Collect item codes first; we'll build the map after survey_items is built.
    # Done after step 5 below.

    # ── 5. Build survey qty map: item_code → {qty, uom, warehouse} ───────────
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

    # ── 6. Build valuation rate map from Bin for all items ───────────────────
    valuation_rate_map = _get_valuation_rate_map(list(survey_items.keys()))

    # ── 7. Build delivered qty map from submitted DNs ─────────────────────────
    # Match by against_sales_order on item rows OR by against_sales_order
    # on the DN header.
    delivered_rows = frappe.db.sql(
        """
        SELECT dni.item_code, SUM(dni.qty) AS delivered_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.docstatus = 1
          AND (
              dni.against_sales_order = %(so)s
              OR dn.against_sales_order = %(so)s
          )
        GROUP BY dni.item_code
        """,
        {"so": sales_order_name},
        as_dict=True,
    )
    delivered_map = {row.item_code: float(row.delivered_qty or 0) for row in delivered_rows}

    # ── 8. Compute remaining qty and build filtered list ─────────────────────
    remaining_items = []
    for item_code, meta in survey_items.items():
        already_delivered = delivered_map.get(item_code, 0.0)
        remaining = meta["qty"] - already_delivered
        if remaining > 0:
            rate = valuation_rate_map.get(item_code, 0.0)
            remaining_items.append(
                {
                    "item_code": item_code,
                    "qty": remaining,
                    "uom": meta["uom"],
                    "warehouse": meta["warehouse"],
                    "rate": rate,
                    "price_list_rate": rate,
                    "against_sales_order": sales_order_name,
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

    # ── 8. Ensure against_sales_order is set on DN header ─────────────────
    if not doc.against_sales_order:
        doc.against_sales_order = sales_order_name



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


def _sync_so_delivery_percent(doc):
    """
    Manually compute per_delivered on the linked Sales Order based on
    how much of the Technical Survey BOM items have been delivered.

    Needed because SO items (saleable item, qty=1) differ from DN items
    (BOM components), so ERPNext's standard update_delivery_status cannot
    calculate per_delivered correctly.
    """
    so_name = get_linked_sales_order(doc)
    if not so_name:
        return

    ts_name = frappe.db.get_value("Sales Order", so_name, "custom_technical_survey")
    if not ts_name:
        return  # No TS — let standard ERPNext mechanism handle it

    ts = frappe.get_doc("Technical Survey", ts_name)

    # Build survey qty map
    survey_items = {}

    def _add(item_code, qty_raw):
        if not item_code:
            return
        try:
            qty = float(qty_raw or 0)
        except (ValueError, TypeError):
            return
        if qty <= 0:
            return
        survey_items[item_code] = survey_items.get(item_code, 0.0) + qty

    if ts.panel:
        _add(ts.panel, ts.panel_qty_bom)
    if ts.inverter:
        _add(ts.inverter, ts.inverter_qty_bom)
    if ts.battery:
        _add(ts.battery, ts.battery_qty_bom)
    for row in ts.get("table_vctx") or []:
        _add(row.item_code, row.qty)

    if not survey_items:
        return

    total_survey_qty = sum(survey_items.values())
    if total_survey_qty <= 0:
        return

    # Sum delivered qty from all submitted DNs for this SO
    delivered_rows = frappe.db.sql(
        """
        SELECT dni.item_code, SUM(dni.qty) AS delivered_qty
        FROM `tabDelivery Note Item` dni
        INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.docstatus = 1
          AND (
              dni.against_sales_order = %(so)s
              OR dn.against_sales_order = %(so)s
          )
        GROUP BY dni.item_code
        """,
        {"so": so_name},
        as_dict=True,
    )
    delivered_map = {r.item_code: float(r.delivered_qty or 0) for r in delivered_rows}

    # Cap each item at survey qty to avoid >100%
    total_delivered = sum(
        min(delivered_map.get(item_code, 0.0), qty)
        for item_code, qty in survey_items.items()
    )

    per_delivered = round((total_delivered / total_survey_qty) * 100, 2)
    per_delivered = min(per_delivered, 100.0)

    if per_delivered >= 100.0:
        delivery_status = "Fully Delivered"
    elif per_delivered > 0:
        delivery_status = "Partly Delivered"
    else:
        delivery_status = "Not Delivered"

    frappe.db.set_value(
        "Sales Order",
        so_name,
        {
            "per_delivered": per_delivered,
            "delivery_status": delivery_status,
        },
        update_modified=False,
    )


def get_linked_sales_order(delivery_note):
    """Get linked Sales Order name from a Delivery Note document."""
    if delivery_note.against_sales_order:
        return delivery_note.against_sales_order

    for item in delivery_note.items or []:
        if item.get("against_sales_order"):
            frappe.db.set_value(
                "Delivery Note",
                delivery_note.name,
                "against_sales_order",
                item.against_sales_order,
                update_modified=False,
            )
            return item.against_sales_order

    return None


# ---------------------------------------------------------------------------
# Self Finance: VH "Initiate Structure Mounting" on first DN submit
# ---------------------------------------------------------------------------

def _sf_create_structure_mounting_vh_todo(doc):
    """
    When a Delivery Note is submitted for a Self Finance Sales Order,
    create a Vendor Head todo to Initiate Structure Mounting.

    Skips if:
      - Structure Mounting is already Approved (e.g. second DN for remaining items)
      - A VH todo already exists for that SM doc (dedup inside _sf_create_vh_todo_for_next)
    """
    so_name = get_linked_sales_order(doc)
    if not so_name:
        return

    # Check Self Finance
    finance_type = frappe.db.get_value("Sales Order", so_name, "custom_finance_type")
    if (finance_type or "").strip() != "Self Finance":
        return

    # Get Job File from SO
    job_file_name = frappe.db.get_value("Sales Order", so_name, "custom_job_file")
    if not job_file_name:
        return

    # If Structure Mounting is already Approved, skip — this is a later DN (remaining items)
    sm_name = frappe.db.get_value("Job File", job_file_name, "custom_structure_mounting")
    if sm_name:
        sm_state = frappe.db.get_value("Structure Mounting", sm_name, "workflow_state")
        if sm_state == "Approved":
            return

    from kaiten_erp.kaiten_erp.doc_events.sales_order_events import _sf_create_vh_todo_for_next
    _sf_create_vh_todo_for_next(job_file_name, "Structure Mounting", "custom_structure_mounting")


def _sf_check_remaining_delivery_and_create_pi_todo(doc):
    """
    After a DN is submitted for a Self Finance SO where Structure is Paid
    and all items are now delivered, close the 'Transfer Remaining Materials'
    Stock Manager todo and create a VH todo for Project Installation.
    """
    so_name = get_linked_sales_order(doc)
    if not so_name:
        return

    finance_type = frappe.db.get_value("Sales Order", so_name, "custom_finance_type")
    if (finance_type or "").strip() != "Self Finance":
        return

    # Only act if Structure milestone is Paid
    so_doc = frappe.get_doc("Sales Order", so_name)
    milestones = so_doc.get("custom_payment_plan") or []
    structure_row = next((r for r in milestones if r.milestone == "Structure"), None)
    if not structure_row or (structure_row.status or "Pending") != "Paid":
        return

    per_delivered = float(frappe.db.get_value("Sales Order", so_name, "per_delivered") or 0)
    if per_delivered < 100.0:
        return

    job_file_name = so_doc.get("custom_job_file")
    if not job_file_name:
        return

    # Close remaining transfer todos
    from kaiten_erp.kaiten_erp.doc_events.sales_order_events import (
        _sf_close_remaining_transfer_todos,
        _sf_create_vh_todo_for_next,
    )
    _sf_close_remaining_transfer_todos(so_name)
    _sf_create_vh_todo_for_next(job_file_name, "Project Installation", "custom_project_installation")