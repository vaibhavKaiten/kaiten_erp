import frappe
from frappe.model.document import Document
from frappe import _


class AMCContract(Document):
	"""AMC Contract - Annual Maintenance Contract for solar installations"""

	def validate(self):
		"""Validate contract data"""
		self.validate_dates()
		self.validate_visits()
		self.set_visits_per_year_by_type()

	def validate_dates(self):
		"""Ensure end_date > start_date"""
		if self.end_date <= self.start_date:
			frappe.throw(_("End date must be after start date"))

	def validate_visits(self):
		"""Validate visits configuration"""
		if self.visits_per_year <= 0:
			frappe.throw(_("Visits per year must be greater than 0"))

	def set_visits_per_year_by_type(self):
		"""Automatically set visits per year based on contract type"""
		visit_defaults = {
			"Basic": 2,
			"Comprehensive": 4,
			"Premium": 6
		}
		if self.contract_type in visit_defaults and not self.visits_per_year:
			self.visits_per_year = visit_defaults[self.contract_type]

	def on_submit(self):
		"""When contract is submitted, set status to Active"""
		self.status = "Active"
		self.db_update()

	def on_cancel(self):
		"""When contract is cancelled"""
		self.status = "Cancelled"
		self.db_update()
