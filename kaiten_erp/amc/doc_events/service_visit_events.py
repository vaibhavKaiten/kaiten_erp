import frappe
from frappe import _


def validate(doc, method=None):
	"""Validate Service Visit"""
	
	# Validate dates
	if doc.actual_visit_date and doc.actual_visit_date > frappe.utils.today():
		frappe.throw(_("Actual visit date cannot be in the future"))
	
	# Validate timing
	if doc.visit_start_time and doc.visit_end_time:
		if doc.visit_start_time >= doc.visit_end_time:
			frappe.throw(_("Visit start time must be before end time"))
	
	# Validate technician
	if doc.technician:
		emp = frappe.get_doc("Employee", doc.technician)
		if emp.status != "Active":
			frappe.throw(_("Technician must be an active employee"))


def on_submit(doc, method=None):
	"""When visit is submitted:
	1. Increment visits_completed on contract
	2. Calculate billable parts amount
	3. Create Stock Entry for parts if needed
	"""
	
	# Update contract visits
	contract = frappe.get_doc("AMC Contract", doc.amc_contract)
	contract.visits_completed += 1
	contract.save(ignore_permissions=True)
	
	# Calculate billable parts
	calculate_billable_parts(doc)
	
	# Create stock entry
	create_stock_entry_for_parts(doc)


def on_cancel(doc, method=None):
	"""When visit is cancelled:
	1. Decrement visits_completed
	2. Cancel corresponding Stock Entry
	"""
	
	# Decrement visits on contract
	contract = frappe.get_doc("AMC Contract", doc.amc_contract)
	contract.visits_completed = max(0, contract.visits_completed - 1)
	contract.save(ignore_permissions=True)
	
	# Cancel related stock entries
	cancel_stock_entry(doc)


def calculate_billable_parts(doc):
	"""Calculate billable parts amount based on contract limit"""
	
	contract = frappe.get_doc("AMC Contract", doc.amc_contract)
	billable_amount = 0
	
	for row in doc.parts_used:
		if row.amount > contract.parts_limit:
			billable_amount += row.amount - contract.parts_limit
			row.billable = 1
		else:
			row.within_contract_limit = 1
	
	doc.billable_parts_amount = billable_amount
	doc.db_update()


def create_stock_entry_for_parts(doc):
	"""Create Stock Entry to consume parts from inventory"""
	
	if not doc.parts_used:
		return
	
	try:
		# Get warehouse
		warehouses = frappe.get_all("Warehouse", filters={"warehouse_type": "Free Supplies"}, limit=1)
		if not warehouses:
			warehouses = frappe.get_all("Warehouse", limit=1)
		
		if not warehouses:
			frappe.msgprint(_("No warehouse configured. Stock entry not created."))
			return
		
		warehouse = warehouses[0].name
		
		# Create Stock Entry
		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"purpose": "Material Issue",
			"stock_entry_type": "Material Issue",
			"company": frappe.defaults.get_default("Company"),
			"from_warehouse": warehouse,
			"remarks": f"Parts consumed in Service Visit {doc.name}",
			"items": [
				{
					"item_code": row.item,
					"qty": row.qty,
					"basic_rate": row.rate,
					"uom": frappe.get_value("Item", row.item, "stock_uom") or "Nos"
				}
				for row in doc.parts_used
			]
		})
		
		se.insert(ignore_permissions=True)
		se.submit(ignore_permissions=True)
		
	except Exception as e:
		frappe.log_error(f"Error creating stock entry for visit {doc.name}: {str(e)}")


def cancel_stock_entry(doc):
	"""Cancel related Stock Entry"""
	
	try:
		stock_entries = frappe.get_all("Stock Entry", filters={
			"remarks": ["like", f"%Service Visit {doc.name}%"],
			"docstatus": 1
		}, fields=["name"])
		
		for se in stock_entries:
			se_doc = frappe.get_doc("Stock Entry", se.name)
			se_doc.cancel()
	
	except Exception as e:
		frappe.log_error(f"Error cancelling stock entry for visit {doc.name}: {str(e)}")
