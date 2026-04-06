# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, nowdate


# ---------------------------------------------------------------------------
# Doc event hooks
# ---------------------------------------------------------------------------

def validate(doc, method=None):
    _sync_links_from_opportunity(doc)
    _fill_item_name_and_uom(doc)
    _set_default_followup_date(doc)

    if doc.get("custom_quotation_stage") == "Final Approved":
        _validate_final_approved_requirements(doc)
        _ensure_single_commercial_item(doc)
        _lock_final_approved_item_structure(doc)


def on_submit(doc, method=None):
    """Create a follow-up ToDo when a Quotation is submitted."""
    if doc.status in ("Ordered", "Lost"):
        return
    if not doc.get("custom_next_followup_date"):
        return
    _create_followup_todo(doc)


def on_update_after_submit(doc, method=None):
    """
    Handles two post-submit changes:
    1. Next Follow-up Date changed → reschedule ToDo.
    2. Status changed to Lost → close all open Quotation ToDos.
    """
    before = doc.get_doc_before_save()
    if not before:
        return

    status_changed_to_lost = (
        before.get("status") != "Lost" and doc.status == "Lost"
    )
    if status_changed_to_lost:
        close_quotation_todos(doc.name)
        return

    if doc.status in ("Ordered", "Lost"):
        return

    prev_date = str(before.get("custom_next_followup_date") or "")
    curr_date = str(doc.get("custom_next_followup_date") or "")
    if curr_date and curr_date != prev_date:
        _reschedule_followup(doc)


# ---------------------------------------------------------------------------
# Follow-up helpers
# ---------------------------------------------------------------------------

def _set_default_followup_date(doc):
    """Default Next Follow-up Date to today + 4 days for new Quotations."""
    if doc.is_new() and not doc.get("custom_next_followup_date"):
        doc.custom_next_followup_date = add_days(nowdate(), 4)


def _get_followup_assignee(doc):
    """
    Resolve the user to assign the follow-up ToDo to.

    Priority:
    1. custom_job_file_owner on the linked Job File (Sales Manager who owns the deal)
    2. doc.owner (Quotation submitter) as fallback
    """
    job_file = doc.get("custom_job_file")
    if job_file:
        owner = frappe.db.get_value("Job File", job_file, "custom_job_file_owner")
        if owner and frappe.db.get_value("User", owner, "enabled"):
            return owner
    return doc.owner


def _create_followup_todo(doc):
    """Create an Open ToDo for the Quotation's Sales Manager / job file owner."""
    customer = doc.get("customer_name") or doc.get("party_name") or doc.get("title") or doc.name
    grand_total = doc.get("grand_total") or 0
    description = f"Follow-up: {customer} | {doc.name} | ₹{grand_total:,.0f}"
    assigned_to = _get_followup_assignee(doc)

    todo = frappe.get_doc({
        "doctype": "ToDo",
        "allocated_to": assigned_to,
        "reference_type": "Quotation",
        "reference_name": doc.name,
        "description": description,
        "date": doc.custom_next_followup_date,
        "status": "Open",
    })
    todo.flags.ignore_permissions = True
    todo.insert()


def _reschedule_followup(doc):
    """Close existing open ToDos, create a new one, update tracking fields."""
    close_quotation_todos(doc.name)
    _create_followup_todo(doc)

    current_count = frappe.db.get_value("Quotation", doc.name, "custom_followup_count") or 0
    frappe.db.set_value(
        "Quotation",
        doc.name,
        {
            "custom_last_followup_date": nowdate(),
            "custom_followup_count": int(current_count) + 1,
        },
        update_modified=False,
    )


def close_quotation_todos(quotation_name):
    """Close all Open ToDos linked to a given Quotation."""
    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Quotation",
            "reference_name": quotation_name,
            "status": "Open",
        },
        fields=["name"],
    )
    for todo in todos:
        frappe.db.set_value("ToDo", todo.name, "status", "Closed", update_modified=False)


def _fill_item_name_and_uom(doc):
    """Auto-populate item_name and UOM from Item master for every row that has item_code."""
    for item in doc.get("items") or []:
        if not item.item_code:
            continue
        if item.item_name and item.uom:
            continue
        item_data = frappe.db.get_value(
            "Item",
            item.item_code,
            ["item_name", "stock_uom"],
            as_dict=True,
        )
        if not item_data:
            continue
        if not item.item_name:
            item.item_name = item_data.item_name
        if not item.uom:
            item.uom = item_data.stock_uom


def _sync_links_from_opportunity(doc):
    if not doc.opportunity:
        return

    fields_to_fetch = ["custom_job_file"]
    has_ts_column = frappe.db.has_column("Opportunity", "custom_technical_survey")
    if has_ts_column:
        fields_to_fetch.append("custom_technical_survey")

    opportunity = frappe.db.get_value(
        "Opportunity",
        doc.opportunity,
        fields_to_fetch,
        as_dict=True,
    )

    if opportunity and opportunity.get("custom_job_file") and not doc.get("custom_job_file"):
        doc.custom_job_file = opportunity.custom_job_file

    if hasattr(doc, "custom_opportunity_link"):
        doc.custom_opportunity_link = doc.opportunity

    # Phase 2: inherit approved Technical Survey link from Opportunity (idempotent)
    if has_ts_column and opportunity and opportunity.get("custom_technical_survey") and not doc.get(
        "custom_technical_survey"
    ):
        doc.custom_technical_survey = opportunity.custom_technical_survey

    # Default stage to Final Approved when a Technical Survey is present (do not override Phase 1)
    if (
        doc.is_new()
        and not doc.get("custom_quotation_stage")
        and doc.get("custom_technical_survey")
    ):
        doc.custom_quotation_stage = "Final Approved"


