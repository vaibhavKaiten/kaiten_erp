# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Material Request event handlers.
Sets the document title to '{customer_name} - {k_number} - Material Request'
on insert. Title is a display-only string; the document ID (MAT-MR-...) is unchanged.
"""

import frappe


def before_insert(doc, method=None):
    _set_title(doc)


def _set_title(doc):
    customer_name = _get_customer_name(doc)
    k_number = _get_k_number(doc)

    parts = [p for p in [customer_name, k_number, "Material Request"] if p]
    # Only override when we have at least customer or k_number to add context
    if len(parts) > 1:
        doc.title = " - ".join(parts)


def _get_customer_name(doc):
    customer_id = (
        doc.get("custom_source_customer")
        or doc.get("customer")
    )
    # Fallback: fetch customer from the linked Sales Order
    if not customer_id and doc.get("custom_source_sales_order"):
        customer_id = frappe.db.get_value(
            "Sales Order", doc.get("custom_source_sales_order"), "customer"
        )
    if not customer_id:
        return ""
    return frappe.db.get_value("Customer", customer_id, "customer_name") or customer_id


def _get_k_number(doc):
    so_name = doc.get("custom_source_sales_order")
    if not so_name:
        return ""
    job_file = frappe.db.get_value("Sales Order", so_name, "custom_job_file")
    if not job_file:
        return ""
    return frappe.db.get_value("Job File", job_file, "k_number") or ""
