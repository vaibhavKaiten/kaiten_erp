import frappe

def execute():
	"""Remove column break fields from Job File DocType"""
	frappe.db.delete("Custom Field", {
		"fieldname": ["in", [
			"custom_column_break_muqjk",
			"custom_column_break_euqua"
		]],
		"dt": "Job File"
	})