def _validate_final_approved_requirements(doc):
    if not doc.opportunity:
        frappe.throw(_("Final Approved Quotation must be linked to an Opportunity."))

    if not doc.get("custom_technical_survey"):
        frappe.throw(
            _("Approved Technical Survey is mandatory for Final Approved Quotation.")
        )

    technical_survey = frappe.get_doc("Technical Survey", doc.custom_technical_survey)

    if technical_survey.get("workflow_state") != "Approved":
        frappe.throw(
            _("Technical Survey {0} must be in Approved state.").format(
                technical_survey.name
            )
        )

    if not technical_survey.get("custom_opportunity"):
        frappe.throw(
            _("Technical Survey {0} must be linked to an Opportunity.").format(
                technical_survey.name
            )
        )

    if technical_survey.custom_opportunity != doc.opportunity:
        frappe.throw(
            _(
                "Technical Survey {0} is linked to Opportunity {1}, not {2}."
            ).format(technical_survey.name, technical_survey.custom_opportunity, doc.opportunity)
        )

    if technical_survey.get("custom_job_file") and not doc.get("custom_job_file"):
        doc.custom_job_file = technical_survey.custom_job_file

    if technical_survey.get("customer") and doc.get("party_name"):
        if (
            doc.get("quotation_to") == "Customer"
            and technical_survey.customer != doc.party_name
        ):
            frappe.throw(
                _(
                    "Technical Survey customer {0} does not match Quotation customer {1}."
                ).format(technical_survey.customer, doc.party_name)
            )


def _ensure_single_commercial_item(doc):
    opportunity = frappe.db.get_value(
        "Opportunity",
        doc.opportunity,
        ["custom_proposed_system", "opportunity_amount"],
        as_dict=True,
    )

    proposed_system = (opportunity or {}).get("custom_proposed_system")
    if not proposed_system:
        frappe.throw(
            _("Opportunity {0} is missing Proposed System.").format(doc.opportunity)
        )

    if not doc.items:
        doc.append(
            "items",
            {
                "item_code": proposed_system,
                "qty": 1,
                "rate": (opportunity or {}).get("opportunity_amount") or 0,
            },
        )
        return

    if len(doc.items) != 1:
        frappe.throw(
            _(
                "Final Approved Quotation can contain only one commercial item (Proposed System)."
            )
        )

    item = doc.items[0]
    if item.item_code != proposed_system:
        frappe.throw(
            _(
                "Final Approved Quotation item must be the Opportunity Proposed System: {0}."
            ).format(proposed_system)
        )

    if not item.qty:
        item.qty = 1


def on_submit(doc, method=None):
    """Close open Sales Manager ToDos on the linked Opportunity when a Quotation is submitted.

    Two open Sales Manager ToDos may exist for the Opportunity:
    1. Created at Job File Initiated state — to create the initial quotation.
    2. Created at Technical Survey Approved state — to create the Final Quotation.

    Both are closed here when the Quotation is submitted, since submitting a Quotation
    means the Sales Manager has completed the relevant task.
    """
    opportunity_name = doc.opportunity
    if not opportunity_name:
        return

    todos = frappe.db.sql(
        """
        SELECT DISTINCT t.name
        FROM `tabToDo` t
        INNER JOIN `tabHas Role` hr ON hr.parent = t.allocated_to AND hr.parenttype = 'User'
        WHERE t.reference_type = 'Opportunity'
            AND t.reference_name = %(opportunity)s
            AND t.status = 'Open'
            AND hr.role = 'Sales Manager'
        """,
        {"opportunity": opportunity_name},
        as_dict=True,
    )
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} Sales Manager ToDo(s) for Opportunity {opportunity_name} on Quotation {doc.name} submit"
        )


def _lock_final_approved_item_structure(doc):
    if doc.is_new() or doc.amended_from:
        return

    previous_doc = doc.get_doc_before_save()
    if not previous_doc:
        return

    if previous_doc.get("custom_quotation_stage") != "Final Approved":
        return

    previous_items = previous_doc.get("items") or []
    current_items = doc.get("items") or []

    if len(previous_items) != len(current_items):
        frappe.throw(
            _(
                "Item add/remove is not allowed for Final Approved Quotation unless amended."
            )
        )

    for index, old_item in enumerate(previous_items):
        new_item = current_items[index]
        if (
            old_item.get("item_code") != new_item.get("item_code")
            or float(old_item.get("qty") or 0) != float(new_item.get("qty") or 0)
            or old_item.get("uom") != new_item.get("uom")
        ):
            frappe.throw(
                _(
                    "Item code, quantity, and UOM are locked for Final Approved Quotation unless amended."
                )
            )
