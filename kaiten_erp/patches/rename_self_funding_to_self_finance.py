import frappe


def execute():
    """
    Rename 'Self Funding' to 'Self Finance' in the custom_finance_type field on Job File:
    1. Update the Custom Field options list.
    2. Update existing Job File records that carry the old value.
    3. Update the depends_on expression on the related section-break Custom Field.
    """
    cf_name = "Job File-custom_finance_type"

    if not frappe.db.exists("Custom Field", cf_name):
        return

    # 1. Update field options
    frappe.db.set_value(
        "Custom Field",
        cf_name,
        "options",
        "Self Finance\nBank Loan",
    )

    # 2. Update existing records
    frappe.db.sql(
        """
        UPDATE `tabJob File`
        SET custom_finance_type = 'Self Finance'
        WHERE custom_finance_type = 'Self Funding'
        """
    )

    # 3. Update depends_on on any Custom Field that references the old value
    frappe.db.sql(
        """
        UPDATE `tabCustom Field`
        SET depends_on = REPLACE(depends_on, 'Self Funding', 'Self Finance')
        WHERE dt = 'Job File'
          AND depends_on LIKE '%Self Funding%'
        """
    )

    frappe.db.commit()
    frappe.clear_cache(doctype="Job File")
