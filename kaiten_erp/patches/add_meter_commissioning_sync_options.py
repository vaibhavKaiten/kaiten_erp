import frappe


def execute():
    """
    Add 'Yes' and 'No' options to inverter_sync_status and grid_sync_status
    Select fields on the Meter Commissioning doctype.
    """
    options = "Yes\nNo"

    for fieldname in ("inverter_sync_status", "grid_sync_status"):
        frappe.db.set_value(
            "DocField",
            {"fieldname": fieldname, "parent": "Meter Commissioning"},
            "options",
            options,
        )

    frappe.db.commit()
    frappe.clear_cache(doctype="Meter Commissioning")
