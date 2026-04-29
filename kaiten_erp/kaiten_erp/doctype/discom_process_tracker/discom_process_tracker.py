# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import base64
import json
import os
import zipfile
from io import BytesIO

import frappe
from frappe.model.document import Document


class DISCOMProcessTracker(Document):
	pass


def _normalize_attach_value(val):
	"""
	`Attach` fields in Frappe usually store a JSON-serialized list of file URLs.
	This helper normalizes those values into a list.
	"""
	if not val:
		return []
	if isinstance(val, (list, tuple)):
		return list(val)
	if not isinstance(val, str):
		return [str(val)]

	s = val.strip()
	if not s:
		return []

	# Common case: JSON list stored as a string
	try:
		parsed = json.loads(s)
		if isinstance(parsed, list):
			return parsed
		if isinstance(parsed, str):
			return [parsed]
	except Exception:
		# Fall back to treating it as a single value
		pass

	return [s]


def _resolve_file_docs(value):
	"""
	Resolve a File doc from an Attach field element.
	`value` is usually a `file_url` (e.g. `/files/foo.pdf`) but may also be a File docname.
	"""
	if not value:
		return []

	s = str(value).strip()
	if not s:
		return []

	# If it already looks like a File docname
	if frappe.db.exists("File", s):
		return [frappe.get_doc("File", s)]

	# Normalize file_url-ish values
	candidates = []
	if s.startswith("files/"):
		candidates.append("/" + s)
	candidates.append(s)
	if s.startswith("private/") and not s.startswith("/"):
		candidates.append("/" + s)

	file_docs = []
	for file_url in candidates:
		if file_url and file_url.startswith("/"):
			for d in frappe.get_all(
				"File",
				filters={"file_url": file_url},
				fields=["name"],
				limit_page_length=50,
			):
				file_docs.append(frappe.get_doc("File", d.name))

	if file_docs:
		return file_docs

	# Last resort: match by file_name
	for d in frappe.get_all(
		"File",
		filters={"file_name": s},
		fields=["name"],
		limit_page_length=20,
	):
		file_docs.append(frappe.get_doc("File", d.name))

	return file_docs


@frappe.whitelist()
def download_customer_site_snapshot_docs(docname):
	"""
	Create a ZIP of Job File "Customer Site Snapshot" attachments and return it as base64.
	The client triggers the browser download (single click).
	"""
	tracker = frappe.get_doc("DISCOM Process Tracker", docname)
	if not tracker.job_file:
		frappe.throw("Job File is required to download Customer Site Snapshot documents.")

	job_file = frappe.get_doc("Job File", tracker.job_file)

	# Attachment fields inside Job File -> Customer Site Snapshot tab
	attach_fieldnames = [
		"custom_electricity_bill_photo",
		"custom_aadhar_card",
		"custom_property_ownership_document",
		"custom_bank_passbookcheque_",
		"custom_pan_card",
		"custom_property_photo",
	]

	unique_file_docs = []
	seen = set()
	for fieldname in attach_fieldnames:
		val = job_file.get(fieldname)
		for item in _normalize_attach_value(val):
			for file_doc in _resolve_file_docs(item):
				if file_doc.name in seen:
					continue
				seen.add(file_doc.name)
				unique_file_docs.append(file_doc)

	if not unique_file_docs:
		frappe.throw("No Customer Site Snapshot documents found to download.")

	zip_buffer = BytesIO()
	with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
		for file_doc in unique_file_docs:
			try:
				content = file_doc.get_content()
			except Exception:
				# Skip broken/missing File entries
				continue

			arcname = file_doc.file_name or os.path.basename(file_doc.file_url or file_doc.name)
			if not arcname:
				arcname = file_doc.name

			# Avoid duplicate names inside ZIP
			if arcname in zf.namelist():
				arcname = f"{file_doc.name}_{arcname}"

			zf.writestr(arcname, content)

	zip_buffer.seek(0)

	b64 = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")
	file_name = f"{tracker.name}_customer_site_snapshot_docs.zip"
	return {"b64": b64, "file_name": file_name}
