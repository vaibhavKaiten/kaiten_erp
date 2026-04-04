# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    _setup_technical_workspace()
    _setup_meter_workspace()

    # Reset saved Desktop Layouts so all users pick up the new icons
    for layout in frappe.get_all("Desktop Layout"):
        frappe.delete_doc("Desktop Layout", layout.name, ignore_permissions=True)

    frappe.db.commit()


def _setup_technical_workspace():
    # --- Workspace Sidebar ---
    if frappe.db.exists("Workspace Sidebar", "Technical Workspace"):
        sidebar = frappe.get_doc("Workspace Sidebar", "Technical Workspace")
        sidebar.header_icon = "tool"
        sidebar.app = "kaiten_erp"
        sidebar.module = "Kaiten Erp"
        sidebar.items = []
        for item in _technical_sidebar_items():
            sidebar.append("items", item)
        sidebar.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar",
                "title": "Technical Workspace",
                "header_icon": "tool",
                "standard": 0,
                "app": "kaiten_erp",
                "module": "Kaiten Erp",
                "items": _technical_sidebar_items(),
            }
        ).insert(ignore_permissions=True)

    # --- Desktop Icon ---
    existing = frappe.get_all(
        "Desktop Icon",
        filters={"label": "Technical Workspace", "standard": 0},
        limit=1,
    )
    if existing:
        icon = frappe.get_doc("Desktop Icon", existing[0].name)
        icon.icon_type = "Link"
        icon.link_type = "Workspace Sidebar"
        icon.link_to = "Technical Workspace"
        icon.icon = "tool"
        icon.app = "kaiten_erp"
        icon.hidden = 0
        icon.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Desktop Icon",
                "label": "Technical Workspace",
                "icon_type": "Link",
                "link_type": "Workspace Sidebar",
                "link_to": "Technical Workspace",
                "parent_icon": "",
                "standard": 0,
                "app": "kaiten_erp",
                "icon": "tool",
                "idx": 51,
                "hidden": 0,
                "bg_color": "blue",
                "roles": [
                    {"doctype": "Has Role", "role": "Vendor Manager"},
                    {"doctype": "Has Role", "role": "Vendor Head"},
                ],
            }
        ).insert(ignore_permissions=True)


def _setup_meter_workspace():
    # --- Workspace Sidebar ---
    if frappe.db.exists("Workspace Sidebar", "Meter Workspace"):
        sidebar = frappe.get_doc("Workspace Sidebar", "Meter Workspace")
        sidebar.header_icon = "dashboard"
        sidebar.app = "kaiten_erp"
        sidebar.module = "Kaiten Erp"
        sidebar.items = []
        for item in _meter_sidebar_items():
            sidebar.append("items", item)
        sidebar.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar",
                "title": "Meter Workspace",
                "header_icon": "dashboard",
                "standard": 0,
                "app": "kaiten_erp",
                "module": "Kaiten Erp",
                "items": _meter_sidebar_items(),
            }
        ).insert(ignore_permissions=True)

    # --- Desktop Icon ---
    existing = frappe.get_all(
        "Desktop Icon",
        filters={"label": "Meter Workspace", "standard": 0},
        limit=1,
    )
    if existing:
        icon = frappe.get_doc("Desktop Icon", existing[0].name)
        icon.icon_type = "Link"
        icon.link_type = "Workspace Sidebar"
        icon.link_to = "Meter Workspace"
        icon.icon = "dashboard"
        icon.app = "kaiten_erp"
        icon.hidden = 0
        icon.save(ignore_permissions=True)
    else:
        frappe.get_doc(
            {
                "doctype": "Desktop Icon",
                "label": "Meter Workspace",
                "icon_type": "Link",
                "link_type": "Workspace Sidebar",
                "link_to": "Meter Workspace",
                "parent_icon": "",
                "standard": 0,
                "app": "kaiten_erp",
                "icon": "dashboard",
                "idx": 52,
                "hidden": 0,
                "bg_color": "blue",
                "roles": [
                    {"doctype": "Has Role", "role": "Vendor Manager"},
                    {"doctype": "Has Role", "role": "Vendor Head"},
                ],
            }
        ).insert(ignore_permissions=True)


def _technical_sidebar_items():
    return [
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Technical Survey",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Technical Survey",
            "icon": "file",
        },
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Structure Mounting",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Structure Mounting",
            "icon": "file",
        },
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Project Installation",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Project Installation",
            "icon": "file",
        },
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Verification Handover",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Verification Handover",
            "icon": "file",
        },
    ]


def _meter_sidebar_items():
    return [
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Meter Installation",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Meter Installation",
            "icon": "file",
        },
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Meter Commissioning",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "Meter Commissioning",
            "icon": "file",
        },
    ]
