# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """
    1. In ALL workflows: replace "Execution Manager" with "Vendor Head"
       in both workflow states (allow_edit) and transitions (allowed).
    2. In the "Updated Verification Handover" workflow only: additionally
       replace "Vendor Manager" and "Vendor Executive" with "Sales Manager".

    Idempotent — skips rows that already have the target role.
    """

    # ── 1. Replace Execution Manager → Vendor Head in all workflows ───────
    _replace_role_in_all_workflows("Execution Manager", "Vendor Head")

    # ── 2. Replace Vendor Manager/Executive → Sales Manager in VH workflow ─
    vh_workflow = "Updated Verification Handover"
    if frappe.db.exists("Workflow", vh_workflow):
        _replace_role_in_workflow(vh_workflow, "Vendor Manager", "Sales Manager")
        _replace_role_in_workflow(vh_workflow, "Vendor Executive", "Sales Manager")

    frappe.db.commit()
    frappe.clear_cache()


def _replace_role_in_all_workflows(old_role, new_role):
    """Replace old_role with new_role across every workflow's states and transitions."""
    # Workflow states
    frappe.db.sql(
        """
        UPDATE `tabWorkflow Document State`
        SET allow_edit = %s
        WHERE allow_edit = %s
        """,
        (new_role, old_role),
    )

    # Workflow transitions
    frappe.db.sql(
        """
        UPDATE `tabWorkflow Transition`
        SET allowed = %s
        WHERE allowed = %s
        """,
        (new_role, old_role),
    )


def _replace_role_in_workflow(workflow_name, old_role, new_role):
    """Replace old_role with new_role in a single workflow's states and transitions."""
    # Workflow states
    frappe.db.sql(
        """
        UPDATE `tabWorkflow Document State`
        SET allow_edit = %s
        WHERE allow_edit = %s AND parent = %s
        """,
        (new_role, old_role, workflow_name),
    )

    # Workflow transitions
    frappe.db.sql(
        """
        UPDATE `tabWorkflow Transition`
        SET allowed = %s
        WHERE allowed = %s AND parent = %s
        """,
        (new_role, old_role, workflow_name),
    )
