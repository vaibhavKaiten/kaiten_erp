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
    Form-level permission: allow if privileged or allocated_to matches user.
    """
    user = user or frappe.session.user

    if _is_privileged(user):
        return True

    return doc.allocated_to == user
