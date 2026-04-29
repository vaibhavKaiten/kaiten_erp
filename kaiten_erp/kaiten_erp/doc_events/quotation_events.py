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
    _apply_negotiated_amount_from_job_file(doc)

    from kaiten_erp.kaiten_erp.doc_events.tax_bifurcation import fill_tax_bifurcation
    fill_tax_bifurcation(doc)

    if doc.get("custom_quotation_stage") == "Final Approved":
        _validate_final_approved_requirements(doc)
        _ensure_single_commercial_item(doc)
        _lock_final_approved_item_structure(doc)


def after_insert(doc, method=None):
    """Link this Quotation to the Job File's initial or final quotation field on first save."""
    _link_quotation_to_job_file(doc)


def on_update(doc, method=None):
    """Sync customer-acceptance ToDos on draft saves."""
    if doc.docstatus != 0:
        return
    _sync_customer_acceptance_todos(doc)


def on_update_after_submit(doc, method=None):
    """
    Handles post-submit changes:
    1. Status is Lost → close all open ToDos (follow-up, initiate TS, create SO).
    2. Next Follow-up Date changed → reschedule follow-up ToDo.
    3. customer_acceptance changed → open/close the right next-step ToDos.

    NOTE: ERPNext's declare_enquiry_lost uses db_set("status", "Lost") before
    calling save(), so get_doc_before_save() already sees "Lost" in the DB.
    We therefore check doc.status == "Lost" directly rather than a before/after
    comparison — all close helpers are idempotent (already-closed todos are skipped).
    """
    if doc.status == "Lost":
        _close_vendor_head_initiate_ts_todos(doc)
        _close_sales_order_todos(doc)
        close_quotation_todos(doc.name)
        return

    if doc.status == "Ordered":
        return

    before = doc.get_doc_before_save()
    if not before:
        return

    prev_date = str(before.get("custom_next_followup_date") or "")
    curr_date = str(doc.get("custom_next_followup_date") or "")
    if curr_date and curr_date != prev_date:
        _reschedule_followup(doc)

    prev_acceptance = str(before.get("custom_customer_acceptance") or "")
    curr_acceptance = str(doc.get("custom_customer_acceptance") or "")
    if curr_acceptance != prev_acceptance:
        _sync_customer_acceptance_todos(doc)


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
    if not doc.get("custom_next_followup_date"):
        return

    assigned_to = _get_followup_assignee(doc)

    # Duplicate guard — targeted to follow-up todos so "Create Sales Order" todos don't block
    if frappe.db.exists("ToDo", {
        "reference_type": "Quotation",
        "reference_name": doc.name,
        "allocated_to": assigned_to,
        "role": "Sales Manager",
        "status": "Open",
        "description": ["like", "%Follow-up:%"],
    }):
        return

    customer = doc.get("customer_name") or doc.get("party_name") or doc.get("title") or doc.name
    grand_total = doc.get("grand_total") or 0
    description = f"Follow-up: {customer} | {doc.name} | ₹{grand_total:,.0f}"

    todo = frappe.get_doc({
        "doctype": "ToDo",
        "allocated_to": assigned_to,
        "reference_type": "Quotation",
        "reference_name": doc.name,
        "description": description,
        "role": "Sales Manager",
        "date": doc.custom_next_followup_date,
        "status": "Open",
    })
    todo.flags.ignore_permissions = True
    todo.insert()


def _reschedule_followup(doc):
    """Close existing follow-up ToDos, create a new one, update tracking fields.

    Only acts when customer acceptance is not yet confirmed — once the customer
    has accepted (acceptance = 'Yes') there is nothing to follow up on.
    """
    # Close only follow-up todos; leave "Create Sales Order" or other open todos intact
    _close_followup_todos(doc.name)

    if doc.get("custom_customer_acceptance") == "Yes":
        # Acceptance already given — no new follow-up todo needed
        return

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


def _close_followup_todos(quotation_name):
    """Close open Follow-up ToDos for a Quotation (without touching other open ToDos)."""
    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Quotation",
            "reference_name": quotation_name,
            "status": "Open",
            "description": ["like", "%Follow-up:%"],
        },
        fields=["name"],
    )
    for todo in todos:
        frappe.db.set_value("ToDo", todo.name, "status", "Closed", update_modified=False)

    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} Follow-up ToDo(s) for Quotation {quotation_name}"
        )


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
    if opportunity_name:
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

    _sync_customer_acceptance_todos(doc)


