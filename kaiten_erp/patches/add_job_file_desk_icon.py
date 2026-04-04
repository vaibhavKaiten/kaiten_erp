# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

# NOTE: "Job File" is an existing DocType — a Workspace named "Job File" would hijack
# the /desk/job-file route and break the list view. This patch creates only a
# Workspace Sidebar + Desktop Icon (no Workspace doc), using "Jobs" as the label.

import frappe


def execute():
    # --- Guard: delete any conflicting Workspace named "Jobs" or "Job File" ---
    for ws_name in ["Jobs", "Job File"]:
        if frappe.db.exists("Workspace", ws_name):
            frappe.delete_doc("Workspace", ws_name, ignore_permissions=True, force=True)

    # --- Workspace Sidebar "Jobs" ---
    if frappe.db.exists("Workspace Sidebar", "Jobs"):
        sidebar = frappe.get_doc("Workspace Sidebar", "Jobs")
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
                "title": "Jobs",
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

    # --- Desktop Icon "Jobs" ---
    existing = frappe.get_all(
        "Desktop Icon",
        filters={"label": "Jobs", "standard": 0},
        limit=1,
    )
    if existing:
        icon = frappe.get_doc("Desktop Icon", existing[0].name)
        icon.icon_type = "Link"
        icon.link_type = "Workspace Sidebar"
        icon.link_to = "Jobs"
        icon.icon = "files"
        icon.app = "kaiten_erp"
        icon.hidden = 0
        icon.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Desktop Icon",
                "label": "Jobs",
                "icon_type": "Link",
                "link_type": "Workspace Sidebar",
                "link_to": "Jobs",
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


def execute():
    # --- Guard: delete any conflicting Workspace named "Jobs" or "Job File" ---
    for ws_name in ["Jobs", "Job File"]:
        if frappe.db.exists("Workspace", ws_name):
            frappe.delete_doc("Workspace", ws_name, ignore_permissions=True, force=True)

    # --- Workspace Sidebar "Jobs" ---
    if frappe.db.exists("Workspace Sidebar", "Jobs"):
        sidebar = frappe.get_doc("Workspace Sidebar", "Jobs")
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
                "title": "Jobs",
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

    # --- Desktop Icon "Jobs" ---
    existing = frappe.get_all(
        "Desktop Icon",
        filters={"label": "Jobs", "standard": 0},
        limit=1,
    )
    if existing:
        icon = frappe.get_doc("Desktop Icon", existing[0].name)
        icon.icon_type = "Link"
        icon.link_type = "Workspace Sidebar"
        icon.link_to = "Jobs"
        icon.icon = "files"
        icon.app = "kaiten_erp"
        icon.hidden = 0
        icon.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Desktop Icon",
                "label": "Jobs",
                "icon_type": "Link",
                "link_type": "Workspace Sidebar",
                "link_to": "Jobs",
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
