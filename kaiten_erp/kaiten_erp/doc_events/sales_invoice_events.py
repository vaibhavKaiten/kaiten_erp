# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from kaiten_erp.kaiten_erp.doc_events.tax_bifurcation import fill_tax_bifurcation


def before_insert(doc, method=None):
    _populate_saleable_item(doc)


@frappe.whitelist()
def get_saleable_item_for_si(delivery_note=None, sales_order=None):
    """Return the single saleable item dict for a Sales Invoice.

    Called from the client-side form script so the user sees the
    replacement immediately (before the document is saved / inserted).

    Args:
        delivery_note: DN name (when SI created from DN)
        sales_order: SO name (when SI created from SO)

    Returns:
        dict with keys: item_code, item_name, qty, uom, stock_uom,
              rate, price_list_rate, description, sales_order,
              technical_survey  — or None on any missing prerequisite.
    """
    so_name = sales_order

    # Resolve SO from DN header if needed
    if not so_name and delivery_note:
        so_name = frappe.db.get_value(
            "Delivery Note", delivery_note, "against_sales_order"
        )

    if not so_name:
        return None

    so = frappe.db.get_value(
        "Sales Order",
        so_name,
        ["custom_technical_survey", "grand_total"],
        as_dict=True,
    )
    if not so or not so.custom_technical_survey:
        return None

    ts = frappe.db.get_value(
        "Technical Survey",
        so.custom_technical_survey,
        ["workflow_state", "proposed_system_kw__tier"],
        as_dict=True,
    )
    if not ts or ts.workflow_state != "Approved" or not ts.proposed_system_kw__tier:
        return None

    item_details = frappe.db.get_value(
        "Item",
        ts.proposed_system_kw__tier,
        ["item_name", "stock_uom", "description"],
        as_dict=True,
    )
    if not item_details:
        return None

    return {
        "item_code": ts.proposed_system_kw__tier,
        "item_name": item_details.item_name,
        "qty": 1,
        "uom": item_details.stock_uom,
        "stock_uom": item_details.stock_uom,
        "rate": float(so.grand_total or 0),
        "price_list_rate": float(so.grand_total or 0),
        "description": item_details.description or item_details.item_name,
        "sales_order": so_name,
        "technical_survey": so.custom_technical_survey,
    }


def _populate_saleable_item(doc):
    """
    When a Sales Invoice is created from a Sales Order, replace the default
    BOM-component items with the single saleable system item
    (proposed_system_kw__tier) from the linked Technical Survey.

    Rate is set to the Sales Order's grand_total (full deal value, qty=1).
    Falls back gracefully with a warning if any prerequisite is missing.
    """
    # 1. Resolve Sales Order from SI item rows.
    #    Path A: SI created from SO  → item.sales_order is set directly.
    #    Path B: SI created from DN  → item.delivery_note is set;
    #            resolve SO via DN header's against_sales_order.
    so_name = None
    for item in doc.get("items") or []:
        if item.get("sales_order"):
            so_name = item.sales_order
            break

    if not so_name:
        # Fallback: resolve via Delivery Note
        dn_name = None
        for item in doc.get("items") or []:
            if item.get("delivery_note"):
                dn_name = item.delivery_note
                break
        if dn_name:
            so_name = frappe.db.get_value(
                "Delivery Note", dn_name, "against_sales_order"
            )

    if not so_name:
        return  # SI not linked to any SO — skip silently

    # 2. Fetch SO fields needed
    so = frappe.db.get_value(
        "Sales Order",
        so_name,
        ["custom_technical_survey", "grand_total"],
        as_dict=True,
    )
    if not so:
        return

    ts_name = so.custom_technical_survey
    so_grand_total = float(so.grand_total or 0)

    if not ts_name:
        frappe.msgprint(
            _("No Technical Survey linked to Sales Order {0}. Items were not replaced.").format(so_name),
            title=_("Technical Survey Missing"),
            indicator="orange",
        )
        return

    # 3. Validate Technical Survey state
    ts = frappe.db.get_value(
        "Technical Survey",
        ts_name,
        ["workflow_state", "proposed_system_kw__tier"],
        as_dict=True,
    )
    if not ts:
        return

    if ts.workflow_state != "Approved":
        frappe.msgprint(
            _(
                "Technical Survey {0} is not Approved (state: {1}). "
                "Items were not replaced."
            ).format(ts_name, ts.workflow_state),
            title=_("Technical Survey Not Approved"),
            indicator="orange",
        )
        return

    # 4. Get the saleable item code
    saleable_item_code = ts.proposed_system_kw__tier
    if not saleable_item_code:
        frappe.msgprint(
            _(
                "Technical Survey {0} does not have a Proposed System item set. "
                "Items were not replaced."
            ).format(ts_name),
            title=_("Proposed System Missing"),
            indicator="orange",
        )
        return

    # 5. Fetch item master details
    item_details = frappe.db.get_value(
        "Item",
        saleable_item_code,
        ["item_name", "stock_uom", "description"],
        as_dict=True,
    )
    if not item_details:
        frappe.msgprint(
            _("Item {0} not found. Items were not replaced.").format(saleable_item_code),
            title=_("Item Not Found"),
            indicator="orange",
        )
        return

    # 6. Replace items table with the single saleable system item
    doc.items = []
    doc.append(
        "items",
        {
            "item_code": saleable_item_code,
            "item_name": item_details.item_name,
            "qty": 1,
            "uom": item_details.stock_uom,
            "stock_uom": item_details.stock_uom,
            "rate": so_grand_total,
            "price_list_rate": so_grand_total,
            "description": item_details.description or item_details.item_name,
            "sales_order": so_name,
        },
    )

    # 7. Populate header traceability custom fields
    doc.custom_technical_survey = ts_name
    doc.custom_sales_order = so_name


