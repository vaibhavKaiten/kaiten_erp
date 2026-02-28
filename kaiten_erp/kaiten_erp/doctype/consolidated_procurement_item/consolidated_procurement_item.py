# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ConsolidatedProcurementItem(Document):
	"""
	Child table for Procurement Consolidation
	
	Purpose:
	- Store consolidated procurement items
	- Track quantities, suppliers, and rates
	- Maintain traceability to source Material Requests
	
	This is Phase 1: Structure only, no logic yet
	"""
	pass