# ---------------------------------------------------------------------------
# Customer Acceptance ToDo helpers
# ---------------------------------------------------------------------------

def _sync_customer_acceptance_todos(doc):
    """Create or close acceptance-driven ToDos based on the Quotation value."""
    if doc.get("custom_customer_acceptance") == "Yes":
        # Customer accepted — close the pending follow-up ToDo and open the next step
        _close_followup_todos(doc.name)
        if not doc.get("custom_technical_survey"):
            _create_vendor_head_initiate_ts_todo(doc)
        else:
            _create_sales_order_todo(doc)
        return

    # Acceptance is NOT Yes — close acceptance-driven todos
    _close_vendor_head_initiate_ts_todos(doc)
    _close_sales_order_todos(doc)

    # For submitted, active quotations recreate the follow-up ToDo so the Sales Manager
    # keeps following up (covers: never accepted yet, acceptance reverted from Yes)
    if doc.docstatus == 1 and doc.status not in ("Ordered", "Lost"):
        _create_followup_todo(doc)


def _get_technical_survey_for_acceptance(doc):
    """Resolve the Technical Survey linked to the accepted Quotation."""
    technical_survey = doc.get("custom_technical_survey")
    if technical_survey:
        return technical_survey

    job_file_name = doc.get("custom_job_file")
    if not job_file_name:
        return None

    return frappe.db.get_value("Job File", job_file_name, "custom_technical_survey")


def _create_vendor_head_initiate_ts_todo(doc):
    """Create ToDo for Vendor Head users to initiate Technical Survey.

    Closes automatically when TS transitions to 'Assigned to Vendor'
    and also when Quotation customer acceptance changes away from Yes.
    """
    ts_name = _get_technical_survey_for_acceptance(doc)
    if not ts_name:
        return

    customer_name = doc.get("customer_name") or doc.get("party_name") or doc.name

    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent"],
    )

    for head in vendor_heads:
        user = head.parent
        if not frappe.db.get_value("User", user, "enabled"):
            continue

        # Duplicate guard
        existing = frappe.db.exists("ToDo", {
            "reference_type": "Technical Survey",
            "reference_name": ts_name,
            "allocated_to": user,
            "role": "Vendor Head",
            "status": "Open",
            "description": ["like", "%Initiate Technical Survey%"],
        })
        if existing:
            continue

       
        description = f"Initiate Technical Survey for {customer_name} - {ts_name}"
        from kaiten_erp.kaiten_erp.api.execution_chain_todo import get_execution_todo_due_date
        due_date = get_execution_todo_due_date("Technical Survey", ts_name)

        todo = frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user,
            "reference_type": "Technical Survey",
            "reference_name": ts_name,
            "role": "Vendor Head",
            "description": description,
            "priority": "High",
            "status": "Open",
            "date": due_date,
        })
        todo.flags.ignore_permissions = True
        todo.insert()

    frappe.logger("kaiten_erp").info(
        f"Created Vendor Head 'Initiate TS' ToDo(s) for Technical Survey {ts_name} from Quotation {doc.name}"
    )


def _close_vendor_head_initiate_ts_todos(doc):
    """Close open Vendor Head 'Initiate Technical Survey' ToDos for this Quotation's TS."""
    ts_name = _get_technical_survey_for_acceptance(doc)
    if not ts_name:
        return

    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Technical Survey",
            "reference_name": ts_name,
            "role": "Vendor Head",
            "status": "Open",
            "description": ["like", "%Initiate Technical Survey%"],
        },
        fields=["name"],
    )
    for todo in todos:
        frappe.db.set_value("ToDo", todo.name, "status", "Closed", update_modified=False)

    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} Vendor Head 'Initiate TS' ToDo(s) for Technical Survey {ts_name} from Quotation {doc.name}"
        )


