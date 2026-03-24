import frappe


def execute():
    fields_to_remove = [
        "custom_advance_invoice",
        "custom_advance_paid",
        "custom_delivery_invoice",
        "custom_delivery_paid",
        "custom_final_invoice",
        "custom_final_paid",
    ]

    for fieldname in fields_to_remove:
        cf_name = frappe.db.get_value(
            "Custom Field", {"dt": "Sales Order", "fieldname": fieldname}
        )
        if cf_name:
            frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True)
            frappe.db.commit()

        # Drop the column from the database table if it still exists
        if frappe.db.has_column("Sales Order", fieldname):
            frappe.db.sql(f"ALTER TABLE `tabSales Order` DROP COLUMN `{fieldname}`")
