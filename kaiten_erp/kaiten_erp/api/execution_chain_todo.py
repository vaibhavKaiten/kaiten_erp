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

EXECUTION_CHAIN = {
    "Structure Mounting": "Project Installation",
    "Project Installation": "Meter Installation",
    "Meter Installation": "Meter Commissioning",
    "Meter Commissioning": "Verification Handover",
}

CHAIN_JOB_FILE_FIELD = {
    "Project Installation": "custom_project_installation",
    "Meter Installation": "custom_meter_installation",
    "Meter Commissioning": "custom_meter_commissioning",
    "Verification Handover": "custom_verification_handover",
}


def _get_workflow_state_field(doctype: str) -> str:
    try:
        fieldname = frappe.db.get_value(
            "Workflow",
            {"document_type": doctype, "is_active": 1},
            "workflow_state_field",
        )
        return fieldname or "workflow_state"
    except Exception:
        return "workflow_state"


def on_update(doc, method=None):
    state_field = _get_workflow_state_field(doc.doctype)
    current_state = doc.get(state_field)

    try:
        changed = bool(doc.has_value_changed(state_field))
    except Exception:
        changed = True

    if not changed or current_state != "Approved":
        return

    next_doctype = EXECUTION_CHAIN.get(doc.doctype)
    if not next_doctype:
        return

    # Structure Mounting Approved → only create PI todo if Structure milestone is Paid
    if doc.doctype == "Structure Mounting" and next_doctype == "Project Installation":
        if not _structure_milestone_is_paid(doc):
            # PI todo will be created later by _sf_check_delivery_after_structure_paid
            # (triggered when AM marks the Structure milestone as Paid on the Sales Order)
            return

    # Self Finance intercept: MC Approved → SM "Collect Final Payment" instead of VH todo
    if doc.doctype == "Meter Commissioning" and next_doctype == "Verification Handover":
        if _sf_intercept_mc_approved(doc):
            return

    _create_vendor_head_todos(doc, next_doctype)


def _create_vendor_head_todos(doc, next_doctype):
    # Get Job File name from the execution document
    job_file_name = doc.get("job_file") or doc.get("custom_job_file")
    if not job_file_name:
        frappe.log_error(
            f"{doc.doctype} {doc.name} has no value in 'job_file' or 'custom_job_file'.",
            "Execution Chain ToDo"
        )
        frappe.msgprint(
            _("Warning: Could not find Job File linked to {0}. ToDo not created.").format(doc.name),
            indicator="orange",
            alert=True,
        )
        return

    # Get the next doctype's document name from the Job File
    jf_field = CHAIN_JOB_FILE_FIELD[next_doctype]
    next_doc_name = frappe.db.get_value("Job File", job_file_name, jf_field)
    if not next_doc_name:
        frappe.log_error(
            f"Job File '{job_file_name}' has no value in field '{jf_field}'. Cannot create ToDo for {next_doctype}.",
            "Execution Chain ToDo"
        )
        frappe.msgprint(
            _("Warning: {0} document not found on Job File. ToDo not created.").format(next_doctype),
            indicator="orange",
            alert=True,
        )
        return

    # Get customer first name from Job File for the description
    customer_first_name = frappe.db.get_value("Job File", job_file_name, "first_name") or job_file_name

    # Get all enabled Vendor Head users
    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent as user"],
    )
    if not vendor_heads:
        frappe.log_error(
            "No users with 'Vendor Head' role found. ToDo not created.",
            "Execution Chain ToDo"
        )
        frappe.msgprint(
            _("Warning: No Vendor Head users found. ToDo not created."),
            indicator="orange",
            alert=True,
        )
        return

    description = f"{customer_first_name} - {next_doc_name} - Initiate {next_doctype}"

    created = 0
    for vh in vendor_heads:
        user = vh.user

        if not frappe.db.get_value("User", user, "enabled"):
            continue

        if frappe.db.exists("ToDo", {
            "reference_type": next_doctype,
            "reference_name": next_doc_name,
            "allocated_to": user,
            "status": "Open",
        }):
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
            frappe.db.commit()
            created += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Execution Chain ToDo – Failed to create ToDo for {user} ({doc.doctype} {doc.name} → {next_doctype})"
            )

    if created:
        frappe.msgprint(
            _("ToDo assigned to {0} Vendor Head(s): Start {1}").format(created, next_doctype),
            alert=True,
            indicator="blue",
        )


# ---------------------------------------------------------------------------
# Structure Mounting: gate PI todo on Structure milestone being Paid
# ---------------------------------------------------------------------------

def _structure_milestone_is_paid(doc):
    """
    Return True if the Sales Order linked to this Structure Mounting doc has its
    'Structure' payment milestone marked as 'Paid'.

    Falls through (returns True) when no payment plan / no Structure row exists,
    so orders without a payment plan are unaffected and proceed normally.
    """
    job_file_name = doc.get("job_file") or doc.get("custom_job_file")
    if not job_file_name:
        return True  # Can't check — let normal chain proceed

    so_name = frappe.db.get_value("Job File", job_file_name, "sales_order")
    if not so_name:
        return True  # No SO linked — let normal chain proceed

    milestones = frappe.db.get_all(
        "Payment Milestone",
        filters={"parent": so_name, "parenttype": "Sales Order", "milestone": "Structure"},
        fields=["status"],
        limit=1,
    )
    if not milestones:
        return True  # No Structure milestone row — proceed normally

    return (milestones[0].status or "Pending") == "Paid"


# ---------------------------------------------------------------------------
# Self Finance: MC Approved → SM "Collect Final Payment" (instead of VH todo)
# ---------------------------------------------------------------------------

def _sf_intercept_mc_approved(doc):
    """
    If the Sales Order linked to this Meter Commissioning is Self Finance,
    create a SM 'Collect Final Payment' todo for the Job File owner instead
    of a VH 'Initiate Verification Handover' todo.

    Returns True if intercepted (Self Finance), False otherwise.
    """
    job_file_name = doc.get("job_file") or doc.get("custom_job_file")
    if not job_file_name:
        return False

    so_name = frappe.db.get_value("Job File", job_file_name, "sales_order")
    if not so_name:
        return False

    finance_type = frappe.db.get_value("Sales Order", so_name, "custom_finance_type")
    if (finance_type or "").strip() != "Self Finance":
        return False

    # Self Finance — create SM "Collect Final Payment" todo
    jf_data = frappe.db.get_value(
        "Job File", job_file_name,
        ["custom_job_file_owner", "first_name", "k_number"],
        as_dict=True,
    )
    if not jf_data:
        return False

    owner = jf_data.get("custom_job_file_owner")
    if not owner or not frappe.db.get_value("User", owner, "enabled"):
        return False

    customer_first_name = jf_data.get("first_name") or ""
    k_part = f" ({jf_data.get('k_number')})" if jf_data.get("k_number") else ""
    description = (
        f"Collect Final Payment"
        f" - {customer_first_name}{k_part}"
        f" | {so_name}"
    )

    if frappe.db.exists("ToDo", {
        "reference_type": "Sales Order",
        "reference_name": so_name,
        "allocated_to": owner,
        "role": "Sales Manager",
        "status": "Open",
        "description": ["like", "Collect Final Payment%"],
    }):
        return True  # Already exists, still intercepted

    frappe.get_doc({
        "doctype": "ToDo",
        "allocated_to": owner,
        "reference_type": "Sales Order",
        "reference_name": so_name,
        "description": description,
        "role": "Sales Manager",
        "priority": "High",
        "status": "Open",
        "date": nowdate(),
    }).insert(ignore_permissions=True)

    return True