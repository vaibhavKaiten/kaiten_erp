# Copyright (c) 2025, KaitenSoftware
# Execution Workflow Controller
# Enforces hard locks and execution sequence for Kaiten Erp

import frappe
from frappe import _
from frappe.utils import flt, nowdate


# Execution sequence stages in order
EXECUTION_STAGES = [
    "Technical Survey",
    "Structure Mounting",
    "Project Installation",
    "Meter Installation",
    "Meter Commissioning",
    "Verification Handover",
]

# Status that qualifies as "approved/completed"
APPROVED_STATUSES = ["Approved"]


def is_admin_user():
    """
    Check if current user is System Manager/Administrator
    Admins can bypass all workflow restrictions
    """
    return (
        frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()
    )


def check_advance_payment_gate(job_file):
    """
    Check if advance payment has been verified for the job

    Returns:
        dict: {
            "verified": bool,
            "quotation": str or None,
            "advance_amount": float,
            "payment_entry": str or None,
            "message": str
        }
    """
    # Admin bypass
    if is_admin_user():
        return {
            "verified": True,
            "bypass": True,
            "message": _("Admin bypass - advance payment check skipped"),
        }

    jf = frappe.get_doc("Job File", job_file)

    # Get linked quotation
    quotation = jf.quotation
    if not quotation:
        return {
            "verified": False,
            "quotation": None,
            "advance_amount": 0,
            "payment_entry": None,
            "message": _(
                "No quotation linked to Job File. Cannot verify advance payment."
            ),
        }

    # Check quotation status
    qt = frappe.get_doc("Quotation", quotation)

    # Check if quotation has custom_quotation_status = "Advance Approved"
    quotation_status = qt.get("custom_quotation_status") or ""

    if quotation_status == "Advance Approved":
        # Find the linked payment entry
        payment_entry = frappe.db.get_value(
            "Payment Entry", {"custom_quotation": quotation, "docstatus": 1}, "name"
        )

        return {
            "verified": True,
            "quotation": quotation,
            "advance_amount": get_advance_amount_received(quotation),
            "payment_entry": payment_entry,
            "message": _("Advance payment verified"),
        }

    # Not verified
    return {
        "verified": False,
        "quotation": quotation,
        "advance_amount": 0,
        "payment_entry": None,
        "message": _("Advance payment not yet received. Quotation status: {0}").format(
            quotation_status or "Pending"
        ),
    }


def get_advance_amount_received(quotation):
    """
    Get total advance amount received for a quotation
    """
    total = frappe.db.sql(
        """
        SELECT COALESCE(SUM(paid_amount), 0) as total
        FROM `tabPayment Entry`
        WHERE custom_quotation = %s AND docstatus = 1
    """,
        quotation,
        as_dict=True,
    )

    return flt(total[0].total) if total else 0


def get_previous_stage(current_stage):
    """
    Get the previous execution stage
    """
    if current_stage not in EXECUTION_STAGES:
        return None

    idx = EXECUTION_STAGES.index(current_stage)
    if idx == 0:
        return None  # Technical Survey has no previous stage

    return EXECUTION_STAGES[idx - 1]


def get_next_stage(current_stage):
    """
    Get the next execution stage
    """
    if current_stage not in EXECUTION_STAGES:
        return None

    idx = EXECUTION_STAGES.index(current_stage)
    if idx >= len(EXECUTION_STAGES) - 1:
        return None  # Verification Handover is last

    return EXECUTION_STAGES[idx + 1]


def check_previous_stage_approved(job_file, current_stage):
    """
    Check if the previous execution stage is approved

    Returns:
        dict: {
            "approved": bool,
            "previous_stage": str,
            "previous_doc": str or None,
            "message": str
        }
    """
    # Admin bypass
    if is_admin_user():
        return {
            "approved": True,
            "bypass": True,
            "message": _("Admin bypass - previous stage check skipped"),
        }

    previous_stage = get_previous_stage(current_stage)

    if not previous_stage:
        # Technical Survey - no previous stage needed
        return {
            "approved": True,
            "previous_stage": None,
            "previous_doc": None,
            "message": _("No previous stage required"),
        }

    # Map stage name to doctype
    doctype_map = {
        "Technical Survey": "Technical Survey",
        "Structure Mounting": "Structure Mounting",
        "Project Installation": "Project Installation",
        "Meter Installation": "Meter Installation",
        "Meter Commissioning": "Meter Commissioning",
        "Verification Handover": "Verification Handover",
    }

    previous_doctype = doctype_map.get(previous_stage)

    if not previous_doctype:
        return {
            "approved": False,
            "previous_stage": previous_stage,
            "previous_doc": None,
            "message": _("Unknown stage: {0}").format(previous_stage),
        }

    # Find the previous stage document
    previous_doc = frappe.db.get_value(
        previous_doctype, {"job_file": job_file}, ["name", "status"], as_dict=True
    )

    if not previous_doc:
        return {
            "approved": False,
            "previous_stage": previous_stage,
            "previous_doc": None,
            "message": _("{0} not yet created for this Job File").format(
                previous_stage
            ),
        }

    if previous_doc.status in APPROVED_STATUSES:
        return {
            "approved": True,
            "previous_stage": previous_stage,
            "previous_doc": previous_doc.name,
            "message": _("{0} is approved").format(previous_stage),
        }

    return {
        "approved": False,
        "previous_stage": previous_stage,
        "previous_doc": previous_doc.name,
        "message": _("{0} ({1}) is not yet approved. Current status: {2}").format(
            previous_stage, previous_doc.name, previous_doc.status
        ),
    }


