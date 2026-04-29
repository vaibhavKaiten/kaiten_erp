import frappe


def get_permission_query_conditions(user):
	"""Filter Complaints based on user role"""
	
	if frappe.session.user == "Administrator":
		return ""
	
	# All authenticated users can see complaints
	return ""


def has_permission(doc, ptype=None, user=None):
    """Check if user has permission on specific complaint"""

    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    user_doc = frappe.get_doc("User", user)

    # System Manager has full access
    if "System Manager" in user_doc.get_roles():
        return True

    # AMC Manager & Sales User can CRUD all complaints
    if ptype in ["read", "write", "create", "submit"]:
        if "Sales User" in user_doc.get_roles() or "AMC Manager" in user_doc.get_roles():
            return True

    # Service Technicians can read all but only submit/update assigned ones
    if "Service Technician" in user_doc.get_roles():
        employee = frappe.get_value("Employee", {"user_id": user}, "name")

        if ptype == "read":
            return True

        if ptype in ["write", "submit"] and doc.assigned_to == employee:
            return True

    # Customers can create and read their own complaints
    if "Customer" in user_doc.get_roles() and ptype in ["create", "read"]:
        if frappe.has_user_permission(doc, user, "Customer", doc.customer):
            return True

    return False
