import frappe


def execute():
    """
    Update select options on Discom Master:
    - Grid Voltage Level: add Single Phase, Three Phase at top
    - Applicable Connection Type: add Single Phase, Three Phase at top; rename Both → Both ( LT & HT )
    - Remove meter_type_required field
    - Make officer_name not mandatory
    """
    doctype = "Discom Master"

    field_updates = {
        "grid_voltage_level": "\nSingle Phase\nThree Phase\nLT (230V / 415V)\nHT\nEHT",
        "applicable_connection_type": "\nSingle Phase\nThree Phase\nLT\nHT\nBoth ( LT & HT )",
    }

    for fieldname, options in field_updates.items():
        frappe.db.set_value(
            "DocField",
            {"parent": doctype, "fieldname": fieldname},
            "options",
            options,
        )

    # Make officer_name not mandatory
    frappe.db.set_value(
        "DocField",
        {"parent": doctype, "fieldname": "officer_name"},
        "reqd",
        0,
    )

    # Migrate existing data only if the table exists
    if frappe.db.table_exists("Discom Master"):
        # Rename existing "Both" values to "Both ( LT & HT )"
        frappe.db.sql(
            """
            UPDATE `tabDiscom Master`
            SET `applicable_connection_type` = 'Both ( LT & HT )'
            WHERE `applicable_connection_type` = 'Both'
            """
        )

        # Drop meter_type_required column if it exists
        if frappe.db.has_column("Discom Master", "meter_type_required"):
            frappe.db.sql(
                "ALTER TABLE `tabDiscom Master` DROP COLUMN `meter_type_required`"
            )

    # Remove the DocField records for meter_type_required and column_break_tech_3
    for fn in ("meter_type_required", "column_break_tech_3"):
        frappe.db.delete(
            "DocField",
            filters={"parent": doctype, "fieldname": fn},
        )

    frappe.db.commit()
    frappe.clear_cache(doctype=doctype)
