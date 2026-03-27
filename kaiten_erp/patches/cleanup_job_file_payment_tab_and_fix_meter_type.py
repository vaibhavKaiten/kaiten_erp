# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    1. Job File: remove all fields belonging to the "Payment Control"
       tab/section (payment_control_tab and everything under it up to the
       next Tab Break).
    2. Meter Installation: ensure the meter_type field is a Select with
       options "Single Phase\nThree Phase".

    Safe to run multiple times (idempotent).
    """
    _remove_job_file_payment_control_fields()
    _fix_meter_type_options()
    frappe.db.commit()


# ─── helpers ──────────────────────────────────────────────────────────────────

# Field types that only carry layout information and have no database column.
_LAYOUT_FIELDTYPES = {
    "Tab Break",
    "Section Break",
    "Column Break",
    "Fold",
    "Heading",
    "HTML",
    "Button",
    "Image",
    "Markdown Editor",
}


def _remove_job_file_payment_control_fields():
    """
    Identify every DocField row that belongs to the payment_control_tab in
    Job File by walking the ordered field list and collecting fields from
    payment_control_tab up to (but not including) the next Tab Break.
    Deletes those DocField rows and drops any physical DB columns they own.
    Re-indexes remaining fields so no gaps remain.
    """
    doctype = "Job File"

    if not frappe.db.exists("DocType", doctype):
        return

    # Fetch all DocField rows for this doctype, ordered by position.
    all_fields = frappe.db.get_all(
        "DocField",
        filters={"parent": doctype},
        fields=["name", "fieldname", "fieldtype"],
        order_by="idx asc",
    )

    # Walk the ordered list; collect everything from payment_control_tab up
    # to (but not including) the next Tab Break.
    in_payment_tab = False
    to_delete = []

    for field in all_fields:
        if field.fieldname == "payment_control_tab":
            in_payment_tab = True
        elif field.fieldtype == "Tab Break" and in_payment_tab:
            # Reached the next tab — stop collecting.
            in_payment_tab = False

        if in_payment_tab:
            to_delete.append(field)

    if not to_delete:
        # Nothing to do — already clean.
        return

    for field in to_delete:
        # Remove the DocField metadata row.
        frappe.db.delete("DocField", {"name": field.name})

        # Drop the physical column for data-bearing fields only.
        # Must commit before ALTER TABLE to avoid ImplicitCommitError.
        if (
            field.fieldtype not in _LAYOUT_FIELDTYPES
            and frappe.db.has_column(doctype, field.fieldname)
        ):
            frappe.db.commit()
            frappe.db.sql(
                "ALTER TABLE `tab{dt}` DROP COLUMN `{col}`".format(
                    dt=doctype, col=field.fieldname
                )
            )

    # Re-index the surviving fields so idx is contiguous (1-based).
    remaining = frappe.db.get_all(
        "DocField",
        filters={"parent": doctype},
        fields=["name"],
        order_by="idx asc",
    )
    for idx, row in enumerate(remaining, start=1):
        frappe.db.set_value("DocField", row.name, "idx", idx, update_modified=False)

    frappe.clear_cache(doctype=doctype)


def _fix_meter_type_options():
    """
    Ensure the meter_type field on Meter Installation is a Select field
    with exactly the options: "Single Phase\nThree Phase".
    Checks both DocField (app-owned) and Custom Field (admin-added) records.
    """
    doctype = "Meter Installation"
    fieldname = "meter_type"
    expected_fieldtype = "Select"
    expected_options = "Single Phase\nThree Phase"

    if not frappe.db.exists("DocType", doctype):
        return

    # Check for a DocField (owned by this app's doctype definition).
    docfield_name = frappe.db.get_value(
        "DocField",
        {"parent": doctype, "fieldname": fieldname},
        "name",
    )

    if docfield_name:
        current_ft, current_opts = frappe.db.get_value(
            "DocField", docfield_name, ["fieldtype", "options"]
        )
        if current_ft != expected_fieldtype or current_opts != expected_options:
            frappe.db.set_value(
                "DocField",
                docfield_name,
                {"fieldtype": expected_fieldtype, "options": expected_options},
            )
        frappe.clear_cache(doctype=doctype)
        return

    # Check for a Custom Field (created via Customize Form / Custom Field doctype).
    custom_field_name = frappe.db.get_value(
        "Custom Field",
        {"dt": doctype, "fieldname": fieldname},
        "name",
    )

    if custom_field_name:
        current_ft, current_opts = frappe.db.get_value(
            "Custom Field", custom_field_name, ["fieldtype", "options"]
        )
        if current_ft != expected_fieldtype or current_opts != expected_options:
            frappe.db.set_value(
                "Custom Field",
                custom_field_name,
                {"fieldtype": expected_fieldtype, "options": expected_options},
            )
        frappe.clear_cache(doctype=doctype)
