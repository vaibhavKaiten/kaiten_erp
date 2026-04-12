# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe

_DOCTYPE = "Job File"
_FIELDNAME = "custom_property_photo"
_CF_NAME = "Job File-custom_property_photo"
_NEW_LABEL = "Property Photo with Geo tagging"


def execute():
    """
    Rename the 'Property Photo' custom field label on Job File to
    'Property Photo with Geo tagging'.  Idempotent.
    """
    if not frappe.db.exists("DocType", _DOCTYPE):
        return

    if not frappe.db.exists("Custom Field", _CF_NAME):
        return

    frappe.db.set_value("Custom Field", _CF_NAME, "label", _NEW_LABEL)
    frappe.db.commit()
    frappe.clear_cache(doctype=_DOCTYPE)
