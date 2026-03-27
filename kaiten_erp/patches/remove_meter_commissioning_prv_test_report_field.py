# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    Remove the prv__test_report field from Meter Commissioning DocType.
    Also removes the companion column_break_qbog layout field that preceded it.
    Safe to run multiple times (idempotent).
    """
    doctype = "Meter Commissioning"

    if not frappe.db.exists("DocType", doctype):
        return

    fields_to_remove = ["prv__test_report", "column_break_qbog"]

    for fieldname in fields_to_remove:
        docfield_name = frappe.db.get_value(
            "DocField",
            {"parent": doctype, "fieldname": fieldname},
            "name",
        )
        if docfield_name:
            frappe.db.delete("DocField", {"name": docfield_name})

        # Drop physical DB column for data-bearing fields (Attach stores a path string).
        # Must commit before ALTER TABLE to avoid ImplicitCommitError.
        if fieldname not in ("column_break_qbog",) and frappe.db.has_column(
            doctype, fieldname
        ):
            frappe.db.commit()
            frappe.db.sql(
                "ALTER TABLE `tabMeter Commissioning` DROP COLUMN `{col}`".format(
                    col=fieldname
                )
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
