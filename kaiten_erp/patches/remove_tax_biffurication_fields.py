import frappe
import json


def execute():
    """Remove the typo'd 'custom_tax_biffurication' table and its section breaks
    from Quotation and Sales Order. The correct field is 'custom_tax_bifurcation'."""

    fields_by_dt = {
        "Quotation": [
            "custom_tax_biffurication",
            "custom_section_break_zjnux",
        ],
        "Sales Order": [
            "custom_tax_biffurication",
            "custom_section_break_rv6r7",
        ],
    }

    for dt, fieldnames in fields_by_dt.items():
        for fieldname in fieldnames:
            cf_name = frappe.db.get_value(
                "Custom Field", {"dt": dt, "fieldname": fieldname}
            )
            if cf_name:
                frappe.delete_doc("Custom Field", cf_name, ignore_permissions=True)

            if frappe.db.has_column(dt, fieldname):
                frappe.db.sql(
                    f"ALTER TABLE `tab{dt}` DROP COLUMN `{fieldname}`"
                )

        # Clean up field_order property setter
        ps_name = frappe.db.get_value(
            "Property Setter",
            {"doc_type": dt, "property": "field_order"},
        )
        if ps_name:
            current = frappe.db.get_value("Property Setter", ps_name, "value") or "[]"
            order = json.loads(current)
            updated = [f for f in order if f not in fieldnames]
            if len(updated) != len(order):
                frappe.db.set_value(
                    "Property Setter", ps_name, "value", json.dumps(updated),
                    update_modified=False,
                )

    frappe.db.commit()
