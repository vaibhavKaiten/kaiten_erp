# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
execution_events.py
Generic doc_events hooks for all non-Technical-Survey execution doctypes:
  Structure Mounting, Project Installation, Meter Installation,
  Meter Commissioning, Verification Handover.

Imports shared helper functions from technical_survey_events so logic
stays in one place but is wired correctly per doctype.
"""

from kaiten_erp.kaiten_erp.doc_events.technical_survey_events import (
    assign_to_vendor_managers,
    assign_to_vendor_managers_for_review,
    assign_to_internal_user,
    sync_job_file_execution_status,
    close_open_todos_by_role,
    assign_to_vendor_executives_on_in_progress,
    assign_to_vendor_heads_for_approval,
    assign_to_vendor_executives_on_rejected,
    assign_to_sales_managers_for_execution,
)


def _validate_verification_handover(doc, state):
    """
    Verification Handover-specific workflow ToDo logic.
    Sales Managers execute; Vendor Heads approve.
    """
    if state == "Assigned to Vendor":
        close_open_todos_by_role(doc, "Vendor Head")
        assign_to_sales_managers_for_execution(doc)

    elif state == "Completed":
        close_open_todos_by_role(doc, "Sales Manager")
        assign_to_vendor_heads_for_approval(doc)

    elif state == "Approved":
        close_open_todos_by_role(doc, "Vendor Head")

    # In Progress / Submitted / On Hold / Rejected: Sales Managers keep their existing ToDo


def validate(doc, method=None):
    """
    Generic validate hook for execution doctypes (NOT Technical Survey).

    Creates role-targeted ToDos on workflow state change and closes the previous role's open ToDos.
    """
    if not doc.has_value_changed("workflow_state"):
        return

    state = doc.workflow_state

    # Verification Handover has a different role flow (Sales Manager instead of Vendor Executive)
    if doc.doctype == "Verification Handover":
        _validate_verification_handover(doc, state)
        return

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
        if doc.doctype == "Structure Mounting":
            _create_structure_payment_todo(doc)

    elif state == "Rejected":
        close_open_todos_by_role(doc, "Vendor Manager")
        assign_to_vendor_executives_on_rejected(doc)



def _create_structure_payment_todo(doc):
    """
    Create a Sales Manager ToDo for the Job File owner and the Sales Order
    submitter to collect the Structure payment after Structure Mounting is approved.
    """
    import frappe

    job_file_name = doc.get("job_file") or doc.get("custom_job_file")
    if not job_file_name:
        return

    jf = frappe.db.get_value(
        "Job File", job_file_name,
        ["custom_job_file_owner", "sales_order", "first_name", "k_number"],
        as_dict=True,
    )
    if not jf:
        return

    so_name = jf.get("sales_order") or doc.get("sales_order")
    if not so_name:
        return

    customer_name = jf.get("first_name") or ""
    k_part = f" ({jf.get('k_number')})" if jf.get("k_number") else ""
    description = (
        f"Collect Structure Payment"
        f" - {customer_name}{k_part}"
        f" | {so_name}"
    )

    # Collect unique enabled users: Job File owner + SO submitter
    users = set()
    jf_owner = jf.get("custom_job_file_owner")
    if jf_owner and frappe.db.get_value("User", jf_owner, "enabled"):
        users.add(jf_owner)

    so_owner = frappe.db.get_value("Sales Order", so_name, "owner")
    if so_owner and frappe.db.get_value("User", so_owner, "enabled"):
        users.add(so_owner)

    if not users:
        return

    for user in users:
        existing = frappe.db.exists("ToDo", {
            "reference_type": "Sales Order",
            "reference_name": so_name,
            "allocated_to": user,
            "role": "Sales Manager",
            "status": "Open",
            "description": ["like", "Collect Structure Payment%"],
        })
        if existing:
            continue

        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user,
            "reference_type": "Sales Order",
            "reference_name": so_name,
            "description": description,
            "role": "Sales Manager",
            "priority": "High",
            "status": "Open",
        }).insert(ignore_permissions=True)


def on_update(doc, method=None):
    """
    Generic on_update hook for execution doctypes (NOT Technical Survey).

    Handles:
      - Sharing document with all assigned users
      - Syncing workflow_state back to Job File tracking table
    """
    import frappe
    import frappe.share

    # If a specific internal user is assigned, create their ToDo + share
    # (not applicable for Verification Handover which uses Sales Manager role-based assignment)
    if doc.doctype != "Verification Handover" and doc.get("assigned_internal_user"):
        assign_to_internal_user(doc)

    # Keep all ToDo-assigned users' share permissions up-to-date
    todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": doc.doctype,
            "reference_name": doc.name,
            "status": ["!=", "Cancelled"],
        },
        fields=["allocated_to"],
    )

    for todo in todos:
        user = todo.allocated_to

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
            try:
                frappe.share.add(
                    doc.doctype, doc.name, user=user, write=1, share=1, notify=0
                )
            except Exception as e:
                frappe.logger("kaiten_erp").error(
                    f"Failed to share {doc.doctype} {doc.name} with {user}: {str(e)}"
                )

    # Sync status to Job File execution tracking table
    try:
        sync_job_file_execution_status(doc)
    except Exception as e:
        frappe.logger("kaiten_erp").error(
            f"Failed to sync Job File execution status for {doc.doctype} {doc.name}: {str(e)}"
        )


def update_job_file_on_approval(doc, method=None):
    """
    When a Verification Handover is approved, set the linked Job File's
    workflow_state to "Completed".
    """
    import frappe

    if doc.doctype != "Verification Handover" or doc.workflow_state != "Approved":
        return

    job_file = frappe.db.get_value(
        "Job File",
        {"custom_verification_handover": doc.name},
        "name",
    )

    if not job_file:
        frappe.logger("kaiten_erp").warning(
            f"update_job_file_on_approval: No Job File linked to Verification Handover {doc.name}"
        )
        return

    current_state = frappe.db.get_value("Job File", job_file, "workflow_state")
    if current_state == "Completed":
        return

    frappe.db.set_value(
        "Job File",
        job_file,
        "workflow_state",
        "Completed",
        update_modified=False,
    )
    # Clear the cache so subsequent reads reflect the new state
    frappe.clear_document_cache("Job File", job_file)
    frappe.logger("kaiten_erp").info(
        f"Job File {job_file} workflow_state set to Completed (triggered by VH {doc.name} approval)"
    )
