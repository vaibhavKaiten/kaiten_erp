import frappe


def execute():
	frappe.delete_doc_if_exists("Custom Field", "Meter Installation-custom_location_log")
