import frappe


def execute():
    doctype = "DISCOM Process Tracker"
    fieldname = "feasibility_status"
    options = "Ok\nNot Ok"

    frappe.db.set_value(
        "DocField",
        {"parent": doctype, "fieldname": fieldname},
        {"fieldtype": "Select", "options": options},
    )

    # If a Property Setter overrides DocField options, align it too.
    if frappe.db.exists(
        "Property Setter",
        {
            "doc_type": doctype,
            "field_name": fieldname,
            "property": "options",
        },
    ):
        frappe.db.set_value(
            "Property Setter",
            {
                "doc_type": doctype,
                "field_name": fieldname,
                "property": "options",
            },
            "value",
            options,
        )

    if frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, fieldname):
        # Migrate old values to new options
        frappe.db.sql(
            """
            UPDATE `tabDISCOM Process Tracker`
            SET `feasibility_status` = 'Ok'
            WHERE `feasibility_status` IN ('Pending', 'Approved', ' ', '')
            """
        )
        frappe.db.sql(
            """
            UPDATE `tabDISCOM Process Tracker`
            SET `feasibility_status` = 'Not Ok'
            WHERE `feasibility_status` = 'Rejected'
            """
        )

    frappe.db.commit()
    frappe.clear_cache(doctype=doctype)
