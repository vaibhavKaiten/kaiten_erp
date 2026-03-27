# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    Replace the "Customer Handover Form" field (customer_handover_form) with
    a new "DCR Certificate" field (dcr_certificate, type Attach) in the
    Verification Handover DocType's Final Documents section.

    Steps:
      1. Add dcr_certificate DocField immediately after customer_handover_form
         (taking its idx slot) if it does not already exist.
      2. Remove the customer_handover_form DocField row.
      3. Drop the customer_handover_form DB column if it still exists.
      4. Re-index all fields.

    Safe to run multiple times (idempotent).
    """
    doctype = "Verification Handover"

    if not frappe.db.exists("DocType", doctype):
        return

    # ── 1. Add dcr_certificate if not already present ─────────────────────
    existing_dcr = frappe.db.get_value(
        "DocField", {"parent": doctype, "fieldname": "dcr_certificate"}, "name"
    )

    if not existing_dcr:
        # Find the idx of the field it replaces so the new field sits in the
        # same position within the section.
        old_idx = frappe.db.get_value(
            "DocField",
            {"parent": doctype, "fieldname": "customer_handover_form"},
            "idx",
        ) or 0

        doc = frappe.get_doc("DocType", doctype)
        doc.append(
            "fields",
            {
                "fieldname": "dcr_certificate",
                "fieldtype": "Attach",
                "label": "DCR Certificate",
                "idx": old_idx,  # will be normalised by re-index below
            },
        )
        # Save only the fields child table without triggering full doctype save hooks.
        frappe.db.set_value(
            "DocType", doctype, "modified", frappe.utils.now(), update_modified=False
        )
        # Insert the new DocField row directly.
        new_field = doc.fields[-1]
        new_field.insert()

    # ── 2. Remove customer_handover_form DocField row ──────────────────────
    old_field_name = frappe.db.get_value(
        "DocField", {"parent": doctype, "fieldname": "customer_handover_form"}, "name"
    )
    if old_field_name:
        frappe.db.delete("DocField", {"name": old_field_name})

    # ── 3. Drop the old DB column ──────────────────────────────────────────
    if frappe.db.has_column(doctype, "customer_handover_form"):
        frappe.db.commit()  # flush open transaction before DDL
        frappe.db.sql(
            "ALTER TABLE `tabVerification Handover` DROP COLUMN `customer_handover_form`"
        )

    # ── 4. Re-index surviving fields ───────────────────────────────────────
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
