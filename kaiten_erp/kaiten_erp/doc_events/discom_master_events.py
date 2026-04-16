# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""DISCOM Master event handlers."""

import frappe


def on_update(doc, method=None):
	"""
	When a DISCOM Linked Customer row's status changes to 'Completed',
	auto-close any open DISCOM Manager ToDos for that customer's Sales Order.
	"""
	old_doc = doc.get_doc_before_save()
	old_rows = {}
	if old_doc:
		for row in (old_doc.get("linked_customers") or []):
			old_rows[row.name] = row.status or "Pending"

	for row in (doc.get("linked_customers") or []):
		old_status = old_rows.get(row.name, "Pending")
		current_status = row.status or "Pending"

		# Status just changed to "Completed" for this customer row
		if current_status == "Completed" and old_status != "Completed":
			# Use the stored job_file link; fall back to DB lookup by customer+discom
			job_file_name = row.job_file
			if not job_file_name:
				job_file_name = frappe.db.get_value(
					"Job File",
					{"customer": row.customer, "discom": doc.name},
					"name",
				)
			_close_discom_todos_for_job_file(doc.name, job_file_name)


def _close_discom_todos_for_job_file(discom_master_name, job_file_name):
	"""Close open DISCOM Manager ToDos for a specific job file when its DISCOM process is completed."""
	if not job_file_name:
		return

	# Primary: use the sales_order field on Job File
	so_name = frappe.db.get_value("Job File", job_file_name, "sales_order")

	# Fallback: search for a submitted Sales Order that links to this Job File
	if not so_name:
		so_name = frappe.db.get_value(
			"Sales Order",
			{"custom_job_file": job_file_name, "docstatus": 1},
			"name",
		)

	if not so_name:
		return

	todos = frappe.db.get_all(
		"ToDo",
		filters={
			"reference_type": "DISCOM Master",
			"reference_name": discom_master_name,
			"role": "DISCOM Manager",
			"status": "Open",
			"description": ["like", f"% | {so_name}"],
		},
		fields=["name"],
	)
	for t in todos:
		frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)

	if todos:
		frappe.logger("kaiten_erp").info(
			f"Closed {len(todos)} DISCOM Manager ToDo(s) for Sales Order {so_name} after DISCOM completion"
		)
