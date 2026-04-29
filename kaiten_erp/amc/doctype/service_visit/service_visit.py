import frappe
from frappe.model.document import Document
from frappe import _


class ServiceVisit(Document):
	"""Service Visit - Record of preventive/breakdown service visits"""

	def validate(self):
		"""Validate visit data"""
		self.validate_dates()
		self.validate_technician()

	def validate_dates(self):
		"""Ensure timing is logical"""
		if self.actual_visit_date and self.actual_visit_date > frappe.utils.today():
			frappe.throw(_("Actual visit date cannot be in the future"))

		if self.visit_start_time and self.visit_end_time:
			if self.visit_start_time >= self.visit_end_time:
				frappe.throw(_("Visit start time must be before end time"))

	def validate_technician(self):
		"""Ensure technician is valid"""
		if self.technician:
			emp = frappe.get_doc("Employee", self.technician)
			if emp.status != "Active":
				frappe.throw(_("Technician must be an active employee"))

	def on_submit(self):
		"""When visit is submitted:
		1. Increment visits_completed on contract
		2. Update billable_parts_amount
		3. Create Stock Entry for parts if needed
		"""
		self.update_contract_visits()
		self.calculate_billable_parts()
		self.create_stock_entry_for_parts()

	def update_contract_visits(self):
		"""Increment visits_completed on the linked contract"""
		contract = frappe.get_doc("AMC Contract", self.amc_contract)
		contract.visits_completed += 1
		contract.save(ignore_permissions=True)

	def calculate_billable_parts(self):
		"""Calculate billable parts amount based on contract limit"""
		contract = frappe.get_doc("AMC Contract", self.amc_contract)
		total_parts = 0
		billable_amount = 0

		for row in self.parts_used:
			total_parts += row.amount
			if row.amount > contract.parts_limit:
				billable_amount += row.amount - contract.parts_limit
				row.billable = 1

		self.billable_parts_amount = billable_amount
		self.db_update()

	def create_stock_entry_for_parts(self):
		"""Create Stock Entry to consume parts from inventory"""
		if not self.parts_used:
			return

		# Get contract to find warehouse
		contract = frappe.get_doc("AMC Contract", self.amc_contract)
		site = frappe.get_doc("Solar Site Profile", contract.solar_site)

		try:
			warehouse = frappe.get_value("Warehouse", {"name": frappe.defaults.get_default("stock_entry_default_warehouse")})
		except:
			warehouse = frappe.get_value("Warehouse", {"company": frappe.defaults.get_default("Company"), "warehouse_type": "Free Supplies"}, "name")

		if not warehouse:
			frappe.msgprint(_("Warehouse not configured. Please configure default warehouse for stock entry."))
			return

		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"purpose": "Material Issue",
			"stock_entry_type": "Material Issue",
			"company": frappe.defaults.get_default("Company"),
			"from_warehouse": warehouse,
			"remarks": f"Parts consumed in Service Visit {self.name} at {site.site_name}",
			"items": [
				{
					"item_code": row.item,
					"qty": row.qty,
					"basic_rate": row.rate,
					"uom": frappe.get_value("Item", row.item, "stock_uom") or "Nos"
				}
				for row in self.parts_used
			]
		})

		se.insert(ignore_permissions=True)
		se.submit(ignore_permissions=True)

	def on_cancel(self):
		"""When visit is cancelled:
		1. Decrement visits_completed
		2. Cancel corresponding Stock Entry
		"""
		self.update_contract_visits_cancel()
		self.cancel_stock_entry()

	def update_contract_visits_cancel(self):
		"""Decrement visits_completed on cancel"""
		contract = frappe.get_doc("AMC Contract", self.amc_contract)
		contract.visits_completed = max(0, contract.visits_completed - 1)
		contract.save(ignore_permissions=True)

	def cancel_stock_entry(self):
		"""Cancel related Stock Entry"""
		stock_entries = frappe.get_all("Stock Entry", filters={
			"remarks": ["like", f"%Service Visit {self.name}%"],
			"docstatus": 1
		})

		for se in stock_entries:
			doc = frappe.get_doc("Stock Entry", se.name)
			doc.cancel()
