import frappe


def get_permission_query_conditions(user):
	"""Filter Solar Site profiles based on user role"""
	
	if frappe.session.user == "Administrator":
		return ""
	
	# All authenticated users can see all sites (for now)
	# In future: add territory/customer-level filters
	return ""


def has_permission(doc, ptype=None, user=None):
    """Check if user has permission on specific site profile"""

    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    user_doc = frappe.get_doc("User", user)

    # System Manager has full access
    if "System Manager" in user_doc.get_roles():
        return True

    # Sales User can create/edit sites
    if ptype in ["read", "write", "create"]:
        if "Sales User" in user_doc.get_roles() or "AMC Manager" in user_doc.get_roles():
            return True

    # Customers can only read their own sites
    if ptype == "read":
        if doc.customer:
            # Check if user is linked to this customer
            customer_user = frappe.get_value("Customer", doc.customer, "customer_type")
            if user == frappe.get_value("Customer", doc.customer, "contact_email"):
                return True

    return False
