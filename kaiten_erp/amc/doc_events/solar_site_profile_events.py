import frappe
from frappe import _


def validate(doc, method=None):
	"""Validate Solar Site Profile"""
	from datetime import datetime
	
	if doc.installation_date > datetime.now().date():
		frappe.throw(_("Installation date cannot be in the future"))
