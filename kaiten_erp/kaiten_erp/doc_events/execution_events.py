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

    elif state == "Rejected":
        close_open_todos_by_role(doc, "Vendor Manager")
        assign_to_vendor_executives_on_rejected(doc)



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
