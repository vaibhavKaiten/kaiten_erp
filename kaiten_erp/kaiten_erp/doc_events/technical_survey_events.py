# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form import assign_to
import frappe.share
from kaiten_erp.kaiten_erp.permissions.vendor_permissions import get_supplier_users


def validate(doc, method=None):
    """
    Technical Survey validate hook - Auto-assign to Vendor Managers when workflow_state changes to 'Assigned to Vendor'
    Also creates Quotation when workflow_state changes to 'Approved'
    """

    # Check if workflow_state field has changed to "Assigned to Vendor"
    if (
        doc.has_value_changed("workflow_state")
        and doc.workflow_state == "Assigned to Vendor"
    ):
        assign_to_vendor_managers(doc)

    # Check if workflow_state field has changed to "Submitted"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Submitted":
        assign_to_vendor_managers_for_review(doc)

    # Check if workflow_state field has changed to "Approved"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Approved":
        assign_to_sales_managers(doc)

    # Check if workflow_state field has changed to "Completed"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Completed":
        assign_to_execution_managers_for_technical_survey(doc)


def assign_to_execution_managers_for_technical_survey(doc):
    """
    Assign Technical Survey to all users with Execution Manager role
    Creates ToDo for each Execution Manager when Technical Survey is completed
    """
    # Get all users with Execution Manager role
    execution_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Execution Manager", "parenttype": "User"},
        fields=["parent"],
    )

    if not execution_managers:
        frappe.msgprint(
            _(
                f"No Execution Managers found to assign this Technical Survey for execution"
            ),
            indicator="orange",
            alert=True,
        )
        return

    assigned_count = 0
    errors = []

    for manager in execution_managers:
        user = manager.parent

        # Check if user is enabled
        user_enabled = frappe.db.get_value("User", user, "enabled")
        if not user_enabled:
            continue

        # Check if ToDo already exists for this user and document
        existing_todo = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Technical Survey",
                "reference_name": doc.name,
                "allocated_to": user,
                "status": "Open",
            },
        )

        if existing_todo:
            continue

        try:
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": "Technical Survey",
                    "reference_name": doc.name,
                    "description": f"Technical Survey {doc.name} is completed. Please take execution action.",
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            frappe.db.commit()
            assigned_count += 1
        except Exception as e:
            error_msg = f"Failed to create ToDo for {user}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(error_msg, "Technical Survey ToDo Assignment Error")

    if assigned_count > 0:
        frappe.msgprint(
            _(
                f"Technical Survey assigned to {assigned_count} Execution Manager(s) for execution action"
            ),
            indicator="green",
            alert=True,
        )

    if errors:
        frappe.msgprint(
            _(f"Some assignments failed. Check Error Log for details."),
            indicator="orange",
            alert=True,
        )


def on_update(doc, method=None):
    """
    Technical Survey on_update hook - Auto-share with write permission when someone is assigned
    """
    # Handle assigned_internal_user field - create ToDo and share document
    if doc.assigned_internal_user:
        assign_to_internal_user(doc)

    # Get all active ToDo assignments for this document
    todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Technical Survey",
            "reference_name": doc.name,
            "status": ["!=", "Cancelled"],
        },
        fields=["allocated_to"],
    )

    # Ensure all assigned users have write permission
    for todo in todos:
        user = todo.allocated_to

        # Check if user already has share access
        existing_share = frappe.db.exists(
            "DocShare",
            {"user": user, "share_name": doc.name, "share_doctype": "Technical Survey"},
        )

        if existing_share:
            # Update existing share to ensure write permission
            frappe.db.set_value(
                "DocShare",
                existing_share,
                {"write": 1, "share": 1},
                update_modified=False,
            )
        else:
            # Create new share with write permission
            try:
                frappe.share.add(
                    "Technical Survey", doc.name, user=user, write=1, share=1, notify=0
                )
            except Exception as e:
                frappe.logger("kaiten_erp").error(
                    f"Failed to share Technical Survey {doc.name} with {user}: {str(e)}"
                )


