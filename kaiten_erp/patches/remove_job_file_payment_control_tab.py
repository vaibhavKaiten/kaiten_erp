import frappe


_LAYOUT_FIELDTYPES = {
    "Tab Break",
    "Section Break",
    "Column Break",
    "Fold",
    "Heading",
    "HTML",
    "Button",
    "Image",
}

# All fieldnames that belonged to the Payment Control tab
_PAYMENT_CONTROL_FIELDS = [
    "payment_control_tab",
    "payment_control_section",
    "advance_invoice_number",
    "advance_invoice_amount",
    "advance_paid_amount",
    "advance_outstanding_amount",
    "advance_invoice_status",
    "column_break_pc1",
    "advance_override_approved",
    "advance_override_remark",
    "column_break_pc2",
    "advance_override_approved_by",
    "advance_override_approved_on",
    "override_notification_sent",
]


def execute():
    """
    Remove the 'Payment Control' tab and all fields under it from the
    Job File doctype — both DocField rows and physical DB columns.
    Safe to run multiple times (idempotent).
    """
    doctype = "Job File"

    if not frappe.db.exists("DocType", doctype):
        return

    # 1. Delete DocField metadata rows
    for fieldname in _PAYMENT_CONTROL_FIELDS:
        if frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname}):
            frappe.db.delete("DocField", {"parent": doctype, "fieldname": fieldname})

    frappe.db.commit()

    # 2. Drop physical DB columns for data-bearing fields
    for fieldname in _PAYMENT_CONTROL_FIELDS:
        if frappe.db.has_column(doctype, fieldname):
            frappe.db.sql(
                "ALTER TABLE `tab{dt}` DROP COLUMN `{col}`".format(
                    dt=doctype, col=fieldname
                )
            )

    # 3. Re-index surviving fields so idx is contiguous
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
