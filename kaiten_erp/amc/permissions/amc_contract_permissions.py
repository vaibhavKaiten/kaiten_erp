import frappe


def get_permission_query_conditions(user):
	"""Filter AMC Contracts based on user role"""
	
	if frappe.session.user == "Administrator":
		return ""
	
	# All authenticated users can see all contracts (for now)
	return ""


def has_permission(doc, ptype=None, user=None):
    """Check if user has permission on specific AMC contract"""

    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    user_doc = frappe.get_doc("User", user)

    # System Manager has full access
    if "System Manager" in user_doc.get_roles():
        return True

    # Sales User & AMC Manager can create/edit/submit contracts
    if ptype in ["read", "write", "create", "submit"]:
        if "Sales User" in user_doc.get_roles() or "AMC Manager" in user_doc.get_roles():
            return True

    # Customers can only read their own contracts
    if ptype == "read":
        if doc.customer:
            # User Permission check
            if frappe.has_user_permission(doc, user, "Customer", doc.customer):
                return True

    return False
