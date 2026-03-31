# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
import re


class JobFile(Document):
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
	def validate(self):
		if self.k_number:
			if not re.fullmatch(r'\d{12,15}', self.k_number):
				frappe.throw(
					"K Number must be 12 to 15 digits only (no spaces or letters).",
					title="Invalid K Number"
				)