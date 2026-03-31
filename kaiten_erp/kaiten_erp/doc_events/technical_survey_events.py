# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form import assign_to
import frappe.share
from kaiten_erp.kaiten_erp.permissions.vendor_permissions import get_supplier_users


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _get_vendor_field(doc):
    """Return the name of the first vendor/supplier field found on the document, or None."""
    for field in ("assigned_vendor", "supplier", "vendor", "assigned_supplier"):
        if hasattr(doc, field):
            return field
    return None


def _get_customer_first_name(doc):
    """Return the customer's first name for display in ToDo descriptions.

    Resolution order:
    1. doc.first_name (most execution doctypes carry this directly)
    2. doc.customer Link -> Customer.customer_name (first word)
    3. linked Job File first_name
    4. linked Job File customer -> Customer.customer_name (first word)
    5. Fallback: doc.name
    """
    first_name = getattr(doc, "first_name", None)
    if first_name:
        return first_name

    customer = getattr(doc, "customer", None)
    if customer:
        cname = frappe.db.get_value("Customer", customer, "customer_name")
        if cname:
            return cname.split()[0]

    job_file_name = _get_job_file_name_from_doc(doc)
    if job_file_name:
        jf_first_name = frappe.db.get_value("Job File", job_file_name, "first_name")
        if jf_first_name:
            return jf_first_name

        jf_customer = frappe.db.get_value("Job File", job_file_name, "customer")
        if jf_customer:
            cname = frappe.db.get_value("Customer", jf_customer, "customer_name")
            if cname:
                return cname.split()[0]

    return doc.name


def _format_todo_description(doc, action_text):
    """Return a standardised ToDo description: '{first_name} - {doc.name} - {action_text}'."""
    first_name = _get_customer_first_name(doc)
    return f"{first_name} - {doc.name} - {action_text}"


def close_open_todos_by_role(doc, role):
    """Close all Open ToDos for this document that are allocated to users with the given role."""
    todos = frappe.db.sql(
        """
        SELECT DISTINCT t.name
        FROM `tabToDo` t
        INNER JOIN `tabHas Role` hr ON hr.parent = t.allocated_to AND hr.parenttype = 'User'
        WHERE t.reference_type = %(doctype)s
            AND t.reference_name = %(name)s
            AND t.status = 'Open'
            AND hr.role = %(role)s
        """,
        {"doctype": doc.doctype, "name": doc.name, "role": role},
        as_dict=True,
    )
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} open {role} ToDo(s) for {doc.doctype} {doc.name}"
        )


def _guard_approved_system_config(doc):
    """Prevent changes to system-configuration fields once the survey is Approved.

    If the workflow_state is transitioning away from Approved (e.g. to Rejected)
    the guard is skipped so the state change itself is not blocked.
    """
    prev = doc.get_doc_before_save()
    if not prev:
        return
    # Only enforce when the document was already Approved and stays Approved
    if prev.workflow_state != "Approved":
        return
    if doc.has_value_changed("workflow_state"):
        return  # state is moving away from Approved — allow

    scalar_fields = [
        "proposed_system_kw__tier", "bom_reference",
        "panel", "panel_qty_bom",
        "inverter", "inverter_qty_bom",
        "battery", "battery_qty_bom",
    ]
    for field in scalar_fields:
        if str(doc.get(field) or "") != str(prev.get(field) or ""):
            frappe.throw(
                _("System Configuration cannot be modified after the Technical Survey is Approved."),
                title=_("Approved Survey Locked"),
            )

    # Check child table changes (row count or any item_code / qty change)
    old_rows = prev.get("table_vctx") or []
    new_rows = doc.get("table_vctx") or []
    if len(old_rows) != len(new_rows):
        frappe.throw(
            _("BOM Items table cannot be modified after the Technical Survey is Approved."),
            title=_("Approved Survey Locked"),
        )
    for old_row, new_row in zip(old_rows, new_rows):
        if (old_row.item_code != new_row.item_code
                or float(old_row.qty or 0) != float(new_row.qty or 0)):
            frappe.throw(
                _("BOM Items table cannot be modified after the Technical Survey is Approved."),
                title=_("Approved Survey Locked"),
            )