def can_start_stage(job_file, stage):
    """
    Comprehensive check if a stage can be started

    Returns:
        dict: {
            "allowed": bool,
            "blocks": list of blocking issues,
            "message": str
        }
    """
    blocks = []

    # Check previous stage
    prev_check = check_previous_stage_approved(job_file, stage)
    if not prev_check.get("approved") and not prev_check.get("bypass"):
        blocks.append(
            {
                "type": "previous_stage",
                "stage": prev_check.get("previous_stage"),
                "message": prev_check.get("message"),
            }
        )

    # For Structure Mounting onwards, check advance payment
    if stage != "Technical Survey":
        payment_check = check_advance_payment_gate(job_file)
        if not payment_check.get("verified") and not payment_check.get("bypass"):
            blocks.append(
                {"type": "advance_payment", "message": payment_check.get("message")}
            )

    if blocks:
        return {
            "allowed": False,
            "blocks": blocks,
            "message": _("Cannot start {0}. {1} blocking issue(s) found.").format(
                stage, len(blocks)
            ),
        }

    return {
        "allowed": True,
        "blocks": [],
        "message": _("{0} can be started").format(stage),
    }


@frappe.whitelist()
def validate_stage_start(job_file, stage):
    """
    API to validate if a stage can be started
    Called from client-side before creating/starting a stage
    """
    return can_start_stage(job_file, stage)


def get_execution_status_summary(job_file):
    """
    Get a summary of all execution stages for a job
    """
    stages = []

    doctype_map = {
        "Technical Survey": "Technical Survey",
        "Structure Mounting": "Structure Mounting",
        "Project Installation": "Project Installation",
        "Meter Installation": "Meter Installation",
        "Meter Commissioning": "Meter Commissioning",
        "Verification Handover": "Verification Handover",
    }

    for stage in EXECUTION_STAGES:
        doctype = doctype_map.get(stage)
        doc = frappe.db.get_value(
            doctype, {"job_file": job_file}, ["name", "status"], as_dict=True
        )

        stages.append(
            {
                "stage": stage,
                "doctype": doctype,
                "doc_name": doc.name if doc else None,
                "status": doc.status if doc else "Not Created",
                "completed": doc and doc.status in APPROVED_STATUSES,
            }
        )

    return stages


def get_vendor_from_previous_stages(job_file):
    """
    Get the assigned vendor from previous execution stages
    Used to enforce same vendor across all stages
    """
    # Check Technical Survey first
    ts_vendor = frappe.db.get_value(
        "Technical Survey", {"job_file": job_file}, "assigned_vendor"
    )

    # Vendor is a Supplier company
    if ts_vendor and frappe.db.exists("Supplier", {"name": ts_vendor, "disabled": 0}):
        return ts_vendor

    # Check other stages
    for stage in [
        "Structure Mounting",
        "Project Installation",
        "Meter Installation",
        "Meter Commissioning",
        "Verification Handover",
    ]:
        vendor = frappe.db.get_value(
            stage.replace(" ", ""),  # Remove spaces for doctype name
            {"job_file": job_file},
            "assigned_vendor",
        )
        # Vendor is a Supplier company
        if vendor and frappe.db.exists("Supplier", {"name": vendor, "disabled": 0}):
            return vendor

    return None


def auto_assign_vendor(doc, method=None):
    """
    Auto-assign vendor from previous stages to maintain continuity
    Called on validate for execution doctypes
    """
    # Check if vendor already assigned
    if doc.get("assigned_vendor"):
        # Validate existing vendor
        existing_vendor = doc.get("assigned_vendor")
        if not frappe.db.exists("Supplier", {"name": existing_vendor, "disabled": 0}):
            # Invalid vendor assigned - clear it
            frappe.logger().warning(
                f"Clearing invalid vendor '{existing_vendor}' from {doc.doctype} {doc.name or 'new'}"
            )
            doc.assigned_vendor = None
        else:
            return  # Valid vendor already assigned

    job_file = doc.get("job_file")
    if not job_file:
        return

    previous_vendor = get_vendor_from_previous_stages(job_file)
    if previous_vendor:
        # Double-check it's a valid Supplier before assigning
        if frappe.db.exists("Supplier", {"name": previous_vendor, "disabled": 0}):
            doc.assigned_vendor = previous_vendor
        else:
            frappe.logger().warning(
                f"Skipping vendor assignment: '{previous_vendor}' is not a valid Supplier for {doc.doctype} {doc.name or 'new'}"
            )


def validate_execution_stage(doc, method=None):
    """
    Validate execution stage on insert/validate
    Called via doc_events hooks
    """
    # Get doctype name cleaned for stage check
    doctype_to_stage = {
        "Technical Survey": "Technical Survey",
        "Structure Mounting": "Structure Mounting",
        "Project Installation": "Project Installation",
        "Meter Installation": "Meter Installation",
        "Meter Commissioning": "Meter Commissioning",
        "Verification Handover": "Verification Handover",
    }

    stage = doctype_to_stage.get(doc.doctype)
    if not stage:
        return

    job_file = doc.get("job_file")
    if not job_file:
        return

    # Only validate on new documents or status changes
    if doc.is_new():
        check = can_start_stage(job_file, stage)
        if not check.get("allowed"):
            blocks = check.get("blocks", [])
            messages = [b.get("message") for b in blocks]
            frappe.throw(
                _("Cannot create {0}:<br>- {1}").format(stage, "<br>- ".join(messages)),
                title=_("Workflow Lock"),
            )
