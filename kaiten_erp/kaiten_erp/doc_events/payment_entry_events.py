# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Payment Entry event handlers — auto-close / reopen 'Create Payment Entry' ToDos
linked to Sales Order Payment Milestone rows.

Chain: Payment Entry → references → Sales Invoice → milestone row (invoice field) → ToDo
"""

import frappe


def on_submit(doc, method=None):
    """Close 'Create Payment Entry' ToDos when a PE is submitted for a matching milestone."""
    _toggle_payment_entry_todos(doc, action="close")


def on_cancel(doc, method=None):
    """Reopen 'Create Payment Entry' ToDos when a PE is cancelled."""
    _toggle_payment_entry_todos(doc, action="reopen")


def _toggle_payment_entry_todos(pe_doc, action="close"):
    """
    Resolve the Sales Order from the PE references, then close or reopen
    all 'Create Payment Entry' ToDos for that SO.

    Handles two reference types:
    - reference_doctype == 'Sales Order'  → use directly
    - reference_doctype == 'Sales Invoice' → resolve SO from SI items
    """
    so_names = set()

    for ref in pe_doc.get("references") or []:
        ref_type = ref.reference_doctype
        ref_name = ref.reference_name
        if not ref_name:
            continue

        if ref_type == "Sales Order":
            so_names.add(ref_name)

        elif ref_type == "Sales Invoice":
            # Resolve SO from SI item rows
            so_from_si = frappe.db.get_value(
                "Sales Invoice Item",
                {"parent": ref_name, "sales_order": ["!=", ""]},
                "sales_order",
            )
            if so_from_si:
                so_names.add(so_from_si)
            else:
                # Fallback: custom_sales_order field on SI header
                so_from_header = frappe.db.get_value(
                    "Sales Invoice", ref_name, "custom_sales_order"
                )
                if so_from_header:
                    so_names.add(so_from_header)

    for so_name in so_names:
        if action == "close":
            _close_pe_todos_for_so(so_name)
        elif action == "reopen":
            _reopen_pe_todos_for_so(so_name)


def _close_pe_todos_for_so(sales_order_name):
    """Close all Open 'Create Payment Entry' ToDos for a Sales Order."""
    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Sales Order",
            "reference_name": sales_order_name,
            "role": "Accounts Manager",
            "status": "Open",
            "description": ["like", f"Create Payment Entry for%| {sales_order_name}"],
        },
        fields=["name"],
    )
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} 'Create Payment Entry' ToDo(s) for {sales_order_name}"
        )


def _reopen_pe_todos_for_so(sales_order_name):
    """Reopen Closed 'Create Payment Entry' ToDos for a Sales Order."""
    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Sales Order",
            "reference_name": sales_order_name,
            "role": "Accounts Manager",
            "status": "Closed",
            "description": ["like", f"Create Payment Entry for%| {sales_order_name}"],
        },
        fields=["name"],
    )
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Open", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Reopened {len(todos)} 'Create Payment Entry' ToDo(s) for {sales_order_name}"
        )


# Keep old per-milestone helpers for backward compatibility
def _close_pe_todos(sales_order_name, milestone_label):
    _close_pe_todos_for_so(sales_order_name)


def _reopen_pe_todos(sales_order_name, milestone_label):
    _reopen_pe_todos_for_so(sales_order_name)