def validate(doc, method=None):
    """
    Technical Survey validate hook.
    Creates role-targeted ToDos on workflow state change and closes the previous role's open ToDos.
    Prevents modification of system-configuration fields once the survey is Approved.
    """
    _guard_approved_system_config(doc)

    if not doc.has_value_changed("workflow_state"):
        return

    state = doc.workflow_state

    if state == "Assigned to Vendor":
        close_open_todos_by_role(doc, "Vendor Head")
        assign_to_vendor_managers(doc)

    elif state == "In Progress":
        close_open_todos_by_role(doc, "Vendor Manager")
        assign_to_vendor_executives_on_in_progress(doc)

    elif state == "Submitted":
        close_open_todos_by_role(doc, "Vendor Executive")
        assign_to_vendor_managers_for_review(doc)

    elif state == "Completed":
        close_open_todos_by_role(doc, "Vendor Manager")
        assign_to_vendor_heads_for_approval(doc)

    elif state == "Approved":
        close_open_todos_by_role(doc, "Vendor Head")
        link_technical_survey_to_opportunity(doc)
        assign_final_quotation_todo(doc)

    elif state == "Rejected":
        close_open_todos_by_role(doc, "Vendor Manager")
        assign_to_vendor_executives_on_rejected(doc)




def _is_completed_by_vendor_manager(doc) -> bool:
    """Return True if the transition to Completed is performed by a Vendor Manager."""

    actor = getattr(doc, "modified_by", None) or frappe.session.user
    if not actor or actor in ("Guest",):
        return False

    try:
        return "Vendor Manager" in frappe.get_roles(actor)
    except Exception:
        return False



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
            "reference_type": doc.doctype,
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
            {"user": user, "share_name": doc.name, "share_doctype": doc.doctype},
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
                    doc.doctype, doc.name, user=user, write=1, share=1, notify=0
                )
            except Exception as e:
                frappe.logger("kaiten_erp").error(
                    f"Failed to share {doc.doctype} {doc.name} with {user}: {str(e)}"
                )

    # Sync execution workflow state into parent Job File tracking table
    # We do this unconditionally on update because at this hook stage
    # has_value_changed("workflow_state") may already be False.
    try:
        sync_job_file_execution_status(doc)
    except Exception as e:
        frappe.logger("kaiten_erp").error(
            f"Failed to sync Job File execution status for {doc.doctype} {doc.name}: {str(e)}"
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

    description = _format_todo_description(doc, f"Execute {doc.doctype}")

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


def _get_job_file_name_from_doc(doc):
    """Return linked Job File name from an execution document.

    Supports both `custom_job_file` and `job_file` link fields so that
    it works across Technical Survey, Structure Mounting, Project Installation,
    Meter Installation, Meter Commissioning and Verification Handover.
    """

    job_file_name = None

    if hasattr(doc, "custom_job_file") and doc.custom_job_file:
        job_file_name = doc.custom_job_file
    elif hasattr(doc, "job_file") and doc.job_file:
        job_file_name = doc.job_file

    return job_file_name


def sync_job_file_execution_status(doc):
    """Update the Job File's execution tracking table (table_royw).

    For the given execution document (Technical Survey, Structure Mounting,
    Project Installation, Meter Installation, Meter Commissioning or
    Verification Handover), ensure there is a child row on the linked
    Job File and keep its Status in sync with the document's workflow_state.
    """

    job_file_name = _get_job_file_name_from_doc(doc)
    if not job_file_name:
        return

    if not doc.workflow_state:
        return

    # Load Job File
    job_file = frappe.get_doc("Job File", job_file_name)

    # Try to find an existing row for this execution document
    target_row = None
    for row in job_file.get("table_royw", []):
        # Exact match by stored reference
        if row.get("referrence_doctype") == doc.name:
            target_row = row
            break

    # Fallback match by stage (rows created at Job File creation time)
    if not target_row:
        for row in job_file.get("table_royw", []):
            if row.get("stage") == doc.doctype:
                target_row = row
                break

    # Create new row if none found
    if not target_row:
        target_row = job_file.append("table_royw", {})
        target_row.stage = doc.doctype

    # Always store the concrete document name for future lookups
    target_row.referrence_doctype = doc.name

    # Update status and supplier
    target_row.status = doc.workflow_state

    supplier_value = None
    if hasattr(doc, "assigned_vendor") and doc.assigned_vendor:
        supplier_value = doc.assigned_vendor
    elif hasattr(doc, "supplier") and doc.supplier:
        supplier_value = doc.supplier

    if supplier_value:
        target_row.supplier = supplier_value

    # Save without touching Job File workflow_state
    job_file.flags.ignore_permissions = True
    job_file.save(ignore_permissions=True)


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

            description = _format_todo_description(doc, f"Start {doc.doctype}")

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

    # Build list with full names for display
    user_data = [
        (user, frappe.db.get_value("User", user, "full_name") or user)
        for user in vendor_executives
    ]

    # Filter by search text if provided
    if txt:
        user_data = [
            (user, full_name)
            for user, full_name in user_data
            if txt.lower() in user.lower()
            or txt.lower() in full_name.lower()
        ]

    # Return in the format expected by Frappe's query (email, full_name)
    return [[user, full_name] for user, full_name in user_data[:page_len]]


def assign_to_vendor_executives_on_in_progress(doc):
    """Create a ToDo for the Vendor Executive when the doctype transitions to 'In Progress'.

    Targets doc.assigned_internal_user if set and has the Vendor Executive role;
    otherwise falls back to all Vendor Executives linked to the assigned supplier.
    """
    users_to_assign = []

    user = getattr(doc, "assigned_internal_user", None)
    if user and frappe.db.get_value("User", user, "enabled"):
        if frappe.db.exists("Has Role", {"parent": user, "role": "Vendor Executive"}):
            users_to_assign = [user]

    if not users_to_assign:
        vendor_field = _get_vendor_field(doc)
        assigned_vendor = getattr(doc, vendor_field, None) if vendor_field else None
        if assigned_vendor:
            users_to_assign = get_supplier_users(assigned_vendor, role="Vendor Executive")

    if not users_to_assign:
        frappe.logger("kaiten_erp").warning(
            f"No Vendor Executive found to assign In Progress ToDo for {doc.doctype} {doc.name}"
        )
        return

    description = _format_todo_description(doc, f"Execute {doc.doctype}")

    for user in users_to_assign:
        if not frappe.db.get_value("User", user, "enabled"):
            continue
        if frappe.db.exists(
            "ToDo",
            {
                "reference_type": doc.doctype,
                "reference_name": doc.name,
                "allocated_to": user,
                "status": "Open",
            },
        ):
            continue
        try:
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": doc.doctype,
                    "reference_name": doc.name,
                    "description": description,
                    "role": "Vendor Executive",
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            frappe.logger("kaiten_erp").info(
                f"Created In Progress ToDo for {user} on {doc.doctype} {doc.name}"
            )
        except Exception as e:
            frappe.log_error(
                f"Failed to create In Progress ToDo for {user} on {doc.doctype} {doc.name}: {str(e)}",
                "Execution ToDo Assignment",
            )


def assign_to_vendor_heads_for_approval(doc):
    """Create ToDos for all Vendor Heads to approve the doctype after Vendor Manager marks it Completed."""
    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent as user"],
    )
    if not vendor_heads:
        frappe.logger("kaiten_erp").warning(
            f"No Vendor Head users found. Skipping approval ToDo for {doc.doctype} {doc.name}"
        )
        return

    description = _format_todo_description(doc, f"Approve {doc.doctype}")
    created = 0

    for vh in vendor_heads:
        user = vh.user
        if not frappe.db.get_value("User", user, "enabled"):
            continue
        if frappe.db.exists(
            "ToDo",
            {
                "reference_type": doc.doctype,
                "reference_name": doc.name,
                "allocated_to": user,
                "status": "Open",
            },
        ):
            continue
        try:
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": doc.doctype,
                    "reference_name": doc.name,
                    "description": description,
                    "role": "Vendor Head",
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            created += 1
        except Exception as e:
            frappe.log_error(
                f"Failed to create Approval ToDo for {user} on {doc.doctype} {doc.name}: {str(e)}",
                "Execution ToDo Assignment",
            )

    if created:
        frappe.msgprint(
            _("Assigned to {0} Vendor Head(s) for Approval").format(created),
            alert=True,
            indicator="blue",
        )


