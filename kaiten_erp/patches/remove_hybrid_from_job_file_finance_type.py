import frappe


def execute():
    """
    Remove the 'Hybrid' option from custom_finance_type on Job File,
    leaving only 'Self Funding' and 'Bank Loan'.
    """
    cf_name = "Job File-custom_finance_type"

    if not frappe.db.exists("Custom Field", cf_name):
        return

    frappe.db.set_value(
        "Custom Field",
        cf_name,
        "options",
        "Self Funding\nBank Loan",
    )

    # Reset any existing records that still carry 'Hybrid' to an empty string
    frappe.db.sql(
        """
        UPDATE `tabJob File`
        SET custom_finance_type = ''
        WHERE custom_finance_type = 'Hybrid'
        """
    )

    frappe.db.commit()
    frappe.clear_cache(doctype="Job File")