def assign_to_internal_user(doc):
    """
    Generic function to assign any doctype to the user specified in assigned_internal_user field
    Creates a ToDo task and shares the document with write permission
    """

    # Detect internal user field dynamically
    user_field = None
    possible_user_fields = ["assigned_internal_user", "internal_user", "assigned_to"]

    for field in possible_user_fields:
        if hasattr(doc, field):
            user_field = field
            break

    if not user_field:
        return  # No internal user field in this doctype

    user = getattr(doc, user_field)

    if not user:
        return

    # Check if this user is already assigned via ToDo
    existing_todo = frappe.db.exists(
        "ToDo",
        {
            "reference_type": doc.doctype,
            "reference_name": doc.name,
            "allocated_to": user,
            "status": ["!=", "Cancelled"],
        },
    )

    if existing_todo:
        frappe.logger("kaiten_erp").debug(
            f"User {user} already assigned to {doc.doctype} {doc.name}"
        )
        return

    # Build description dynamically
    vendor = (
        getattr(doc, "assigned_vendor", None)
        or getattr(doc, "supplier", None)
        or "supplier"
    )

    description = f"{doc.doctype} for {vendor}"

    # Create ToDo assignment
    try:
        assign_to.add(
            {
                "doctype": doc.doctype,
                "name": doc.name,
                "assign_to": [user],
                "description": description,
                "priority": "Medium",
                "notify": 1,
            }
        )

        frappe.logger("kaiten_erp").info(f"Assigned {doc.doctype} {doc.name} to {user}")
    except Exception as e:
        frappe.logger("kaiten_erp").error(
            f"Failed to assign {doc.doctype} {doc.name} to {user}: {str(e)}"
        )

    # Share document with write permission
    try:
        existing_share = frappe.db.exists(
            "DocShare",
            {"user": user, "share_name": doc.name, "share_doctype": doc.doctype},
        )

        if existing_share:
            frappe.db.set_value(
                "DocShare",
                existing_share,
                {"write": 1, "share": 1},
                update_modified=False,
            )
        else:
            frappe.share.add(
                doc.doctype, doc.name, user=user, write=1, share=1, notify=0
            )

        frappe.logger("kaiten_erp").info(f"Shared {doc.doctype} {doc.name} with {user}")
    except Exception as e:
        frappe.logger("kaiten_erp").error(
            f"Failed to share {doc.doctype} {doc.name} with {user}: {str(e)}"
        )


