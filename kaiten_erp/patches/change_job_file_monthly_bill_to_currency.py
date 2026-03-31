# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe

_DOCTYPE = "Job File"
_FIELDNAME = "custom_monthly_bill"
_CF_NAME = "Job File-custom_monthly_bill"


def execute():
    """
    Change the fieldtype of Job File > tab_2_tab > custom_monthly_bill
    from Data to Currency.

    Steps:
      1. Update the Custom Field metadata record.
      2. ALTER the physical DB column from varchar to decimal.
      3. Clear cache so the new fieldtype takes effect immediately.

    Idempotent — safe to run multiple times.
    """
    if not frappe.db.exists("DocType", _DOCTYPE):
        return

    if not frappe.db.exists("Custom Field", _CF_NAME):
        return

    # 1. Update Custom Field metadata
    frappe.db.set_value("Custom Field", _CF_NAME, "fieldtype", "Currency")
    frappe.db.commit()

    # 2. Alter DB column to decimal(21,9) — Frappe's standard for Currency
    if frappe.db.has_column(_DOCTYPE, _FIELDNAME):
        frappe.db.sql(
            "ALTER TABLE `tab{dt}` MODIFY COLUMN `{col}` decimal(21,9) DEFAULT NULL".format(
                dt=_DOCTYPE, col=_FIELDNAME
            )
        )

    frappe.db.commit()
    frappe.clear_cache(doctype=_DOCTYPE)
