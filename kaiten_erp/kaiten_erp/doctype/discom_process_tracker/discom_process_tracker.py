# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import base64
import os
import zipfile
from io import BytesIO

import frappe
from frappe.model.document import Document


class DISCOMProcessTracker(Document):
	pass


# Ordered list of (fieldname, label) for the Customer Site Snapshot attachments.
# Must match SNAPSHOT_ATTACH_FIELDS in job_file.py.
SNAPSHOT_ATTACH_FIELDS = [
	("custom_electricity_bill_photo", "Electricity Bill Photo"),
	("custom_aadhar_card", "Aadhar Card"),
	("custom_property_ownership_document", "Property Ownership Document"),
	("custom_bank_passbookcheque_", "Bank Passbook Cheque"),
	("custom_pan_card", "Pan Card"),
	("custom_property_photo", "Property Photo with Geo tagging"),
]


@frappe.whitelist()
def download_customer_site_snapshot_docs(docname):
	"""
	Create a ZIP of Job File "Customer Site Snapshot" attachments and return it as base64.
	Files are fetched only for the specific Job File (attached_to_doctype + attached_to_name
	+ attached_to_field) so no files from other records are included.
	Each file is named "{job_file_name} - {field_label}.{ext}" inside the ZIP.
	"""
	tracker = frappe.get_doc("DISCOM Process Tracker", docname)
	if not tracker.job_file:
		frappe.throw("Job File is required to download Customer Site Snapshot documents.")

	job_file_name = tracker.job_file
	job_file = frappe.get_doc("Job File", job_file_name)

	zip_buffer = BytesIO()
	files_added = 0

	with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
		for fieldname, label in SNAPSHOT_ATTACH_FIELDS:
			file_url = job_file.get(fieldname)
			if not file_url:
				continue

			# Look up the File doc that belongs specifically to this Job File field
			file_docs = frappe.get_all(
				"File",
				filters={
					"attached_to_doctype": "Job File",
					"attached_to_name": job_file_name,
					"attached_to_field": fieldname,
				},
				fields=["name", "file_name", "file_url"],
				limit_page_length=1,
			)

			if not file_docs:
				# Fallback: match by file_url + doctype/name (covers files saved before
				# the attached_to_field was populated)
				file_docs = frappe.get_all(
					"File",
					filters={
						"file_url": file_url,
						"attached_to_doctype": "Job File",
						"attached_to_name": job_file_name,
					},
					fields=["name", "file_name", "file_url"],
					limit_page_length=1,
				)

			if not file_docs:
				continue

			file_doc = frappe.get_doc("File", file_docs[0]["name"])

			try:
				content = file_doc.get_content()
			except Exception:
				# Skip broken / missing files
				continue

			# Determine extension from the stored file_name
			original_name = file_doc.file_name or os.path.basename(file_doc.file_url or "")
			_, ext = os.path.splitext(original_name)

			arcname = f"{job_file_name} - {label}{ext}"

			# Guard against duplicate arc names (shouldn't happen, but be safe)
			if arcname in zf.namelist():
				arcname = f"{arcname}_{files_added}"

			zf.writestr(arcname, content)
			files_added += 1

	if not files_added:
		frappe.throw("No Customer Site Snapshot documents found for this Job File.")

	zip_buffer.seek(0)
	b64 = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")
	file_name = f"{job_file_name}_customer_site_snapshot_docs.zip"
	return {"b64": b64, "file_name": file_name}

