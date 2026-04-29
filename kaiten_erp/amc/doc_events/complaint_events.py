import frappe
from frappe import _
from datetime import datetime, timedelta


def before_insert(doc, method=None):
	"""Set reported_on before insertion"""
	if not doc.reported_on:
		doc.reported_on = frappe.utils.now()


def after_insert(doc, method=None):
	"""After insert, calculate SLA deadline and auto-assign technician"""
	
	calculate_sla_deadline(doc)
	auto_assign_technician(doc)


def validate(doc, method=None):
	"""Validate Complaint"""
	
	# Validate resolution date
	if doc.resolved_on and doc.reported_on:
		if doc.resolved_on < doc.reported_on:
			frappe.throw(_("Resolution date cannot be before reported date"))


def on_submit(doc, method=None):
	"""When complaint is submitted, set status to Assigned"""
	doc.status = "Assigned"
	doc.db_update()


def on_update(doc, method=None):
	"""Track SLA breach status"""
	
	if doc.status not in ["Closed", "Resolved"] and doc.sla_deadline:
		try:
			now = datetime.fromisoformat(str(frappe.utils.now()))
			deadline = datetime.fromisoformat(str(doc.sla_deadline))
			
			if now > deadline:
				doc.status = "Escalated"
				doc.db_update()
		except:
			pass


def calculate_sla_deadline(doc):
	"""Calculate SLA deadline based on contract or default"""
	
	if doc.amc_contract:
		contract = frappe.get_doc("AMC Contract", doc.amc_contract)
		sla_hours = contract.sla_response_hours
	else:
		# Default SLA if no contract
		sla_hours = 24
	
	# Add hours to reported_on
	try:
		reported = datetime.fromisoformat(str(doc.reported_on))
		doc.sla_deadline = reported + timedelta(hours=sla_hours)
	except:
		pass


def auto_assign_technician(doc):
	"""Auto-assign technician to complaint if available"""
	
	try:
		# Get active technicians
		technicians = frappe.get_all(
			"Employee",
			filters={"status": "Active"},
			fields=["name"],
			limit=1
		)
		
		if technicians:
			doc.assigned_to = technicians[0].name
	except:
		pass
