import frappe


def execute():
    """
    Migrate Delivery Note: replace custom_linked_sales_order with against_sales_order.

    1. Copy data from custom_linked_sales_order → against_sales_order (where not already set)
    2. Remove the custom_linked_sales_order Custom Field
    3. Drop the old column from the database
    """
    dn_table = "tabDelivery Note"

    # Step 1: Ensure against_sales_order column exists on DN parent
    if not frappe.db.has_column("Delivery Note", "against_sales_order"):
        frappe.log_error(
            "against_sales_order column does not exist on Delivery Note. "
            "Please create the Custom Field first before running this patch."
        )
        return

    # Step 2: Migrate data from old field to new field
    if frappe.db.has_column("Delivery Note", "custom_linked_sales_order"):
        frappe.db.sql(f"""
            UPDATE `{dn_table}`
            SET `against_sales_order` = `custom_linked_sales_order`
            WHERE (`against_sales_order` IS NULL OR `against_sales_order` = '')
              AND `custom_linked_sales_order` IS NOT NULL
              AND `custom_linked_sales_order` != ''
        """)
        frappe.db.commit()

    # Step 3: Remove the Custom Field record
    cf_name = frappe.db.get_value(
        "Custom Field",
        {"dt": "Delivery Note", "fieldname": "custom_linked_sales_order"},
    )
    if cf_name:
        frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True)
        frappe.db.commit()

    # Step 4: Drop the old column
    if frappe.db.has_column("Delivery Note", "custom_linked_sales_order"):
        frappe.db.sql(
            f"ALTER TABLE `{dn_table}` DROP COLUMN `custom_linked_sales_order`"
        )
        frappe.db.commit()