@frappe.whitelist()
def make_sales_invoice_from_dn(source_name, target_doc=None, args=None):
    """Override ERPNext's make_sales_invoice to replace BOM items with the
    single saleable system item from the linked Technical Survey."""
    from erpnext.stock.doctype.delivery_note.delivery_note import (
        make_sales_invoice as _original_make_sales_invoice,
    )

    si = _original_make_sales_invoice(source_name, target_doc=target_doc, args=args)

    # Resolve SO from DN header
    so_name = frappe.db.get_value("Delivery Note", source_name, "against_sales_order")
    if not so_name:
        return si

    saleable = get_saleable_item_for_si(delivery_note=source_name, sales_order=so_name)
    if not saleable:
        return si

    # Replace items with the single saleable item
    si.items = []
    si.append(
        "items",
        {
            "item_code": saleable["item_code"],
            "item_name": saleable["item_name"],
            "qty": saleable["qty"],
            "uom": saleable["uom"],
            "stock_uom": saleable["stock_uom"],
            "conversion_factor": 1,
            "rate": saleable["rate"],
            "price_list_rate": saleable["price_list_rate"],
            "description": saleable["description"],
            "sales_order": saleable["sales_order"],
            "delivery_note": source_name,
        },
    )

    si.custom_technical_survey = saleable["technical_survey"]
    si.custom_sales_order = saleable["sales_order"]

    return si


def validate(doc, method=None):
    _set_place_of_supply(doc)
    fill_tax_bifurcation(doc)


def _set_place_of_supply(doc):
    """Ensure place_of_supply is set before india_compliance GST validations run.

    india_compliance crashes with a TypeError if place_of_supply is None.
    Priority:
      1. india_compliance's own get_place_of_supply (uses customer address/GSTIN)
      2. Fallback: derive state from company_gstin (in-state supply assumption)
    """
    if doc.get("place_of_supply"):
        return

    # 1. Try india_compliance's own logic (uses customer address / GSTIN)
    try:
        from india_compliance.gst_india.utils import get_place_of_supply

        pos = get_place_of_supply(doc, "Sales Invoice")
        if pos:
            doc.place_of_supply = pos
            return
    except Exception:
        pass

    # 2. Fallback: derive from company GSTIN state code (first 2 digits)
    try:
        from india_compliance.gst_india.constants import STATE_NUMBERS

        company_gstin = doc.get("company_gstin") or ""
        if len(company_gstin) >= 2:
            state_code = company_gstin[:2]
            # STATE_NUMBERS is {state_name: code}, so invert it
            code_to_state = {v: k for k, v in STATE_NUMBERS.items()}
            state_name = code_to_state.get(state_code)
            if state_name:
                doc.place_of_supply = f"{state_code}-{state_name}"
    except Exception:
        pass
