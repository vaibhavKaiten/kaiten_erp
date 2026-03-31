# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe

_DOCTYPE = "Job File"
_FIELDNAME = "monthly_consumption"
_PS_NAME = "Job File-monthly_consumption-label"
_NEW_LABEL = " Avg Monthly Consumption (Unit)"


def execute():
    """
    Update the label of Job File > tab_2_tab > monthly_consumption
    from 'Avg Monthly Consumption' to 'Avg Monthly Consumption (Unit)'.

    Works via the existing Property Setter record; falls back to creating
    one if it is somehow absent.  Idempotent.
    """
    if not frappe.db.exists("DocType", _DOCTYPE):
        return

    if frappe.db.exists("Property Setter", _PS_NAME):
        frappe.db.set_value("Property Setter", _PS_NAME, "value", _NEW_LABEL)
    else:
        # Property Setter missing — create it so the label is applied
        ps = frappe.new_doc("Property Setter")
        ps.doctype_or_field = "DocField"
        ps.doc_type = _DOCTYPE
        ps.field_name = _FIELDNAME
        ps.property = "label"
        ps.property_type = "Data"
        ps.value = _NEW_LABEL
        ps.module = "Kaiten Erp"
        ps.insert(ignore_permissions=True)

    frappe.db.commit()
    frappe.clear_cache(doctype=_DOCTYPE)
