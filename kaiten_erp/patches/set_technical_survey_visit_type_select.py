import frappe


def execute():
	doctype = "Technical Survey"
	fieldname = "visit_type"
	options = "Technical Survey\nMarketing"

	# Update the DocField meta record
	frappe.db.set_value(
		"DocField",
		{"parent": doctype, "fieldname": fieldname},
		{
			"fieldtype": "Select",
			"options": options,
		},
	)

	frappe.db.commit()

	# Ensure the DB column can hold the select value (varchar 140)
	frappe.db.sql(
		"ALTER TABLE `tabTechnical Survey` MODIFY `visit_type` varchar(140) DEFAULT NULL"
	)
