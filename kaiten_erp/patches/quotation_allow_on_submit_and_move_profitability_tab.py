# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    1. Make customer_name allow_on_submit in Quotation via Property Setter.
    
    Idempotent — safe to run multiple times.
    """

    # ── 1. Quotation customer_name → allow_on_submit = 1 ─────────────────
    ps_name = "Quotation-customer_name-allow_on_submit"
    if frappe.db.exists("Property Setter", ps_name):
        frappe.db.set_value("Property Setter", ps_name, "value", "1")
    else:
        frappe.get_doc(
            {
                "doctype": "Property Setter",
                "doctype_or_field": "DocField",
                "doc_type": "Quotation",
                "field_name": "customer_name",
                "property": "allow_on_submit",
                "property_type": "Check",
                "value": "1",
            }
        ).insert(ignore_permissions=True)


    frappe.clear_cache(doctype="Quotation")
    
