import frappe
from frappe.model.document import Document


class RenewalNotice(Document):
	"""Renewal Notice - Track AMC renewal pipeline"""

	def validate(self):
		"""Validate renewal notice"""
		self.validate_proposed_value()

	def validate_proposed_value(self):
		"""Ensure proposed value is reasonable (at least 80% of original)"""
		if self.amc_contract:
			contract = frappe.get_doc("AMC Contract", self.amc_contract)
			min_value = contract.contract_value * 0.8

			if self.proposed_value < min_value:
				frappe.msgprint(f"Warning: Proposed value is significantly lower than original contract value (₹{contract.contract_value})")
