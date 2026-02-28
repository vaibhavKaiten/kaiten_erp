# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Custom Fields Setup for Milestone-Based Invoicing
Creates custom fields programmatically for tracking milestone invoices and payment status
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup_milestone_custom_fields():
    """
    Create custom fields for milestone invoice tracking
    Organized in a separate "Payment Milestones" tab in Sales Order for clean UI
    """

    custom_fields = {
        "Sales Order": [
            # Payment Milestones Tab
            {
                "fieldname": "custom_payment_milestones_tab",
                "label": "Payment Milestones",
                "fieldtype": "Tab Break",
                "insert_after": "taxes",
                "collapsible": 0,
            },
            # Milestone Invoices Section
            {
                "fieldname": "custom_milestone_invoices_section",
                "label": "Milestone Invoices",
                "fieldtype": "Section Break",
                "insert_after": "custom_payment_milestones_tab",
            },
            # Advance Invoice
            {
                "fieldname": "custom_advance_invoice",
                "label": "Advance Invoice",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "insert_after": "custom_milestone_invoices_section",
                "read_only": 1,
            },
            {
                "fieldname": "custom_advance_paid",
                "label": "Advance Paid",
                "fieldtype": "Check",
                "insert_after": "custom_advance_invoice",
                "read_only": 1,
                "default": 0,
            },
            # Column Break
            {
                "fieldname": "custom_milestone_column_break_1",
                "fieldtype": "Column Break",
                "insert_after": "custom_advance_paid",
            },
            # Delivery Invoice
            {
                "fieldname": "custom_delivery_invoice",
                "label": "Delivery Invoice",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "insert_after": "custom_milestone_column_break_1",
                "read_only": 1,
            },
            {
                "fieldname": "custom_delivery_paid",
                "label": "Delivery Paid",
                "fieldtype": "Check",
                "insert_after": "custom_delivery_invoice",
                "read_only": 1,
                "default": 0,
            },
            # Column Break
            {
                "fieldname": "custom_milestone_column_break_2",
                "fieldtype": "Column Break",
                "insert_after": "custom_delivery_paid",
            },
            # Final Invoice
            {
                "fieldname": "custom_final_invoice",
                "label": "Final Invoice",
                "fieldtype": "Link",
                "options": "Sales Invoice",
                "insert_after": "custom_milestone_column_break_2",
                "read_only": 1,
            },
            {
                "fieldname": "custom_final_paid",
                "label": "Final Paid",
                "fieldtype": "Check",
                "insert_after": "custom_final_invoice",
                "read_only": 1,
                "default": 0,
            },
        ],
        "Sales Invoice": [
            # Milestone tracking fields
            {
                "fieldname": "custom_milestone_type",
                "label": "Milestone Type",
                "fieldtype": "Select",
                "options": "\nAdvance Payment\nDelivery\nFinal Payment",
                "insert_after": "customer",
                "read_only": 1,
            },
            {
                "fieldname": "custom_sales_order",
                "label": "Linked Sales Order",
                "fieldtype": "Link",
                "options": "Sales Order",
                "insert_after": "custom_milestone_type",
                "read_only": 1,
            },
            {
                "fieldname": "custom_job_file",
                "label": "Job File",
                "fieldtype": "Link",
                "options": "Job File",
                "insert_after": "custom_sales_order",
                "read_only": 1,
            },
            {
                "fieldname": "custom_technical_survey",
                "label": "Technical Survey",
                "fieldtype": "Link",
                "options": "Technical Survey",
                "insert_after": "custom_job_file",
                "read_only": 1,
            },
        ],
        "Delivery Note": [
            {
                "fieldname": "custom_linked_sales_order",
                "label": "Linked Sales Order",
                "fieldtype": "Link",
                "options": "Sales Order",
                "insert_after": "customer",
                "read_only": 1,
            }
        ],
        "Meter Commissioning": [
            {
                "fieldname": "custom_linked_sales_order",
                "label": "Linked Sales Order",
                "fieldtype": "Link",
                "options": "Sales Order",
                "insert_after": "basic_details_tab",
                "read_only": 0,
            }
        ],
    }

    create_custom_fields(custom_fields, update=True)

    frappe.msgprint(
        "Milestone custom fields created successfully", alert=True, indicator="green"
    )


def remove_milestone_custom_fields():
    """
    Remove milestone custom fields (for cleanup/uninstall)
    """
    fields_to_remove = [
        # Sales Order
        ("Sales Order", "custom_payment_milestones_tab"),
        ("Sales Order", "custom_milestone_invoices_section"),
        ("Sales Order", "custom_advance_invoice"),
        ("Sales Order", "custom_advance_paid"),
        ("Sales Order", "custom_milestone_column_break_1"),
        ("Sales Order", "custom_delivery_invoice"),
        ("Sales Order", "custom_delivery_paid"),
        ("Sales Order", "custom_milestone_column_break_2"),
        ("Sales Order", "custom_final_invoice"),
        ("Sales Order", "custom_final_paid"),
        # Sales Invoice
        ("Sales Invoice", "custom_milestone_type"),
        ("Sales Invoice", "custom_sales_order"),
        # Delivery Note
        ("Delivery Note", "custom_linked_sales_order"),
        # Meter Commissioning
        ("Meter Commissioning", "custom_linked_sales_order"),
    ]

    for dt, fieldname in fields_to_remove:
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
            frappe.delete_doc("Custom Field", {"dt": dt, "fieldname": fieldname})

    frappe.msgprint(
        "Milestone custom fields removed successfully", alert=True, indicator="orange"
    )
