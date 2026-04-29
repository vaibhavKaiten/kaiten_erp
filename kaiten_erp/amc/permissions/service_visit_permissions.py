import frappe


def get_permission_query_conditions(user):
	"""Filter Service Visits based on user role"""
	
	if frappe.session.user == "Administrator":
		return ""
	
	# All authenticated users can see all visits
	return ""


def has_permission(doc, perm_type, user):
	"""Check if user has permission on specific service visit"""
	
	if frappe.session.user == "Administrator":
		return True
	
	user_doc = frappe.get_doc("User", user)
	
	# System Manager has full access
	if "System Manager" in user_doc.get_roles():
		return True
	
	# Sales User & AMC Manager can create/edit/submit all visits
	if perm_type in ["read", "write", "create", "submit"]:
		if "Sales User" in user_doc.get_roles() or "AMC Manager" in user_doc.get_roles():
			return True
	
	# Service Technicians can only see/edit visits assigned to them
	if "Service Technician" in user_doc.get_roles():
		# Get Employee linked to this user
		employee = frappe.get_value("Employee", {"user_id": user}, "name")
		if employee and doc.technician == employee:
			return True
	
	return False
