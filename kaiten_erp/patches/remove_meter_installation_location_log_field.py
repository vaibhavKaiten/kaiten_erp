# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    Remove the location_log Table field from Meter Installation DocType.
    Meter Installation uses custom_location_activity_log instead.
    Table fields have no column in the parent table, so no ALTER TABLE is needed.
    Orphaned child rows (parentfield="location_log", parenttype="Meter Installation")
    are also cleaned up.
    Safe to run multiple times (idempotent).
    """
    doctype = "Meter Installation"

    if not frappe.db.exists("DocType", doctype):
        return

    fieldname = "location_log"

    docfield_name = frappe.db.get_value(
        "DocField",
        {"parent": doctype, "fieldname": fieldname},
        "name",
    )
    if docfield_name:
        frappe.db.delete("DocField", {"name": docfield_name})

    # Remove any orphaned child rows stored under this parentfield.
    frappe.db.delete(
        "Location Log",
        {"parenttype": doctype, "parentfield": fieldname},
    )

    # Re-index surviving fields so idx is contiguous.
    remaining = frappe.db.get_all(
        "DocField",
        filters={"parent": doctype},
        fields=["name"],
        order_by="idx asc",
    )
    for idx, row in enumerate(remaining, start=1):
        frappe.db.set_value("DocField", row.name, "idx", idx, update_modified=False)

    frappe.db.commit()
    frappe.clear_cache(doctype=doctype)
