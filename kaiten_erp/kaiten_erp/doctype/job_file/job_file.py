# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import os
import frappe
import secrets
from frappe.model.naming import make_autoname
from frappe.website.website_generator import WebsiteGenerator


# Map fieldname -> human-readable label used in the ZIP file name
SNAPSHOT_ATTACH_FIELDS = {
	"custom_electricity_bill_photo": "Electricity Bill Photo",
	"custom_aadhar_card": "Aadhar Card",
	"custom_property_ownership_document": "Property Ownership Document",
	"custom_bank_passbookcheque_": "Bank Passbook Cheque",
	"custom_pan_card": "Pan Card",
	"custom_property_photo": "Property Photo with Geo tagging",
}


class JobFile(WebsiteGenerator):
	def before_save(self):
		if not self.route:
			self.set_route()
		if not self.get("custom_web_access_token"):
			self.custom_web_access_token = secrets.token_urlsafe(32)
		self.published = 1

		# Rename snapshot attachment files to "{job_file_name} - {field_label}.{ext}"
		# so they are uniquely identifiable in the File library.
		if self.name:
			self._rename_snapshot_attachments()

	def _rename_snapshot_attachments(self):
		"""
		For each Customer Site Snapshot attachment field, find the linked File doc
		and rename it to "{self.name} - {field_label}.{ext}" if it hasn't been
		renamed already.
		"""
		for fieldname, label in SNAPSHOT_ATTACH_FIELDS.items():
			file_url = self.get(fieldname)
			if not file_url:
				continue

			# Frappe Attach fields store the file_url directly (a string like /files/foo.jpg)
			file_docs = frappe.get_all(
				"File",
				filters={
					"file_url": file_url,
					"attached_to_doctype": "Job File",
					"attached_to_name": self.name,
					"attached_to_field": fieldname,
				},
				fields=["name", "file_name"],
				limit_page_length=1,
			)

			if not file_docs:
				# Fallback: match by url + doctype/name without field filter
				file_docs = frappe.get_all(
					"File",
					filters={
						"file_url": file_url,
						"attached_to_doctype": "Job File",
						"attached_to_name": self.name,
					},
					fields=["name", "file_name"],
					limit_page_length=1,
				)

			if not file_docs:
				continue

			file_doc = frappe.get_doc("File", file_docs[0]["name"])
			original_name = file_doc.file_name or ""
			_, ext = os.path.splitext(original_name)

			desired_name = f"{self.name} - {label}{ext}"

			# Skip if already correctly named
			if original_name == desired_name:
				continue

			file_doc.file_name = desired_name
			# Also update attached_to_field so the download lookup is reliable
			file_doc.attached_to_field = fieldname
			file_doc.save(ignore_permissions=True)

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