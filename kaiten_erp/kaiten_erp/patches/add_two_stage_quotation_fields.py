# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    custom_fields = {
        "Quotation": [
            {
                "fieldname": "custom_quotation_stage",
                "label": "Quotation Stage",
                "fieldtype": "Select",
                "options": "Pre-Survey Estimate\nFinal Approved",
                "insert_after": "custom_technical_survey",
                "reqd": 1,
                "in_list_view": 1,
            }
        ],
        "Technical Survey": [
            {
                "fieldname": "custom_opportunity",
                "label": "Opportunity",
                "fieldtype": "Link",
                "options": "Opportunity",
                "insert_after": "custom_job_file",
                "reqd": 1,
                "in_list_view": 1,
            }
        ],
    }

    create_custom_fields(custom_fields, update=True)
