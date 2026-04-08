# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Stock Entry event handlers.

Handles auto-close and auto-reopen of Stock Manager Material Transfer ToDos
based on the status of the primary Material Request (linked via Technical Survey)
for each Sales Order.
"""

import frappe
from kaiten_erp.kaiten_erp.doc_events.sales_order_events import (
    _close_stock_transfer_todos,
    _create_stock_manager_transfer_todo,
)


def _get_primary_mr_sales_orders(stock_entry_doc):
    """
    Collect (material_request_name, sales_order_name) pairs for all
    *primary* Material Requests referenced in this Stock Entry's items.

    A primary MR is one created from a Technical Survey
    (custom_source_technical_survey is set). Shortage MRs are excluded.

    Returns a dict: {mr_name: sales_order_name}
    """
    mr_to_so = {}
    seen_mrs = set()

    for item in stock_entry_doc.get("items") or []:
        mr_name = item.get("material_request")
        if not mr_name or mr_name in seen_mrs:
            continue
        seen_mrs.add(mr_name)

        mr_data = frappe.db.get_value(
            "Material Request",
            mr_name,
            ["custom_source_technical_survey", "custom_source_sales_order", "status", "per_ordered"],
            as_dict=True,
        )
        if not mr_data:
            continue

        # Only act on primary MRs (linked to a Technical Survey)
        if not mr_data.get("custom_source_technical_survey"):
            continue

        sales_order = mr_data.get("custom_source_sales_order")
        if not sales_order:
            continue

        mr_to_so[mr_name] = {
            "sales_order": sales_order,
            "status": mr_data.get("status"),
            "per_ordered": float(mr_data.get("per_ordered") or 0),
        }

    return mr_to_so


def on_submit(doc, method=None):
    """
    Stock Entry on_submit hook.
    When the primary Material Request reaches status 'Transferred' (fully fulfilled),
    close all open Stock Manager Material Transfer ToDos for the linked Sales Order.
    """
    if doc.stock_entry_type != "Material Transfer":
        return

    mr_map = _get_primary_mr_sales_orders(doc)

    for mr_name, info in mr_map.items():
        mr_status = info["status"]
        sales_order = info["sales_order"]

        if mr_status == "Transferred":
            _close_stock_transfer_todos(sales_order)
            frappe.logger("kaiten_erp").info(
                f"Closed Stock Manager transfer ToDos for Sales Order {sales_order} "
                f"— MR {mr_name} is now Transferred"
            )


def on_cancel(doc, method=None):
    """
    Stock Entry on_cancel hook.
    When a Stock Entry is cancelled, the MR may revert from 'Transferred' back to
    a lower status. If the first payment milestone on the Sales Order is still 'Paid',
    create a new Stock Manager ToDo so the transfer gets picked up again.
    """
    if doc.stock_entry_type != "Material Transfer":
        return

    mr_map = _get_primary_mr_sales_orders(doc)

    for mr_name, info in mr_map.items():
        mr_status = info["status"]
        sales_order = info["sales_order"]

        # MR reverted from Transferred — check if action is still needed
        if mr_status != "Transferred":
            so_doc = frappe.get_doc("Sales Order", sales_order)
            milestones = so_doc.get("custom_payment_plan") or []
            if not milestones:
                continue

            first_row = min(milestones, key=lambda r: r.idx)
            if (first_row.status or "Pending") == "Paid":
                # First milestone is still paid — recreate the transfer ToDo
                _create_stock_manager_transfer_todo(so_doc)
                frappe.logger("kaiten_erp").info(
                    f"Recreated Stock Manager transfer ToDo for Sales Order {sales_order} "
                    f"— MR {mr_name} reverted from Transferred after Stock Entry cancel"
                )
