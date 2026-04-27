import frappe
from frappe import _


def validate(doc, method=None):
	"""Validate AMC Contract"""
	
	# Validate dates
	if doc.end_date <= doc.start_date:
		frappe.throw(_("End date must be after start date"))
	
	# Validate visits
	if doc.visits_per_year <= 0:
		frappe.throw(_("Visits per year must be greater than 0"))
	
	# Auto-set visits per year based on contract type
	visit_defaults = {
		"Basic": 2,
		"Comprehensive": 4,
		"Premium": 6
	}
	if doc.contract_type in visit_defaults and not doc.visits_per_year:
		doc.visits_per_year = visit_defaults[doc.contract_type]


def on_submit(doc, method=None):
	"""When contract is submitted, set status to Active"""
	doc.status = "Active"
	doc.db_update()


def on_cancel(doc, method=None):
	"""When contract is cancelled"""
	doc.status = "Cancelled"
	doc.db_update()
