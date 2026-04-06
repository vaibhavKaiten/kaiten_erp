# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

# Adds "Job File" link to the CRM Workspace Sidebar so it appears in the
# left sidebar when a user is on /desk/dashboard-view/CRM.

import frappe


def execute():
    if not frappe.db.exists("Workspace Sidebar", "CRM"):
        return

    sidebar = frappe.get_doc("Workspace Sidebar", "CRM")

    # Avoid duplicating the item if the patch runs more than once
    existing_labels = [item.label for item in sidebar.items]
    if "Job File" in existing_labels:
        return

    sidebar.append(
        "items",
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Job File",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Job File",
            "icon": "files",
            "child": 0,
            "collapsible": 1,
            "indent": 0,
            "keep_closed": 0,
            "show_arrow": 0,
        },
    )

    sidebar.save(ignore_permissions=True)
    frappe.db.commit()
