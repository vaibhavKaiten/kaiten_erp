# Copyright (c) 2025, Kaiten Erp
# Quotation Workflow - Action methods for quotation lifecycle
# Status Flow: Draft → Open → Advance Pending / Revised / Rejected

import frappe
from frappe import _


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _has_sales_manager_role():
    """Check if current user has Sales Manager role"""
    return (
        frappe.db.exists(
            "Has Role", {"parent": frappe.session.user, "role": "Sales Manager"}
        )
        or "System Manager" in frappe.get_roles()
        or "Administrator" in frappe.get_roles()
    )


def _log_quotation_action(docname, action, details=""):
    """Log quotation action as comment for audit"""
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Quotation",
            "reference_name": docname,
            "content": _("{0}: {1}").format(action, details) if details else action,
        }
    ).insert(ignore_permissions=True)


# =============================================================================
# ON QUOTATION SUBMIT
# Status: Draft → Submitted
# =============================================================================


def on_quotation_submit(doc, method):
    """
    Called when Quotation is submitted
    Changes status from Draft to Submitted
    """
    if (
        doc.custom_quotation_status in ["Draft", "Quotation Open"]
        or not doc.custom_quotation_status
    ):
        frappe.db.set_value(
            "Quotation",
            doc.name,
            "custom_quotation_status",
            "Submitted",
            update_modified=False,
        )
        _log_quotation_action(
            doc.name, "Quotation Submitted", "Status changed to Submitted"
        )


# =============================================================================
# APPROVE QUOTATION
# Status: Open → Advance Pending
# =============================================================================


@frappe.whitelist()
def approve_quotation(docname, approval_method, comment=""):
    """
    Approve quotation after customer confirmation
    Status: Open → Advance Pending
    """
    if not _has_sales_manager_role():
        frappe.throw(_("Only Sales Manager can approve quotations"))

    doc = frappe.get_doc("Quotation", docname)

    # Only allow approval from Open status
    if doc.custom_quotation_status != "Open":
        frappe.throw(_("Can only approve when status is 'Open'"))

    if not approval_method:
        frappe.throw(_("Please select customer approval method"))

    doc.custom_quotation_status = "Advance Pending"
    doc.custom_acceptance_confirmed = 1
    doc.custom_customer_approval_method = approval_method
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    details = f"Approval Method: {approval_method}"
    if comment:
        details += f". Comment: {comment}"
    _log_quotation_action(docname, "Quotation Approved", details)

    return {
        "status": "success",
        "message": _("Quotation approved. Status changed to Advance Pending."),
    }


# =============================================================================
# REVISE QUOTATION
# Status: Open → Revised (locks this version, new version can be created)
# =============================================================================


@frappe.whitelist()
def revise_quotation(docname, reason):
    """
    Revise quotation - lock current version, create new
    Status: Open → Revised
    """
    if not _has_sales_manager_role():
        frappe.throw(_("Only Sales Manager can revise quotations"))

    if not reason or reason.strip() == "":
        frappe.throw(_("Revision reason is mandatory"))

    doc = frappe.get_doc("Quotation", docname)

    # Only allow revision from Open status
    if doc.custom_quotation_status != "Open":
        frappe.throw(_("Can only revise when status is 'Open'"))

    doc.custom_quotation_status = "Revised"
    doc.custom_revision_reason = reason
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    _log_quotation_action(docname, "Quotation Revised", reason)

    return {
        "status": "success",
        "message": _("Quotation marked as Revised. This version is now locked."),
    }


# =============================================================================
# CUSTOMER REJECTS
# Status: Open → Rejected (no further actions allowed)
# =============================================================================


@frappe.whitelist()
def customer_rejects(docname, reason):
    """
    Record customer rejection
    Status: Open → Rejected
    """
    if not _has_sales_manager_role():
        frappe.throw(_("Only Sales Manager can record customer rejection"))

    if not reason or reason.strip() == "":
        frappe.throw(_("Rejection reason is mandatory"))

    doc = frappe.get_doc("Quotation", docname)

    # Only allow rejection from Open status
    if doc.custom_quotation_status != "Open":
        frappe.throw(_("Can only reject when status is 'Open'"))

    doc.custom_quotation_status = "Rejected"
    doc.custom_rejection_reason = reason
    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    _log_quotation_action(docname, "Customer Rejected Quotation", reason)

    return {
        "status": "success",
        "message": _("Quotation marked as Rejected. No further actions allowed."),
    }


# =============================================================================
# RESCHEDULE FOLLOW-UP
# Updates custom_next_followup_date directly (bypasses full save to avoid
# in_words allow_on_submit restriction on submitted Quotation)
# =============================================================================


@frappe.whitelist()
def reschedule_followup(docname, new_date):
    """Update the next follow-up date and reschedule the ToDo without full doc save."""
    doc = frappe.get_doc("Quotation", docname)

    if doc.docstatus != 1:
        frappe.throw(_("Can only reschedule follow-up on a submitted Quotation."))

    frappe.db.set_value(
        "Quotation",
        docname,
        "custom_next_followup_date",
        new_date,
        update_modified=False,
    )
    doc.reload()

    if doc.get("custom_customer_acceptance") == "Yes":
        frappe.throw(_("Cannot reschedule follow-up after customer has accepted the quotation."))

    from kaiten_erp.kaiten_erp.doc_events.quotation_events import _reschedule_followup
    _reschedule_followup(doc)

    frappe.db.commit()
    return {"status": "success"}
