# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    # --- Delete conflicting ToDo/To Do workspaces if they exist ---
    for ws_name in ["ToDo", "To Do"]:
        if frappe.db.exists("Workspace", ws_name):
            frappe.delete_doc("Workspace", ws_name, ignore_permissions=True, force=True)

    # --- Delete stale "To Do" (with space) Desktop Icon and Workspace Sidebar ---
    if frappe.db.exists("Desktop Icon", "To Do"):
        frappe.delete_doc("Desktop Icon", "To Do", ignore_permissions=True, force=True)
    if frappe.db.exists("Workspace Sidebar", "To Do"):
        frappe.delete_doc("Workspace Sidebar", "To Do", ignore_permissions=True, force=True)

    # --- Create or fix Workspace Sidebar "ToDo" ---
    if frappe.db.exists("Workspace Sidebar", "ToDo"):
        sidebar = frappe.get_doc("Workspace Sidebar", "ToDo")
        sidebar.header_icon = "check"
        sidebar.app = "kaiten_erp"
        sidebar.module = "Kaiten Erp"
        sidebar.items = []
        sidebar.append(
            "items",
            {
                "label": "ToDo",
                "type": "Link",
                "link_type": "DocType",
                "link_to": "ToDo",
                "icon": "check",
            },
        )
        sidebar.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar",
                "title": "ToDo",
                "header_icon": "check",
                "standard": 0,
                "app": "kaiten_erp",
                "module": "Kaiten Erp",
                "items": [
                    {
                        "doctype": "Workspace Sidebar Item",
                        "label": "ToDo",
                        "type": "Link",
                        "link_type": "DocType",
                        "link_to": "ToDo",
                        "icon": "check",
                    }
                ],
            }
        ).insert(ignore_permissions=True)

    # --- Create or fix Desktop Icon "ToDo" ---
    if frappe.db.exists("Desktop Icon", "ToDo"):
        icon = frappe.get_doc("Desktop Icon", "ToDo")
        icon.icon_type = "Link"
        icon.link_type = "Workspace Sidebar"
        icon.link_to = "ToDo"
        icon.icon = "check"
        icon.app = "kaiten_erp"
        icon.hidden = 0
        icon.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Desktop Icon",
                "label": "ToDo",
                "icon_type": "Link",
                "link_type": "Workspace Sidebar",
                "link_to": "ToDo",
                "parent_icon": "",
                "standard": 0,
                "app": "kaiten_erp",
                "icon": "check",
                "idx": 50,
                "hidden": 0,
                "bg_color": "blue",
                "roles": [],
            }
        ).insert(ignore_permissions=True)

    # --- Reset saved Desktop Layouts ---
    for layout in frappe.get_all("Desktop Layout"):
        frappe.delete_doc("Desktop Layout", layout.name, ignore_permissions=True)

    frappe.db.commit()
