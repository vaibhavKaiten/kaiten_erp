import frappe


def _is_privileged(user: str) -> bool:
    """System Manager and Administrator keep full visibility."""
    return user in {"Administrator"} or "System Manager" in frappe.get_roles(user)


def todo_permission_query(user):
    """
    Limit ToDo list to items explicitly allocated_to the current user
    unless the user is privileged (System Manager/Administrator).
    """
    if _is_privileged(user):
        return ""

    user_esc = frappe.db.escape(user)
    # allocated_to is a Link field; restrict strictly to exact match
    return f"`tabToDo`.`allocated_to` = {user_esc}"


def todo_has_permission(doc, user=None):
    """
    Form-level permission: allow if privileged, allocated_to matches user,
    or user has permission to access referenced document.
    """
    user = user or frappe.session.user

    if _is_privileged(user):
        return True

    # Direct allocation check
    if doc.allocated_to == user:
        return True
    
    # For cross-document references, check if user can access the referenced document
    if doc.reference_type and doc.reference_name:
        try:
            # Import the permission module for the referenced doctype
            if doc.reference_type == "Technical Survey":
                from kaiten_erp.kaiten_erp.permissions.technical_survey_permissions import has_permission as ts_has_permission
                ref_doc = frappe.get_doc(doc.reference_type, doc.reference_name)
                return ts_has_permission(ref_doc, "read", user)
        except Exception:
            # If we can't check the referenced document, fall back to standard check
            pass
    
    return False
