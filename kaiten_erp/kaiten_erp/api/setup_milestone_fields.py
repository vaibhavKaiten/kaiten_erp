#!/usr/bin/env python3
"""
Setup script for milestone-based invoicing custom fields
Run this script to create all required custom fields

Usage:
    bench execute kaiten_erp.kaiten_erp.api.setup_milestone_fields.setup
"""

import frappe
from kaiten_erp.kaiten_erp.api.milestone_custom_fields import (
    setup_milestone_custom_fields,
)


def setup():
    """
    Main setup function to create milestone custom fields
    """
    frappe.init(site="dev2.localhost")  # Update with your site name
    frappe.connect()

    print("Setting up milestone custom fields...")
    setup_milestone_custom_fields()

    frappe.db.commit()
    print("Milestone custom fields setup completed successfully!")


if __name__ == "__main__":
    setup()
