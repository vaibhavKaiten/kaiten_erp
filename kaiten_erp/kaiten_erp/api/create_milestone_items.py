#!/usr/bin/env python3
"""
Create Item masters for milestone payments
These items are used in milestone-based Sales Invoices

Usage:
    bench execute kaiten_erp.kaiten_erp.api.create_milestone_items.create_items
"""

import frappe


def create_items():
    """
    Create Item masters for milestone payment types
    """
    frappe.init(site="dev2.localhost")  # Update with your site name
    frappe.connect()

    items = [
        {
            "item_code": "Advance Payment",
            "item_name": "Advance Payment",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "gst_hsn_code": "998599",
            "description": "Advance payment milestone for sales orders",
        },
        {
            "item_code": "Delivery Payment",
            "item_name": "Delivery Payment",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "gst_hsn_code": "998599",
            "description": "Delivery payment milestone for sales orders",
        },
        {
            "item_code": "Final Payment",
            "item_name": "Final Payment",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "is_sales_item": 1,
            "gst_hsn_code": "998599",
            "description": "Final payment milestone for sales orders",
        },
    ]

    for item_data in items:
        item_code = item_data["item_code"]

        if frappe.db.exists("Item", item_code):
            print(f"Item {item_code} already exists, skipping...")
            continue

        try:
            item = frappe.get_doc({"doctype": "Item", **item_data})
            item.insert(ignore_permissions=True)
            print(f"Created Item: {item_code}")
        except Exception as e:
            print(f"Error creating Item {item_code}: {str(e)}")

    frappe.db.commit()
    print("Milestone items creation completed!")


if __name__ == "__main__":
    create_items()
