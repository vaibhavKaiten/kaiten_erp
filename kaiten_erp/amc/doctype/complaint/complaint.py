import frappe
from frappe.model.document import Document
from frappe import _
from datetime import timedelta


class Complaint(Document):
	"""Complaint - Customer complaint tracking for solar systems"""

	def validate(self):
		"""Validate complaint data"""
		self.validate_resolution_date()

	def validate_resolution_date(self):
		"""Ensure resolved_on >= reported_on"""
		if self.resolved_on and self.reported_on:
			if self.resolved_on < self.reported_on:
				frappe.throw(_("Resolution date cannot be before reported date"))

	def before_insert(self):
		"""Set reported_on and calculate SLA before insertion"""
		if not self.reported_on:
			self.reported_on = frappe.utils.now()

	def after_insert(self):
		"""After insert, calculate SLA deadline"""
		self.calculate_sla_deadline()
		self.auto_assign_technician()
		self.db_update()

	def calculate_sla_deadline(self):
		"""Calculate SLA deadline based on contract or default"""
		if self.amc_contract:
			contract = frappe.get_doc("AMC Contract", self.amc_contract)
			sla_hours = contract.sla_response_hours
		else:
			# Default SLA if no contract
			sla_hours = 24

		# Add hours to reported_on
		from datetime import datetime, timedelta
		reported = datetime.fromisoformat(str(self.reported_on))
		self.sla_deadline = reported + timedelta(hours=sla_hours)

	def auto_assign_technician(self):
		"""Auto-assign technician to complaint if available"""
		# Get active technicians
		technicians = frappe.get_all(
			"Employee",
			filters={"status": "Active", "user_id": ["!=", ""]},
			fields=["name", "user_id"],
			limit=1
		)

		if technicians:
			self.assigned_to = technicians[0].name
		else:
			# If no technician available, assign to Service Manager
			service_managers = frappe.get_all(
				"User",
				filters={"role_profile_name": ["like", "%Manager%"]},
				fields=["name"],
				limit=1
			)
			if service_managers:
				emp = frappe.get_all(
					"Employee",
					filters={"user_id": service_managers[0].name},
					fields=["name"],
					limit=1
				)
				if emp:
					self.assigned_to = emp[0].name

	def on_submit(self):
		"""When complaint is submitted, set status to Assigned"""
		self.status = "Assigned"
		self.db_update()

	def on_update(self):
		"""Track SLA breach status"""
		if self.status not in ["Closed", "Resolved"] and self.sla_deadline:
			from datetime import datetime
			if datetime.fromisoformat(str(frappe.utils.now())) > datetime.fromisoformat(str(self.sla_deadline)):
				self.status = "Escalated"
				self.db_update()
