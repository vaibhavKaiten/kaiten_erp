# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Execution Chain ToDo
When an execution doctype's workflow_state transitions to "Approved",
a ToDo is created for all Vendor Head users to start the next doctype
in the execution chain.

Chain order:
  Structure Mounting → Project Installation → Meter Installation
  → Meter Commissioning → Verification Handover
"""

import frappe
from frappe import _
from frappe.utils import nowdate

# Ordered chain: current doctype → next doctype to start
EXECUTION_CHAIN = {
    "Structure Mounting": "Project Installation",
    "Project Installation": "Meter Installation",
    "Meter Installation": "Meter Commissioning",
    "Meter Commissioning": "Verification Handover",
}

# Map next doctype → the field on Job File that holds its document name
CHAIN_JOB_FILE_FIELD = {
    "Project Installation": "custom_project_installation",
    "Meter Installation": "custom_meter_installation",
    "Meter Commissioning": "custom_meter_commissioning",
    "Verification Handover": "custom_verification_handover",
}


def _get_workflow_state_field(doctype: str) -> str:
    """Return the active workflow state field for a DocType."""
    try:
        fieldname = frappe.db.get_value(
            "Workflow",
            {"document_type": doctype, "is_active": 1},
            "workflow_state_field",
        )
        return fieldname or "workflow_state"
    except Exception:
        return "workflow_state"


def _value_changed(doc, fieldname: str) -> bool:
    if not fieldname:
        return False
    try:
        return bool(doc.has_value_changed(fieldname))
    except Exception:
        try:
            return doc.get_db_value(fieldname) != doc.get(fieldname)
        except Exception:
            return False


def on_update(doc, method=None):
    """
    Fired on on_update for every execution doctype in the chain.
    When workflow_state becomes "Approved", create a ToDo for all
    Vendor Head users pointing at the next document in the chain.
    """
    state_field = _get_workflow_state_field(doc.doctype)

    if not _value_changed(doc, state_field):
        return

    if doc.get(state_field) != "Approved":
        return

    next_doctype = EXECUTION_CHAIN.get(doc.doctype)
    if not next_doctype:
        return  # Verification Handover is the last step – nothing to chain

    _create_vendor_head_todos(doc, next_doctype)


def _create_vendor_head_todos(doc, next_doctype):
    # ------------------------------------------------------------------
    # Step 1: Get the Job File name directly from the execution document.
    #         Every execution doctype has either job_file or custom_job_file.
    # ------------------------------------------------------------------
    job_file_name = doc.get("job_file") or doc.get("custom_job_file")

    if not job_file_name:
        frappe.log_error(
            f"{doc.doctype} {doc.name} has no value in 'job_file' or 'custom_job_file'.",
            "Execution Chain ToDo – Missing Job File",
        )
        return

    # ------------------------------------------------------------------
    # Step 2: From the Job File, get the next doctype's document name.
    #         e.g. custom_project_installation → "PI-0001"
    # ------------------------------------------------------------------
    jf_field = CHAIN_JOB_FILE_FIELD[next_doctype]
    next_doc_name = frappe.db.get_value("Job File", job_file_name, jf_field)

    if not next_doc_name:
        frappe.log_error(
            (
                f"Job File '{job_file_name}' field '{jf_field}' is empty. "
                f"Cannot create ToDo for {next_doctype}."
            ),
            "Execution Chain ToDo – Missing Next Doc",
        )
        return

    # ------------------------------------------------------------------
    # Step 3: Get customer name for the description (from Job File).
    # ------------------------------------------------------------------
    customer = frappe.db.get_value("Job File", job_file_name, "customer") or job_file_name

    # ------------------------------------------------------------------
    # Step 4: Create one ToDo per enabled Vendor Head user.
    # ------------------------------------------------------------------
    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent as user"],
    )

    if not vendor_heads:
        frappe.log_error(
            "No users with 'Vendor Head' role found.",
            "Execution Chain ToDo – No Vendor Heads",
        )
        return

    description = _("{0} is approved. Please start {1} for {2}.").format(
        doc.doctype, next_doctype, customer
    )

    created = 0
    for vh in vendor_heads:
        user = vh.user

        if not frappe.db.get_value("User", user, "enabled"):
            continue

        # Skip if an open ToDo already exists for this user + document
        if frappe.db.exists(
            "ToDo",
            {
                "reference_type": next_doctype,
                "reference_name": next_doc_name,
                "allocated_to": user,
                "status": "Open",
            },
        ):
            continue

        try:
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "allocated_to": user,
                "description": description,
                "reference_type": next_doctype,
                "reference_name": next_doc_name,
                "role": "Vendor Head",
                "priority": "High",
                "status": "Open",
                "date": nowdate(),
            })
            todo.flags.ignore_permissions = True
            todo.insert()
            created += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Execution Chain ToDo insert failed ({doc.doctype} {doc.name} → {next_doctype} {next_doc_name})",
            )

    if created:
        frappe.db.commit()
        frappe.msgprint(
            _("ToDo assigned to {0} Vendor Head(s): Start {1}").format(created, next_doctype),
            alert=True,
            indicator="blue",
        )