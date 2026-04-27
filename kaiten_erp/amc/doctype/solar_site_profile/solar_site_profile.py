import frappe
from frappe.model.document import Document


class SolarSiteProfile(Document):
	"""Solar Site Profile - Tracks customer installation sites"""

	def validate(self):
		"""Validate site profile data"""
		self.validate_dates()

	def validate_dates(self):
		"""Ensure installation date is reasonable"""
		from datetime import datetime
		if self.installation_date > datetime.now().date():
			frappe.throw("Installation date cannot be in the future")
