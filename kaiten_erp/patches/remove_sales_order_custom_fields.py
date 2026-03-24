import frappe


def execute():
    fields_to_remove = [
        "gst_col_break",
        "ecommerce_supply_type",
        "ecommerce_gstin",
        "custom_stock_reserved",
        "custom_reservation_timestamp",
        "custom_linked_material_request",
        "custom_procurement_status",
        "company_gstin",
        "place_of_supply",
        "gst_category",
        "billing_address_gstin",
        "gst_breakup_table",
        "section_gst_breakup",
        "custom_payment_milestones_tab",
        "is_export_with_gst",
        "is_reverse_charge",
        "custom_job_file",
        "custom_technical_survey",
        "gst_section",
        "custom_milestone_column_break_2",
        "custom_milestone_column_break_1",
        "custom_milestone_invoices_section",
    ]

    for fieldname in fields_to_remove:
        cf_name = frappe.db.get_value(
            "Custom Field", {"dt": "Sales Order", "fieldname": fieldname}
        )
        if cf_name:
            frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True)
            frappe.db.commit()

        if frappe.db.has_column("Sales Order", fieldname):
            frappe.db.sql(f"ALTER TABLE `tabSales Order` DROP COLUMN `{fieldname}`")
