# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
import secrets
from frappe.model.naming import make_autoname
from frappe.website.website_generator import WebsiteGenerator


class JobFile(WebsiteGenerator):
	def before_save(self):
		if not self.route:
			self.set_route()
		if not self.custom_web_access_token:
			self.custom_web_access_token = secrets.token_urlsafe(32)
		self.published = 1

	def autoname(self):
		# Get first_name from lead if not already set
		if not self.first_name and self.lead:
			lead_doc = frappe.get_doc("Lead", self.lead)
			self.first_name = lead_doc.first_name
		
		# Generate name with first_name
		first_name = self.first_name or "UNKNOWN"
		# Clean first_name to remove any spaces or special characters for naming
		clean_first_name = "".join(c for c in first_name if c.isalnum()).upper()
		
		# Generate the name using the existing pattern but with populated first_name
		self.name = make_autoname(f"JOB-{clean_first_name}-.YYYY.-.#####")

	def get_context(self, context):
		request_token = frappe.form_dict.get("token")
		if frappe.session.user != "Administrator":
			if not request_token or request_token != self.custom_web_access_token:
				frappe.throw(
					"Invalid or missing web access token for this Job File.",
					frappe.PermissionError,
				)

		context.title = self.name
		context.doc = self
		context.execution_stages = [
			{
				"stage": row.stage or "",
				"status": row.status or "",
				"supplier": row.supplier or "",
				"referrence_doctype": row.referrence_doctype or "",
			}
			for row in (self.table_royw or [])
		]
		context.customer_mobile = getattr(self, "mobile_number", "") or ""
		context.job_file_workflow_state = self.workflow_state or ""