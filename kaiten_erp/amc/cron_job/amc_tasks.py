import frappe
from frappe import _
from datetime import datetime, timedelta


def daily_amc_jobs():
	"""Daily AMC maintenance tasks"""
	
	check_amc_expiry()
	check_sla_breach()
	auto_close_resolved_complaints()


def check_amc_expiry():
	"""Create Renewal Notices for contracts expiring in 30 days"""
	
	try:
		# Get contracts expiring in ~30 days
		expiry_date = (datetime.now() + timedelta(days=30)).date()
		
		contracts = frappe.get_all(
			"AMC Contract",
			filters={
				"status": "Active",
				"end_date": ["<=", expiry_date],
				"end_date": [">", datetime.now().date()]
			},
			fields=["name", "customer", "contract_value", "end_date"]
		)
		
		for contract in contracts:
			# Check if Renewal Notice already exists
			existing = frappe.get_all(
				"Renewal Notice",
				filters={
					"amc_contract": contract.name,
					"status": ["!=", "Lapsed"]
				},
				limit=1
			)
			
			if not existing:
				# Create Renewal Notice
				renewal = frappe.get_doc({
					"doctype": "Renewal Notice",
					"amc_contract": contract.name,
					"proposed_value": contract.contract_value,
					"status": "Pending"
				})
				renewal.insert(ignore_permissions=True)
				
				frappe.logger().info(f"Created Renewal Notice for contract {contract.name}")
	
	except Exception as e:
		frappe.logger().error(f"Error in check_amc_expiry: {str(e)}")


def check_sla_breach():
	"""Check for complaints breaching SLA and mark as Escalated"""
	
	try:
		now = datetime.now()
		
		# Get open complaints past SLA deadline
		complaints = frappe.get_all(
			"Complaint",
			filters={
				"status": ["in", ["Open", "Assigned", "In Progress"]],
				"sla_deadline": ["<", now]
			},
			fields=["name", "status"]
		)
		
		for complaint in complaints:
			doc = frappe.get_doc("Complaint", complaint.name)
			doc.status = "Escalated"
			doc.save(ignore_permissions=True)
			
			frappe.logger().info(f"Escalated complaint {complaint.name} due to SLA breach")
	
	except Exception as e:
		frappe.logger().error(f"Error in check_sla_breach: {str(e)}")


def auto_close_resolved_complaints():
	"""Auto-close complaints resolved >7 days ago"""
	
	try:
		close_date = (datetime.now() - timedelta(days=7)).date()
		
		# Get resolved complaints older than 7 days
		complaints = frappe.get_all(
			"Complaint",
			filters={
				"status": "Resolved",
				"resolved_on": ["<", close_date]
			},
			fields=["name"]
		)
		
		for complaint in complaints:
			doc = frappe.get_doc("Complaint", complaint.name)
			doc.status = "Closed"
			doc.save(ignore_permissions=True)
			
			frappe.logger().info(f"Auto-closed complaint {complaint.name}")
	
	except Exception as e:
		frappe.logger().error(f"Error in auto_close_resolved_complaints: {str(e)}")