def assign_to_sales_managers_for_execution(doc):
    """
    Create ToDos for all Sales Managers to execute the Verification Handover
    and share the document with write permission so they can edit it.
    """
    sales_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Sales Manager", "parenttype": "User"},
        fields=["parent as user"],
    )
    if not sales_managers:
        frappe.logger("kaiten_erp").warning(
            f"No Sales Manager users found. Skipping ToDo assignment for {doc.doctype} {doc.name}"
        )
        return

    description = _format_todo_description(doc, f"Execute {doc.doctype}")
    successful = []

    for sm in sales_managers:
        user = sm.user
        if not frappe.db.get_value("User", user, "enabled"):
            continue
        if frappe.db.exists(
            "ToDo",
            {
                "reference_type": doc.doctype,
                "reference_name": doc.name,
                "allocated_to": user,
                "status": "Open",
            },
        ):
            continue
        try:
            # Share document with write permission (same as Vendor Manager flow)
            if not frappe.has_permission(doctype=doc.doctype, doc=doc.name, user=user):
                frappe.share.add(
                    doc.doctype, doc.name, user=user, write=1, share=1, notify=0
                )

            assign_to.add(
                {
                    "assign_to": [user],
                    "doctype": doc.doctype,
                    "name": doc.name,
                    "description": description,
                    "priority": "Medium",
                }
            )
            user_full_name = frappe.db.get_value("User", user, "full_name") or user
            successful.append(user_full_name)
            frappe.logger("kaiten_erp").info(
                f"{doc.doctype} {doc.name} assigned to Sales Manager: {user}"
            )
        except Exception as e:
            frappe.log_error(
                f"Failed to assign {doc.doctype} {doc.name} to Sales Manager {user}: {str(e)}",
                "Verification Handover ToDo Assignment",
            )

    if successful:
        frappe.msgprint(
            _("Assigned to: {0}").format(", ".join(successful)),
            title=_("Assignment Successful"),
            indicator="green",
        )


