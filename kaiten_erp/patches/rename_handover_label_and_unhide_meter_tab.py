# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    1. Rename the Verification Handover > customer_handover_form label
       from "Customer Handover Form" to "DCR Certificate".
    2. Unhide the Meter Installation > meter_installation_details_tab.

    Both changes are applied via Property Setter records.  Idempotent.
    """

    # ── 1. Rename customer_handover_form label ────────────────────────────
    vh_doctype = "Verification Handover"
    vh_field = "customer_handover_form"
    vh_ps_name = f"{vh_doctype}-{vh_field}-label"
    new_label = "DCR Certificate"

    if frappe.db.exists("DocType", vh_doctype):
        if frappe.db.exists("Property Setter", vh_ps_name):
            frappe.db.set_value("Property Setter", vh_ps_name, "value", new_label)
        else:
            ps = frappe.new_doc("Property Setter")
            ps.doctype_or_field = "DocField"
            ps.doc_type = vh_doctype
            ps.field_name = vh_field
            ps.property = "label"
            ps.property_type = "Data"
            ps.value = new_label
            ps.module = "Kaiten Erp"
            ps.insert(ignore_permissions=True)

    # ── 2. Unhide Meter Installation Details tab ──────────────────────────
    mi_doctype = "Meter Installation"
    mi_field = "meter_installation_details_tab"
    mi_ps_name = f"{mi_doctype}-{mi_field}-hidden"

    if frappe.db.exists("DocType", mi_doctype):
        if frappe.db.exists("Property Setter", mi_ps_name):
            frappe.db.set_value("Property Setter", mi_ps_name, "value", "0")
        else:
            ps = frappe.new_doc("Property Setter")
            ps.doctype_or_field = "DocField"
            ps.doc_type = mi_doctype
            ps.field_name = mi_field
            ps.property = "hidden"
            ps.property_type = "Check"
            ps.value = "0"
            ps.module = "Kaiten Erp"
            ps.insert(ignore_permissions=True)

    frappe.db.commit()
    frappe.clear_cache(doctype=vh_doctype)
    frappe.clear_cache(doctype=mi_doctype)
