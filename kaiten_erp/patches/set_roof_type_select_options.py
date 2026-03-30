import frappe


def execute():
    doctype = "Technical Survey"
    fieldname = "roof_type"
    options = "RCC\nTin Shed\nAsbestos\nMixed\nOther"

    # Update the DocField meta record
    frappe.db.set_value(
        "DocField",
        {"parent": doctype, "fieldname": fieldname},
        {
            "fieldtype": "Select",
            "options": options,
        },
    )

    frappe.db.commit()

    # Ensure the DB column can hold the select value (varchar 140)
    frappe.db.sql(
        "ALTER TABLE `tabTechnical Survey` MODIFY `roof_type` varchar(140) DEFAULT NULL"
    )
