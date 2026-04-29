import frappe
from frappe import _


@frappe.whitelist()
def create_solar_site_profile(job_file_name):
	"""Create a Solar Site Profile from a Job File, or return existing one."""

	existing = frappe.db.get_value(
		"Solar Site Profile", {"job_file": job_file_name}, "name"
	)
	if existing:
		return {"name": existing, "existing": True}

	job_file = frappe.get_doc("Job File", job_file_name)

	# Build address string for site_name
	address_parts = filter(None, [
		job_file.get("address_line_1"),
		job_file.get("city"),
		job_file.get("state"),
	])
	address_hint = ", ".join(address_parts) or job_file_name

	site = frappe.new_doc("Solar Site Profile")
	site.site_name = address_hint
	site.job_file = job_file_name
	site.customer = job_file.get("customer")
	site.status = "Active"

	site.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"name": site.name, "existing": False}
