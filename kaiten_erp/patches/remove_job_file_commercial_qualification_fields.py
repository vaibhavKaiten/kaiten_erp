import frappe


_FIELDS_TO_REMOVE = [
    "custom_commercial_qualification",  # Tab Break (Custom Field)
    "balance_amount",
    "column_break_wwih",               # Column Break that only separated balance_amount / payment_term_template
    "payment_term_template",
    "finance_required",
]


def execute():
    """
    Remove the 'Commercial Qualification' tab (custom field) and the
    balance_amount, payment_term_template, and finance_required fields
    from the Job File doctype — both DocField / Custom Field metadata
    and physical DB columns.
    Safe to run multiple times (idempotent).
    """
    doctype = "Job File"

    if not frappe.db.exists("DocType", doctype):
        return

    # 1. Delete standard DocField metadata rows
    for fieldname in _FIELDS_TO_REMOVE:
        if frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname}):
            frappe.db.delete("DocField", {"parent": doctype, "fieldname": fieldname})

    # 2. Delete the Custom Field record for custom_commercial_qualification
    custom_field_name = "Job File-custom_commercial_qualification"
    if frappe.db.exists("Custom Field", custom_field_name):
        frappe.delete_doc("Custom Field", custom_field_name, ignore_permissions=True)

    frappe.db.commit()

    # 3. Drop physical DB columns for data-bearing fields
    #    (layout-only fields like Tab Break / Column Break have no column)
    data_fields = [
        "balance_amount",
        "payment_term_template",
        "finance_required",
    ]
    for fieldname in data_fields:
        if frappe.db.has_column(doctype, fieldname):
            frappe.db.sql(
                "ALTER TABLE `tab{dt}` DROP COLUMN `{col}`".format(
                    dt=doctype, col=fieldname
                )
            )

    # 4. Re-index surviving fields so idx is contiguous
    remaining = frappe.db.get_all(
        "DocField",
        filters={"parent": doctype},
        fields=["name"],
        order_by="idx asc",
    )
    for i, row in enumerate(remaining, start=1):
        frappe.db.set_value("DocField", row.name, "idx", i)

    frappe.db.commit()
    frappe.clear_cache(doctype=doctype)