def _create_sales_order_todo(doc):
    """Case 2: Create ToDo for the Sales Manager who submitted the Quotation
    to create a Sales Order.

    Closes automatically when the Sales Order is submitted
    (handled in sales_order_events._close_create_sales_order_todos).
    """
    assigned_to = _get_followup_assignee(doc)

    if not frappe.db.get_value("User", assigned_to, "enabled"):
        return

    customer_name = doc.get("customer_name") or doc.get("party_name") or doc.name
    grand_total = doc.get("grand_total") or 0

    # Duplicate guard
    existing = frappe.db.exists("ToDo", {
        "reference_type": "Quotation",
        "reference_name": doc.name,
        "allocated_to": assigned_to,
        "role": "Sales Manager",
        "status": "Open",
        "description": ["like", "%Create Sales Order%"],
    })
    if existing:
        return

    description = f"Create Sales Order for {customer_name} | {doc.name} | ₹{grand_total:,.0f}"

    todo = frappe.get_doc({
        "doctype": "ToDo",
        "allocated_to": assigned_to,
        "reference_type": "Quotation",
        "reference_name": doc.name,
        "role": "Sales Manager",
        "description": description,
        "priority": "High",
        "status": "Open",
    })
    todo.flags.ignore_permissions = True
    todo.insert()
    frappe.logger("kaiten_erp").info(
        f"Created 'Create Sales Order' ToDo for {assigned_to} on Quotation {doc.name}"
    )


def _close_sales_order_todos(doc):
    """Close open 'Create Sales Order' ToDos for this Quotation."""
    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Quotation",
            "reference_name": doc.name,
            "role": "Sales Manager",
            "status": "Open",
            "description": ["like", "%Create Sales Order%"],
        },
        fields=["name"],
    )
    for todo in todos:
        frappe.db.set_value("ToDo", todo.name, "status", "Closed", update_modified=False)

    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} 'Create Sales Order' ToDo(s) for Quotation {doc.name}"
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


# ---------------------------------------------------------------------------
# Job File quotation link helpers
# ---------------------------------------------------------------------------

def _apply_negotiated_amount_from_job_file(doc):
    """
    Fetch negotiated_amount from the linked Job File and set it as the rate
    (and recalculate amount) on all items.

    Applies to both initial quotations (no TS) and final quotations (TS present)
    as long as a Job File is linked.

    Skipped when:
    - No custom_job_file linked
    - negotiated_amount is zero / unset on Job File
    - doc is Final Approved and not new (item structure is locked separately)
    """
    if not doc.get("custom_job_file"):
        return
    # Final Approved has its own item lock — skip to avoid conflict
    if doc.get("custom_quotation_stage") == "Final Approved" and not doc.is_new():
        return

    negotiated_amount = frappe.db.get_value(
        "Job File", doc.custom_job_file, "negotiated_amount"
    )
    if not negotiated_amount:
        return

    from frappe.utils import flt
    for item in doc.get("items") or []:
        item.rate = flt(negotiated_amount)
        item.amount = flt(item.qty or 1) * flt(negotiated_amount)


def _link_quotation_to_job_file(doc):
    """
    Populate either custom_initial_quotation or custom_final_quotation on the
    linked Job File, depending on whether the Quotation has a Technical Survey.

    - custom_technical_survey is empty  → custom_initial_quotation (if blank)
    - custom_technical_survey is filled → custom_final_quotation   (if blank)

    The field is only set when it is currently empty to avoid overwriting an
    already-linked quotation.
    """
    job_file_name = doc.get("custom_job_file")
    if not job_file_name:
        return

    if not frappe.db.exists("Job File", job_file_name):
        return

    has_ts = bool(doc.get("custom_technical_survey"))
    field = "custom_final_quotation" if has_ts else "custom_initial_quotation"

    existing = frappe.db.get_value("Job File", job_file_name, field)
    if existing:
        return

    frappe.db.set_value(
        "Job File",
        job_file_name,
        field,
        doc.name,
        update_modified=False,
    )
    frappe.logger("kaiten_erp").info(
        f"Linked Quotation {doc.name} to Job File {job_file_name}.{field}"
    )


# ---------------------------------------------------------------------------
# Sales Order creation guard
# ---------------------------------------------------------------------------

@frappe.whitelist()
def make_sales_order(source_name, target_doc=None):
    """Override ERPNext's make_sales_order to block creation when Technical Survey is missing."""
    custom_ts = frappe.db.get_value("Quotation", source_name, "custom_technical_survey")
    if not custom_ts:
        frappe.throw(
            _("Technical Survey is mandatory to create a Sales Order. Please link a Technical Survey to Quotation {0} first.").format(source_name),
            title=_("Technical Survey Required"),
        )

    from erpnext.selling.doctype.quotation.quotation import make_sales_order as _erpnext_make_so
    return _erpnext_make_so(source_name, target_doc)
