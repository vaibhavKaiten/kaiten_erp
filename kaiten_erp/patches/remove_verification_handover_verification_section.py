# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    Remove the "Verification" section (installation_notes_section) and its
    fields from the Verification Handover DocType:
      - installation_notes_section  (Section Break)
      - verification_reference_no   (Data)
      - verification_notes          (Small Text)
      - execution_remarks           (Small Text)
      - column_break_axcy           (Column Break)
      - column_break_oifu           (Column Break)

    Safe to run multiple times (idempotent).
    """
    doctype = "Verification Handover"

    if not frappe.db.exists("DocType", doctype):
        return

    layout_fields = {
        "installation_notes_section",
        "column_break_axcy",
        "column_break_oifu",
    }
    data_fields = {
        "verification_reference_no",
        "verification_notes",
        "execution_remarks",
    }
    all_fields = layout_fields | data_fields

    for fieldname in all_fields:
        docfield_name = frappe.db.get_value(
            "DocField",
            {"parent": doctype, "fieldname": fieldname},
            "name",
        )
        if docfield_name:
            frappe.db.delete("DocField", {"name": docfield_name})

        # Drop physical DB column for data-bearing fields only.
        # Must commit before ALTER TABLE — DDL causes an implicit commit in
        # MySQL and Frappe raises ImplicitCommitError if a transaction is open.
        if fieldname in data_fields and frappe.db.has_column(doctype, fieldname):
            frappe.db.commit()
            frappe.db.sql(
                "ALTER TABLE `tabVerification Handover` DROP COLUMN `{col}`".format(
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
