import frappe


def execute():
	options = "Technical Survey\nMarketing"
	default = "Technical Survey"

	# Update Technical Survey – built-in visit_type field
	frappe.db.set_value(
		"DocField",
		{"parent": "Technical Survey", "fieldname": "visit_type"},
		{
			"fieldtype": "Select",
			"options": options,
			"default": default,
		},
	)

	# Update Structure Mounting – custom_visit_type custom field
	frappe.db.set_value(
		"Custom Field",
		"Structure Mounting-custom_visit_type",
		{
			"fieldtype": "Select",
			"options": options,
			"default": default,
		},
	)

	frappe.db.commit()

	# Ensure the DB columns can hold the select value
	frappe.db.sql(
		"ALTER TABLE `tabTechnical Survey` MODIFY `visit_type` varchar(140) DEFAULT %s",
		(default,),
	)
	frappe.db.sql(
		"ALTER TABLE `tabStructure Mounting` MODIFY `custom_visit_type` varchar(140) DEFAULT %s",
		(default,),
	)