def assign_to_vendor_managers(doc):
    """
    Generic function to assign any execution doctype to all Vendor Managers
    of the assigned supplier with duplicate prevention
    """

    # Dynamically detect vendor field
    vendor_field = None

    possible_vendor_fields = [
        "assigned_vendor",
        "supplier",
        "vendor",
        "assigned_supplier",
    ]

    for field in possible_vendor_fields:
        if hasattr(doc, field):
            vendor_field = field
            break

    if not vendor_field:
        frappe.throw(
            _(
                f"No vendor field found in {doc.doctype}. Cannot assign to Vendor Managers."
            ),
            title=_("Configuration Error"),
        )

    assigned_vendor = getattr(doc, vendor_field)

    if not assigned_vendor:
        frappe.throw(
            _(
                f"{vendor_field.replace('_', ' ').title()} is required before initiating {doc.doctype}"
            ),
            title=_("Validation Error"),
        )

    # Get all Vendor Managers for this supplier
    vendor_managers = get_supplier_users(assigned_vendor, role="Vendor Manager")

    if not vendor_managers:
        frappe.throw(
            _("No Vendor Manager found for supplier: {0}").format(assigned_vendor),
            title=_("Validation Error"),
        )

    # Check for existing ToDos dynamically
    existing_todos = frappe.db.sql(
        """
        SELECT DISTINCT allocated_to
        FROM `tabToDo`
        WHERE reference_type = %(doctype)s
            AND reference_name = %(doc_name)s
            AND status != 'Cancelled'
        """,
        {"doctype": doc.doctype, "doc_name": doc.name},
        as_dict=True,
    )

    existing_users = [todo.allocated_to for todo in existing_todos]

    users_to_assign = [user for user in vendor_managers if user not in existing_users]

    if not users_to_assign and existing_users:
        frappe.msgprint(
            _(f"ToDo is already created and assigned for {doc.doctype}"),
            title=_("Information"),
            indicator="blue",
        )
        return

    successful_assignments = []
    failed_assignments = []

    for user in users_to_assign:
        try:
            user_full_name = frappe.db.get_value("User", user, "full_name") or user

            # Dynamic description without assuming first_name field
            display_name = getattr(doc, "first_name", None) or doc.name

            description = _(f"Complete {doc.doctype} - {display_name}")

            # Dynamic permission check
            if not frappe.has_permission(doctype=doc.doctype, doc=doc.name, user=user):
                frappe.share.add(
                    doc.doctype,
                    doc.name,
                    user=user,
                    write=1,
                    share=1,
                    notify=0,
                )

                frappe.logger("kaiten_erp").info(
                    f"Shared {doc.doctype} {doc.name} with full permissions to: {user}"
                )

            # Dynamic assign_to call
            assign_to.add(
                {
                    "assign_to": [user],
                    "doctype": doc.doctype,
                    "name": doc.name,
                    "description": description,
                    "priority": "Medium",
                }
            )

            successful_assignments.append(user_full_name)

            frappe.logger("kaiten_erp").info(
                f"{doc.doctype} {doc.name} assigned to Vendor Manager: {user}"
            )

        except Exception as e:
            failed_assignments.append(
                {
                    "user": user,
                    "user_full_name": frappe.db.get_value("User", user, "full_name")
                    or user,
                    "error": str(e),
                }
            )

            frappe.logger("kaiten_erp").error(
                f"Failed to assign {doc.doctype} {doc.name} to {user}: {str(e)}"
            )

    if successful_assignments:
        success_msg = _("Successfully assigned to: {0}").format(
            ", ".join(successful_assignments)
        )
        frappe.msgprint(
            success_msg, title=_("Assignment Successful"), indicator="green"
        )

    if failed_assignments:
        error_details = "<br>".join(
            [f"• {f['user_full_name']}: {f['error']}" for f in failed_assignments]
        )

        frappe.flags.failed_todo_assignments = [f["user"] for f in failed_assignments]
        frappe.flags.survey_name = doc.name

        error_msg = _(
            f"""
            <b>Failed to assign {doc.doctype} to the following users:</b><br><br>
            {error_details}<br><br>
            <i>Click 'Retry' to attempt creating ToDos again for these users.</i>
            """
        )

        frappe.msgprint(
            error_msg,
            title=_("Partial Assignment Failure"),
            indicator="orange",
            primary_action={
                "label": _("Retry"),
                "client_action": "kaiten_erp.technical_survey.retry_todo_assignments",
            },
        )


@frappe.whitelist()
def retry_failed_todo_assignments(survey_name, failed_users):
    """
    Retry creating ToDo assignments for users who failed in the initial attempt

    Args:
        survey_name (str): Technical Survey document name
        failed_users (str or list): JSON string or list of user emails to retry

    Returns:
        dict: Success status and message
    """
    import json

    # Parse failed_users if it's a JSON string
    if isinstance(failed_users, str):
        failed_users = json.loads(failed_users)

    if not isinstance(failed_users, list):
        failed_users = [failed_users]

    # Get the Technical Survey document
    doc = frappe.get_doc("Technical Survey", survey_name)

    successful_retries = []
    still_failed = []

    for user in failed_users:
        try:
            # Check if ToDo was created since last attempt
            existing_todo = frappe.db.exists(
                "ToDo",
                {
                    "reference_type": "Technical Survey",
                    "reference_name": survey_name,
                    "allocated_to": user,
                    "status": ["!=", "Cancelled"],
                },
            )

            if existing_todo:
                user_full_name = frappe.db.get_value("User", user, "full_name") or user
                successful_retries.append(user_full_name)
                continue

            # Check if user has permission, share if not
            if not frappe.has_permission(
                doctype="Technical Survey", doc=survey_name, user=user
            ):
                # Share document with full permissions
                frappe.share.add(
                    "Technical Survey",
                    survey_name,
                    user=user,
                    write=1,
                    share=1,
                    notify=0,
                )

            # Attempt to create ToDo again
            user_full_name = frappe.db.get_value("User", user, "full_name") or user
            description = _("Complete Technical Survey for {0}").format(
                doc.first_name or doc.name
            )

            assign_to.add(
                {
                    "assign_to": [user],
                    "doctype": "Technical Survey",
                    "name": doc.name,
                    "description": description,
                    "priority": "Medium",
                }
            )

            successful_retries.append(user_full_name)

        except Exception as e:
            user_full_name = frappe.db.get_value("User", user, "full_name") or user
            still_failed.append({"user": user_full_name, "error": str(e)})

    # Return results
    if still_failed:
        error_list = ", ".join([f["user"] for f in still_failed])
        return {
            "success": False,
            "message": _("Still failed to assign to: {0}").format(error_list),
            "successful_retries": successful_retries,
            "still_failed": still_failed,
        }
    else:
        return {
            "success": True,
            "message": _("Successfully assigned to all users: {0}").format(
                ", ".join(successful_retries)
            ),
            "successful_retries": successful_retries,
        }


