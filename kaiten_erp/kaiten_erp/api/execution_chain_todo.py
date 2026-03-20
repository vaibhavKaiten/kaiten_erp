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
    """
    Create High-priority ToDo for every active Vendor Head user
    to start the next execution doctype.
    """
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
    ).format(doc.doctype, next_doctype, doc.customer)

    created = 0
    for vh in vendor_heads:
        user = vh.user
        if frappe.db.get_value("User", user, "enabled") == 0:
            continue

        # Prevent duplicate ToDos
        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": next_doctype,
                "reference_name": next_doctype,
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
                "reference_name": next_doctype,
                "priority": "High",
                "status": "Open",
                "date": nowdate(),
            }
        )
        todo.flags.ignore_permissions = True
        todo.flags.ignore_links = True
        todo.insert()
        created += 1

    if created:
        frappe.msgprint(
            _("ToDo assigned to Vendor Heads: Start {0}").format(next_doctype),
            alert=True,
            indicator="blue",
        )
