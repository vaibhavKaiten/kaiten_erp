# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt
#
# Patch: fix_location_log_visibility_and_logging
#
# Fixes location log field bugs across execution doctypes:
#
# 1. Structure Mounting:
#    - custom_location_activity_log was missing from field_order in the JSON.
#      Added to JSON; this patch ensures the DB Custom Field record has
#      allow_on_submit=1, read_only=1, hidden=0, and insert_after="location_log".
#
# 2. Meter Installation:
#    - custom_location_activity_log fixture had allow_on_submit=0 and read_only=0,
#      preventing writes on submitted docs. Fixed in fixture and here in DB.
#
# 3. Meter Commissioning:
#    - location_log was in field_order but the custom_location__history Tab Break
#      was not, so location_log appeared outside the tab and was effectively hidden.
#      Fixed in JSON (tab added to field_order before location_log).
#    - Any Property Setter setting hidden=1 on location_log is removed.
#
# 4. Project Installation:
#    - custom_location_activity_log fixture had hidden=1, allow_on_submit=0,
#      read_only=0. gps.py finds custom_location_activity_log first in its
#      candidates list, so data was going into a hidden field.
#      Fixed in fixture and here in DB.

import frappe


def execute():
    _fix_custom_fields()
    _remove_hidden_property_setters()
    frappe.db.commit()


def _fix_custom_fields():
    """
    Ensure all location log Custom Field records have the correct attributes.
    """
    fixes = [
        # (doctype, fieldname, updates_dict)
        (
            "Structure Mounting",
            "custom_location_activity_log",
            {
                "hidden": 0,
                "allow_on_submit": 1,
                "read_only": 1,
                "insert_after": "location_log",
                "options": "Location Log",
            },
        ),
        (
            "Meter Installation",
            "custom_location_activity_log",
            {
                "hidden": 0,
                "allow_on_submit": 1,
                "read_only": 1,
            },
        ),
        (
            "Project Installation",
            "custom_location_activity_log",
            {
                "hidden": 0,
                "allow_on_submit": 1,
                "read_only": 1,
            },
        ),
        (
            "Meter Commissioning",
            "location_log",
            {
                "hidden": 0,
                "allow_on_submit": 1,
                "read_only": 1,
            },
        ),
        (
            "Project Installation",
            "location_log",
            {
                "hidden": 0,
                "allow_on_submit": 1,
                "read_only": 1,
            },
        ),
    ]

    for doctype, fieldname, updates in fixes:
        cf_name = f"{doctype}-{fieldname}"
        if frappe.db.exists("Custom Field", cf_name):
            frappe.db.set_value("Custom Field", cf_name, updates, update_modified=False)
            frappe.logger().info(
                f"[fix_location_log] Updated Custom Field {cf_name}: {updates}"
            )
        else:
            # Field is defined in the doctype JSON (not a custom field) — update
            # via Property Setter if needed, or just log that it's a core field.
            frappe.logger().info(
                f"[fix_location_log] Custom Field {cf_name} not found — "
                f"field is defined in doctype JSON (no DB action needed)."
            )


def _remove_hidden_property_setters():
    """
    Delete any Property Setter that sets hidden=1 on a location log field.
    These may have been created accidentally via the Customize Form UI.
    """
    location_log_fields = {
        "Meter Commissioning": ["location_log", "custom_location__history"],
        "Project Installation": [
            "location_log",
            "custom_location__history",
            "custom_location_activity_log",
        ],
        "Meter Installation": [
            "custom_location__history",
            "custom_location_activity_log",
        ],
        "Structure Mounting": [
            "location_log",
            "custom_location_activity_log",
        ],
    }

    for doctype, fields in location_log_fields.items():
        for fieldname in fields:
            ps_name = f"{doctype}-{fieldname}-hidden"
            if frappe.db.exists("Property Setter", ps_name):
                ps_value = frappe.db.get_value("Property Setter", ps_name, "value")
                if str(ps_value) == "1":
                    frappe.delete_doc(
                        "Property Setter", ps_name, ignore_permissions=True
                    )
                    frappe.logger().info(
                        f"[fix_location_log] Removed hidden=1 Property Setter: {ps_name}"
                    )