@frappe.whitelist()
def ensure_assigned_users_have_access(docname):
    """
    Ensure all users assigned to a Technical Survey have write access
    Called after manual assignment to immediately grant permissions

    Args:
        docname: Technical Survey document name
    """
    # Get all active ToDo assignments
    todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Technical Survey",
            "reference_name": docname,
            "status": ["!=", "Cancelled"],
        },
        fields=["allocated_to"],
    )

    for todo in todos:
        user = todo.allocated_to

        try:
            # Check if share exists
            existing_share = frappe.db.get_value(
                "DocShare",
                {
                    "user": user,
                    "share_name": docname,
                    "share_doctype": "Technical Survey",
                },
                ["name", "write", "share"],
                as_dict=True,
            )

            if existing_share:
                # Update if write or share is not enabled
                if not existing_share.write or not existing_share.share:
                    frappe.db.set_value(
                        "DocShare",
                        existing_share.name,
                        {"write": 1, "share": 1},
                        update_modified=False,
                    )
                    frappe.db.commit()
                    frappe.logger("kaiten_erp").info(
                        f"Updated share permissions for {user} on Technical Survey {docname}"
                    )
            else:
                # Create new share
                frappe.share.add(
                    "Technical Survey", docname, user=user, write=1, share=1, notify=0
                )
                frappe.db.commit()
                frappe.logger("kaiten_erp").info(
                    f"Created share with write permission for {user} on Technical Survey {docname}"
                )
        except Exception as e:
            frappe.logger("kaiten_erp").error(
                f"Failed to ensure access for {user} on Technical Survey {docname}: {str(e)}"
            )

    return {"success": True}


@frappe.whitelist()
def get_vendor_executives_list(supplier):
    """
    Get list of Vendor Executives for a supplier with their details

    Args:
        supplier: Supplier company name

    Returns:
        list: List of dicts with email and full_name
    """
    if not supplier:
        return []

    # Get Vendor Executives for this supplier
    vendor_executives = get_supplier_users(supplier, role="Vendor Executive")

    # Get user details
    user_list = []
    for user in vendor_executives:
        full_name = frappe.db.get_value("User", user, "full_name") or user
        user_list.append({"email": user, "full_name": full_name})

    return user_list


@frappe.whitelist()
def get_vendor_users_for_assignment(
    doctype, txt, searchfield, start, page_len, filters
):
    """
    Filter users in assignment dropdown to show only Vendor Executives
    from the supplier in assigned_vendor field

    Args:
        doctype: The doctype being filtered (User)
        txt: Search text entered by user
        searchfield: Field to search in
        start: Pagination start
        page_len: Number of results per page
        filters: Additional filters including docname and doctype_name

    Returns:
        list: List of tuples containing user emails
    """
    if not filters or not filters.get("docname"):
        return []

    # Get the doctype name from filters, default to Technical Survey for backward compatibility
    doctype_name = filters.get("doctype_name", "Technical Survey")

    # Get the document
    try:
        doc = frappe.get_doc(doctype_name, filters.get("docname"))
    except Exception:
        return []

    # If no assigned_vendor, return empty
    if not doc.assigned_vendor:
        return []

    # Get Vendor Executives for this supplier
    vendor_executives = get_supplier_users(doc.assigned_vendor, role="Vendor Executive")

    if not vendor_executives:
        return []

    # Filter by search text if provided
    if txt:
        vendor_executives = [
            user
            for user in vendor_executives
            if txt.lower() in user.lower()
            or txt.lower()
            in (frappe.db.get_value("User", user, "full_name") or "").lower()
        ]

    # Return in the format expected by Frappe's query
    return [[user] for user in vendor_executives[:page_len]]


