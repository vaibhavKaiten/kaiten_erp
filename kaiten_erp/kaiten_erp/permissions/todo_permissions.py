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
            permission_modules = {
                "Technical Survey": "kaiten_erp.kaiten_erp.permissions.technical_survey_permissions",
                "Structure Mounting": "kaiten_erp.kaiten_erp.permissions.structure_mounting_permissions",
                "Project Installation": "kaiten_erp.kaiten_erp.permissions.project_installation_permissions",
                "Meter Installation": "kaiten_erp.kaiten_erp.permissions.meter_installation_permissions",
                "Meter Commissioning": "kaiten_erp.kaiten_erp.permissions.meter_commissioning_permissions",
                "Verification Handover": "kaiten_erp.kaiten_erp.permissions.verification_handover_permissions"
            }
            
            if doc.reference_type in permission_modules:
                module_path = permission_modules[doc.reference_type]
                permission_module = frappe.get_module(module_path)
                if hasattr(permission_module, 'has_permission'):
                    ref_doc = frappe.get_doc(doc.reference_type, doc.reference_name)
                    return permission_module.has_permission(ref_doc, "read", user)
        except Exception:
            # If we can't check the referenced document, fall back to standard check
            pass
    
    return False
