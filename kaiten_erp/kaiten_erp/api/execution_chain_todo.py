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

# Map next doctype → Job File field that holds its document name
CHAIN_JOB_FILE_FIELD = {
    "Project Installation": "custom_project_installation",
    "Meter Installation": "custom_meter_installation",
    "Meter Commissioning": "custom_meter_commissioning",
    "Verification Handover": "custom_verification_handover",
}



def _get_job_file_link_field(doctype):
    """Return link fieldname in doctype that points to Job File, if any."""
    meta = frappe.get_meta(doctype)
    for field in meta.fields:
        if field.fieldtype == "Link" and field.options == "Job File":
            return field.fieldname
    return None


def _get_next_doc_name_from_job_file(job_file_name, next_doctype):
    """Find next doctype doc name using Job File linkage."""
    next_link_field = _get_job_file_link_field(next_doctype)
    if next_link_field:
        return frappe.db.get_value(next_doctype, {next_link_field: job_file_name}, "name")

    # Fallback to Job File pointer fields if next doctype has no Job File link field.
    jf_field = CHAIN_JOB_FILE_FIELD.get(next_doctype)
    if jf_field and frappe.db.has_column("Job File", jf_field):
        return frappe.db.get_value("Job File", job_file_name, jf_field)

    return None


def on_update(doc, method=None):
    """
    Hook called on on_update for execution doctypes.
    When workflow_state transitions to "Approved", create a ToDo
    for Vendor Head users to start the next doctype in the chain.
    """
    if not doc.has_value_changed("workflow_state"):
        return

    if doc.workflow_state != "Approved":
        return

    next_doctype = EXECUTION_CHAIN.get(doc.doctype)
    if not next_doctype:
        return

    _create_vendor_head_todos(doc, next_doctype)


def _create_vendor_head_todos(doc, next_doctype):
    # Resolve Job File from current execution doc via dynamic link field.
    current_link_field = _get_job_file_link_field(doc.doctype)
    job_file_name = doc.get(current_link_field) if current_link_field else None

    # Backward compatibility for instances where fieldnames vary.
    if not job_file_name:
        job_file_name = doc.get("job_file") or doc.get("custom_job_file")

    if not job_file_name:
        frappe.log_error(
            f"Could not find Job File link on {doc.doctype} {doc.name}",
            "Execution Chain ToDo",
        )
        return

    next_doc_name = _get_next_doc_name_from_job_file(job_file_name, next_doctype)

    if not next_doc_name:
        frappe.log_error(
            f"Could not find {next_doctype} document on Job File {job_file_name}",
            "Execution Chain ToDo",
        )
        return

    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent as user"],
    )

    if not vendor_heads:
        frappe.log_error(
            "No users with Vendor Head role found for execution chain ToDo",
            "Execution Chain ToDo",
        )
        return

    description = _(
        "{0} is approved please start {1} for {2}"
    ).format(doc.doctype, next_doctype, doc.customer or "Customer")

    created = 0
    for vh in vendor_heads:
        user = vh.user
        if frappe.db.get_value("User", user, "enabled") == 0:
            continue

        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": next_doctype,
                "reference_name": next_doc_name,   # actual doc name e.g. "PI-0001"
                "allocated_to": user,
                "status": "Open",
                "description": ["like", f"%start {next_doctype} for {doc.customer}%"],
            },
        )
        if existing:
            continue

        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": user,
                "description": description,
                "reference_type": next_doctype,
                "reference_name": next_doc_name,   # actual doc name
                "priority": "High",
                "status": "Open",
                "date": nowdate(),
            }
        )
        todo.flags.ignore_permissions = True
        todo.insert()
        created += 1

    if created:
        frappe.msgprint(
            _("ToDo assigned to Vendor Heads: Start {0}").format(next_doctype),
            alert=True,
            indicator="blue",
        )