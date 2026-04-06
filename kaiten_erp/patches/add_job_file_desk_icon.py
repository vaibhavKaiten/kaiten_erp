# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

# NOTE: "Job File" is an existing DocType — a Workspace named "Job File" would hijack
# the /desk/job-file route and break the list view. We use "Job Workspace" as the label
# (no route conflict). This patch creates Desktop Icon + Workspace Sidebar + Workspace JSON.

import frappe


def execute():
    # --- Cleanup old "Jobs" entries from previous version of this patch ---
    if frappe.db.exists("Workspace Sidebar", "Jobs"):
        frappe.delete_doc("Workspace Sidebar", "Jobs", ignore_permissions=True, force=True)
    for old_icon in frappe.get_all("Desktop Icon", filters={"label": "Jobs", "standard": 0}):
        frappe.delete_doc("Desktop Icon", old_icon.name, ignore_permissions=True, force=True)

    # --- Guard: delete any Workspace named "Job File" (would hijack /desk/job-file route) ---
    if frappe.db.exists("Workspace", "Job File"):
        frappe.delete_doc("Workspace", "Job File", ignore_permissions=True, force=True)

    # --- Workspace Sidebar "Job Workspace" ---
    if frappe.db.exists("Workspace Sidebar", "Job Workspace"):
        sidebar = frappe.get_doc("Workspace Sidebar", "Job Workspace")
        sidebar.header_icon = "files"
        sidebar.app = "kaiten_erp"
        sidebar.module = "Kaiten Erp"
        sidebar.items = []
        sidebar.append(
            "items",
            {
                "label": "Job File",
                "type": "Link",
                "link_type": "DocType",
                "link_to": "Job File",
                "icon": "files",
            },
        )
        sidebar.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar",
                "title": "Job Workspace",
                "header_icon": "files",
                "standard": 0,
                "app": "kaiten_erp",
                "module": "Kaiten Erp",
                "items": [
                    {
                        "doctype": "Workspace Sidebar Item",
                        "label": "Job File",
                        "type": "Link",
                        "link_type": "DocType",
                        "link_to": "Job File",
                        "icon": "files",
                    }
                ],
            }
        ).insert(ignore_permissions=True)

    # --- Desktop Icon "Job Workspace" ---
    existing = frappe.get_all(
        "Desktop Icon",
        filters={"label": "Job Workspace", "standard": 0},
        limit=1,
    )
    if existing:
        icon = frappe.get_doc("Desktop Icon", existing[0].name)
        icon.icon_type = "Link"
        icon.link_type = "Workspace Sidebar"
        icon.link_to = "Job Workspace"
        icon.icon = "files"
        icon.app = "kaiten_erp"
        icon.hidden = 0
        icon.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Desktop Icon",
                "label": "Job Workspace",
                "icon_type": "Link",
                "link_type": "Workspace Sidebar",
                "link_to": "Job Workspace",
                "parent_icon": "",
                "standard": 0,
                "app": "kaiten_erp",
                "icon": "files",
                "idx": 53,
                "hidden": 0,
                "bg_color": "blue",
                "roles": [
                    {"doctype": "Has Role", "role": "System Manager"},
                    {"doctype": "Has Role", "role": "Execution Manager"},
                    {"doctype": "Has Role", "role": "Accounts Manager"},
                    {"doctype": "Has Role", "role": "Sales Executive"},
                ],
            }
        ).insert(ignore_permissions=True)

    # --- Reset saved Desktop Layouts so all users see the updated grid ---
    for layout in frappe.get_all("Desktop Layout"):
        frappe.delete_doc("Desktop Layout", layout.name, ignore_permissions=True)

    frappe.db.commit()