def assign_to_vendor_executives_on_rejected(doc):
    """Create a ToDo for the Vendor Executive to rectify and resubmit after the doctype is Rejected."""
    users_to_assign = []

    user = getattr(doc, "assigned_internal_user", None)
    if user and frappe.db.get_value("User", user, "enabled"):
        if frappe.db.exists("Has Role", {"parent": user, "role": "Vendor Executive"}):
            users_to_assign = [user]

    if not users_to_assign:
        vendor_field = _get_vendor_field(doc)
        assigned_vendor = getattr(doc, vendor_field, None) if vendor_field else None
        if assigned_vendor:
            users_to_assign = get_supplier_users(assigned_vendor, role="Vendor Executive")

    if not users_to_assign:
        frappe.logger("kaiten_erp").warning(
            f"No Vendor Executive found to notify Rejected state for {doc.doctype} {doc.name}"
        )
        return

    description = _format_todo_description(doc, f"Rectify and Resubmit {doc.doctype}")

    for user in users_to_assign:
        if not frappe.db.get_value("User", user, "enabled"):
            continue
        if frappe.db.exists(
            "ToDo",
            {
                "reference_type": doc.doctype,
                "reference_name": doc.name,
                "allocated_to": user,
                "description": description,
                "status": "Open",
            },
        ):
            continue
        try:
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": doc.doctype,
                    "reference_name": doc.name,
                    "description": description,
                    "role": "Vendor Executive",
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            frappe.logger("kaiten_erp").info(
                f"Created Rejected ToDo for {user} on {doc.doctype} {doc.name}"
            )
        except Exception as e:
            frappe.log_error(
                f"Failed to create Rejected ToDo for {user} on {doc.doctype} {doc.name}: {str(e)}",
                "Execution ToDo Assignment",
            )


