import frappe


def execute():
	doctype = "DISCOM Process Tracker"
	fieldname = "installation_status"
	options = "yes\nno"

	# Update DocField options + label
	frappe.db.set_value(
		"DocField",
		{"parent": doctype, "fieldname": fieldname},
		{"fieldtype": "Select", "options": options, "label": "Documents Uploaded"},
	)

	# If a Property Setter overrides DocField options, align it too.
	if frappe.db.exists(
		"Property Setter",
		{
			"doc_type": doctype,
			"field_name": fieldname,
			"property": "options",
		},
	):
		frappe.db.set_value(
			"Property Setter",
			{
				"doc_type": doctype,
				"field_name": fieldname,
				"property": "options",
			},
			"value",
			options,
		)

	if frappe.db.table_exists(doctype) and frappe.db.has_column(doctype, fieldname):
		# Previous values: Pending / Completed / Docs Uploaded
		frappe.db.sql(
			"""
			UPDATE `tabDISCOM Process Tracker`
			SET `installation_status` = 'yes'
			WHERE `installation_status` = 'Docs Uploaded'
			"""
		)
		frappe.db.sql(
			"""
			UPDATE `tabDISCOM Process Tracker`
			SET `installation_status` = 'no'
			WHERE `installation_status` IN ('Pending', 'Completed')
			"""
		)
		# Normalize empty values too (optional but keeps UI consistent)
		frappe.db.sql(
			"""
			UPDATE `tabDISCOM Process Tracker`
			SET `installation_status` = 'no'
			WHERE `installation_status` IS NULL OR `installation_status` = ''
			"""
		)

	frappe.db.commit()
	frappe.clear_cache(doctype=doctype)