def assign_to_vendor_managers_for_review(doc):
    """
    Assign Technical Survey to all Vendor Managers for review when submitted
    """
    assigned_vendor = doc.assigned_vendor
    if not assigned_vendor:
        return

    # Get all Vendor Managers for this supplier
    vendor_managers = get_supplier_users(assigned_vendor, role="Vendor Manager")

    if not vendor_managers:
        frappe.msgprint(
            _("No Vendor Managers found for {0} to review this survey").format(
                assigned_vendor
            ),
            indicator="orange",
            alert=True,
        )
        return

    for user in vendor_managers:
        # Check if user is enabled (optional, but good practice)
        if not frappe.db.get_value("User", user, "enabled"):
            continue

        description = _(
            "Technical Survey {0} has been Submitted. Please review."
        ).format(doc.name)

        # Check existing ToDo
        existing_todo = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Technical Survey",
                "reference_name": doc.name,
                "allocated_to": user,
                "description": description,
                "status": "Open",
            },
        )

        if existing_todo:
            continue

        try:
            # Ensure permissions
            if not frappe.has_permission(doctype=doc.doctype, doc=doc.name, user=user):
                frappe.share.add(
                    doc.doctype, doc.name, user=user, write=1, share=1, notify=0
                )

            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": "Technical Survey",
                    "reference_name": doc.name,
                    "description": description,
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            frappe.logger("kaiten_erp").info(
                f"Created Review ToDo for {user} on {doc.name}"
            )

        except Exception as e:
            frappe.log_error(
                f"Failed to create Review ToDo for {user}: {str(e)}",
                "Technical Survey Review Assignment",
            )


def assign_to_sales_managers(doc):
    """
    Assign ToDo to Sales Managers regarding the linked Opportunity when Approved
    """
    # 1. Find linked Sales Order
    sales_order_name = frappe.db.get_value(
        "Sales Order", {"custom_technical_survey": doc.name}, "name"
    )

    if not sales_order_name:
        frappe.msgprint(
            _(
                "No linked Sales Order found for Technical Survey {0}. Cannot assign to Sales Manager."
            ).format(doc.name),
            indicator="orange",
            alert=True,
        )
        return

    # 2. Get Opportunity from Sales Order
    opportunity_name = frappe.db.get_value(
        "Sales Order", sales_order_name, "opportunity"
    )

    if not opportunity_name:
        frappe.msgprint(
            _(
                "No linked Opportunity found for Sales Order {0}. Cannot assign to Sales Manager."
            ).format(sales_order_name),
            indicator="orange",
            alert=True,
        )
        return

    # 3. Get Sales Managers
    sales_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Sales Manager", "parenttype": "User"},
        fields=["parent"],
    )

    if not sales_managers:
        frappe.msgprint(
            _("No Sales Managers found in the system."), indicator="orange", alert=True
        )
        return

    count = 0
    for manager in sales_managers:
        user = manager.parent
        if not frappe.db.get_value("User", user, "enabled"):
            continue

        description = _(
            "Technical Survey {0} has been Approved. Please take action on this Opportunity."
        ).format(doc.name)

        # Check existing ToDo
        existing_todo = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Opportunity",
                "reference_name": opportunity_name,
                "allocated_to": user,
                "description": description,
                "status": "Open",
            },
        )

        if existing_todo:
            continue

        try:
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": "Opportunity",
                    "reference_name": opportunity_name,
                    "description": description,
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            count += 1

        except Exception as e:
            frappe.log_error(
                f"Failed to create Sales Manager ToDo for {user}: {str(e)}",
                "Technical Survey Approved Assignment",
            )

    if count > 0:
        frappe.msgprint(
            _(
                "Created ToDos for {0} Sales Managers to take action on Opportunity {1}"
            ).format(count, opportunity_name),
            indicator="green",
            alert=True,
        )