def assign_to_vendor_managers_for_review(doc):
    """Assign to Vendor Managers for review when the doctype is Submitted by a Vendor Executive."""
    vendor_field = _get_vendor_field(doc)
    if not vendor_field:
        frappe.logger("kaiten_erp").warning(
            f"No vendor field found in {doc.doctype}. Cannot assign review ToDo."
        )
        return

    assigned_vendor = getattr(doc, vendor_field)
    if not assigned_vendor:
        return

    vendor_managers = get_supplier_users(assigned_vendor, role="Vendor Manager")
    if not vendor_managers:
        frappe.msgprint(
            _("No Vendor Managers found for {0} to review this {1}").format(
                assigned_vendor, doc.doctype
            ),
            indicator="orange",
            alert=True,
        )
        return

    description = _format_todo_description(doc, f"Review {doc.doctype}")
    created = 0

    for user in vendor_managers:
        if not frappe.db.get_value("User", user, "enabled"):
            continue
        if frappe.db.exists(
            "ToDo",
            {
                "reference_type": doc.doctype,
                "reference_name": doc.name,
                "allocated_to": user,
                "status": "Open",
            },
        ):
            continue
        try:
            if not frappe.has_permission(doctype=doc.doctype, doc=doc.name, user=user):
                frappe.share.add(doc.doctype, doc.name, user=user, write=1, share=1, notify=0)
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": doc.doctype,
                    "reference_name": doc.name,
                    "description": description,
                    "role": "Vendor Manager",
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            created += 1
        except Exception as e:
            frappe.log_error(
                f"Failed to create Review ToDo for {user} on {doc.doctype} {doc.name}: {str(e)}",
                "Execution ToDo Assignment",
            )

    if created:
        frappe.msgprint(
            _("Review assigned to {0} Vendor Manager(s)").format(created),
            alert=True,
            indicator="blue",
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


def link_technical_survey_to_opportunity(doc):
    """
    Set Opportunity.custom_technical_survey when a Technical Survey is approved.
    - Uses Opportunity as the anchor to avoid reverse lookups.
    - Does not overwrite existing links (idempotent).
    """
    opportunity_name = doc.get("custom_opportunity")

    # Fallback: find opportunity linked to the same Job File
    if not opportunity_name and doc.get("custom_job_file"):
        opportunity_name = frappe.db.get_value(
            "Opportunity", {"custom_job_file": doc.custom_job_file}, "name"
        )

    if not opportunity_name:
        frappe.logger("kaiten_erp").warning(
            "link_technical_survey_to_opportunity: no opportunity found for Technical Survey %s", doc.name
        )
        return

    # Ensure Opportunity has the expected custom field; fail silently otherwise
    if not frappe.db.has_column("Opportunity", "custom_technical_survey"):
        frappe.throw(
            _("Opportunity.custom_technical_survey is missing; skipping link for Technical Survey {0}").format(doc.name)
        )
        return

    existing_link = frappe.db.get_value(
        "Opportunity", opportunity_name, "custom_technical_survey"
    )
    if existing_link:
        # Already linked; do not overwrite
        return

    frappe.db.set_value(
        "Opportunity",
        opportunity_name,
        "custom_technical_survey",
        doc.name,
        update_modified=False,
    )
    frappe.logger("kaiten_erp").info(
        "Linked Technical Survey %s to Opportunity %s", doc.name, opportunity_name
    )


def assign_final_quotation_todo(doc):
    """
    After Technical Survey approval, assign a ToDo to the initiating Sales Manager
    (stored on the Job File) to create the Final Quotation from the same Opportunity.
    - Prevents duplicates.
    - Idempotent across re-saves.
    """
    opportunity_name = doc.get("custom_opportunity")

    # Fallback: find opportunity linked to the same Job File
    if not opportunity_name and doc.get("custom_job_file"):
        opportunity_name = frappe.db.get_value(
            "Opportunity", {"custom_job_file": doc.custom_job_file}, "name"
        )

    if not opportunity_name:
        frappe.logger("kaiten_erp").warning(
            "assign_final_quotation_todo: no opportunity found for Technical Survey %s", doc.name
        )
        return

    # Fetch Job File from Opportunity (anchor)
    job_file_name = frappe.db.get_value(
        "Opportunity", opportunity_name, "custom_job_file"
    )
    if not job_file_name and doc.get("custom_job_file"):
        job_file_name = doc.custom_job_file
    if not job_file_name:
        return

    # Sales Manager who initiated the Job File — check both possible field names
    sales_manager = None
    for owner_field in ("custom_job_file_owner", "custom_job_file_ownerr"):
        if frappe.db.has_column("Job File", owner_field):
            sales_manager = frappe.db.get_value("Job File", job_file_name, owner_field)
            if sales_manager:
                break

    # Ensure user is enabled and still a Sales Manager
    if not frappe.db.get_value("User", sales_manager, "enabled"):
        return
    has_role = frappe.db.exists(
        "Has Role", {"parent": sales_manager, "role": "Sales Manager"}
    )
    if not has_role:
        return

    description = _(
        "Technical Survey {0} approved. Please create Final Quotation from Opportunity {1}."
    ).format(doc.name, opportunity_name)

    existing_todo = frappe.db.exists(
        "ToDo",
        {
            "reference_type": "Opportunity",
            "reference_name": opportunity_name,
            "allocated_to": sales_manager,
            "description": description,
            "status": "Open",
        },
    )
    if existing_todo:
        return

    todo = frappe.get_doc(
        {
            "doctype": "ToDo",
            "allocated_to": sales_manager,
            "reference_type": "Opportunity",
            "reference_name": opportunity_name,
            "description": description,
            "priority": "High",
            "status": "Open",
        }
    )
    todo.flags.ignore_permissions = True
    todo.insert()
    frappe.logger("kaiten_erp").info(
        "Created Final Quotation ToDo for %s on Opportunity %s", sales_manager, opportunity_name
    )
