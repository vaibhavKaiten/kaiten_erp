# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    # --- Delete conflicting ToDo workspace if it exists ---
    if frappe.db.exists("Workspace", "ToDo"):
        frappe.delete_doc("Workspace", "ToDo", ignore_permissions=True, force=True)

    # --- Create Workspace Sidebar ---
    if not frappe.db.exists("Workspace Sidebar", "ToDo"):
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

    # --- Create Desktop Icon ---
    if not frappe.db.exists("Desktop Icon", {"label": "ToDo", "standard": 0}):
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
