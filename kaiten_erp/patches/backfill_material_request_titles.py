"""
Patch: backfill_material_request_titles
Retroactively set the title of all existing Material Requests to the format:
  '{customer_name} - {k_number} - Material Request'

Only Material Requests that have custom_source_sales_order set are updated,
since k_number comes from the Job File linked on the Sales Order.
MRs without a linked Sales Order are skipped (no context to build the title).
"""

import frappe


def execute():
    mrs = frappe.db.sql(
        """
        SELECT
            mr.name,
            mr.custom_source_customer,
            mr.customer,
            mr.custom_source_sales_order
        FROM `tabMaterial Request` mr
        WHERE mr.custom_source_sales_order IS NOT NULL
          AND mr.custom_source_sales_order != ''
        """,
        as_dict=True,
    )

    updated = 0
    for mr in mrs:
        # Resolve customer name
        customer_id = mr.custom_source_customer or mr.customer
        customer_name = ""
        if customer_id:
            customer_name = (
                frappe.db.get_value("Customer", customer_id, "customer_name")
                or customer_id
            )

        # Resolve k_number via Sales Order → Job File
        k_number = ""
        job_file = frappe.db.get_value(
            "Sales Order", mr.custom_source_sales_order, "custom_job_file"
        )
        if job_file:
            k_number = frappe.db.get_value("Job File", job_file, "k_number") or ""

        parts = [p for p in [customer_name, k_number, "Material Request"] if p]
        if len(parts) <= 1:
            continue  # Not enough context; skip

        new_title = " - ".join(parts)
        frappe.db.set_value(
            "Material Request",
            mr.name,
            "title",
            new_title,
            update_modified=False,
        )
        updated += 1

    frappe.db.commit()
    frappe.logger().info(
        f"backfill_material_request_titles: updated {updated} Material Request(s)."
    )
