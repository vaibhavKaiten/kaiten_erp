import frappe


def execute():
    """
    Change the custom_finance_type field on Sales Order from Select to Link,
    pointing to Payment Milestone Template.
    """
    doctype = "Sales Order"
    fieldname = "custom_finance_type"
    cf_name = f"{doctype}-{fieldname}"

    if frappe.db.exists("Custom Field", cf_name):
        frappe.db.set_value(
            "Custom Field",
            cf_name,
            {
                "fieldtype": "Link",
                "options": "Payment Milestone Template",
                "translatable": 0,
            },
        )
    else:
        # Field doesn't exist yet — create it
        cf = frappe.get_doc(
            {
                "doctype": "Custom Field",
                "dt": doctype,
                "fieldname": fieldname,
                "fieldtype": "Link",
                "label": "Finance Type",
                "options": "Payment Milestone Template",
                "insert_after": "custom_payment_milestone",
                "module": "Kaiten Erp",
            }
        )
        cf.insert(ignore_permissions=True)

    frappe.db.commit()

    # Reload the doctype metadata so the change takes effect in the current process
    frappe.clear_cache(doctype=doctype)
