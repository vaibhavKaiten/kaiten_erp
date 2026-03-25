import frappe


def execute():
    # Only remove fields that belong to kaiten_erp and are no longer used.
    # Do NOT include india_compliance GST fields (gst_category, place_of_supply,
    # billing_address_gstin, company_gstin, gst_section, gst_col_break,
    # ecommerce_gstin, ecommerce_supply_type, is_reverse_charge, is_export_with_gst)
    # — those are owned by india_compliance and must remain on Sales Order.
    # Do NOT include custom_technical_survey or custom_job_file — they are actively
    # used by delivery_note_events, sales_order_events, JobFile_events, etc.
    fields_to_remove = [
        "custom_stock_reserved",
        "custom_reservation_timestamp",
        "custom_linked_material_request",
        "custom_procurement_status",
        "custom_payment_milestones_tab",
        "custom_milestone_column_break_2",
        "custom_milestone_column_break_1",
        "custom_milestone_invoices_section",
        "section_gst_breakup",
        "gst_breakup_table",
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
