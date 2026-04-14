# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Sales Order event handlers for Technical Survey integration
"""

import frappe
from frappe import _
from kaiten_erp.kaiten_erp.doc_events.quotation_events import close_quotation_todos


def validate(doc, method=None):
    """
    Sales Order validate hook
    Called before Sales Order is saved
    """
    sync_links_from_source_quotation(doc)
    link_technical_survey_to_sales_order(doc)
    enforce_final_approved_quotation_rule(doc)


def on_update(doc, method=None):
    """Sales Order on_update hook – link back to Job File."""
    link_sales_order_to_job_file(doc)


def on_cancel(doc, method=None):
    """Sales Order on_cancel hook – clear link from Job File."""
    unlink_sales_order_from_job_file(doc)
    _close_all_milestone_todos(doc)
    _recalculate_job_file_profitability(doc)


def on_submit(doc, method=None):
    """
    Sales Order on_submit hook - Create Material Request from Technical Survey's System Configuration
    Called after Sales Order is submitted
    """
    create_material_request_from_technical_survey(doc)
    _close_source_quotation_todos(doc)
    _close_create_sales_order_todos(doc)
    _create_payment_milestone_todos(doc)
    _sf_create_collect_payment_todo(doc)
    _create_stock_manager_transfer_todo(doc)
    _recalculate_job_file_profitability(doc)
    _sync_billing_from_milestones(doc.name)


def on_update_after_submit(doc, method=None):
    """Handle Payment Milestone changes after Sales Order is submitted."""
    _sync_payment_milestone_todos(doc)
    _sf_sync_todos(doc)
    _close_structure_payment_todo_if_filled(doc)
    _close_final_payment_todo_if_filled(doc)
    _sync_billing_from_milestones(doc.name)


def _recalculate_job_file_profitability(doc):
    """Recalculate profitability on the linked Job File, if any."""
    job_file = doc.get("custom_job_file")
    if job_file:
        from kaiten_erp.kaiten_erp.api.profitability import update_profitability
        update_profitability(job_file)


# ---------------------------------------------------------------------------
# Milestone-based billing % override
# ---------------------------------------------------------------------------

def _sync_billing_from_milestones(sales_order_name):
    """Recalculate per_billed from Payment Milestone paid amounts.

    When a Sales Order has a payment plan (custom_payment_plan), per_billed
    should reflect the sum of *paid* milestone amounts divided by grand_total,
    NOT the standard ERPNext SI-based calculation.

    Also updates billing_status, SO item billed_amt, and SO status.
    """
    from frappe.utils import flt

    so = frappe.get_doc("Sales Order", sales_order_name)
    milestones = so.get("custom_payment_plan") or []
    if not milestones:
        return  # No payment plan – leave standard ERPNext behaviour

    grand_total = flt(so.grand_total)
    if not grand_total:
        return

    total_paid = sum(
        flt(r.amount) for r in milestones if (r.status or "Pending") == "Paid"
    )
    per_billed = min(flt(total_paid / grand_total * 100, 2), 100)

    if per_billed >= 100:
        billing_status = "Fully Billed"
    elif per_billed > 0:
        billing_status = "Partly Billed"
    else:
        billing_status = "Not Billed"

    # Derive correct status from per_delivered and per_billed
    per_delivered = flt(so.per_delivered)
    if so.status in ("Closed", "On Hold"):
        new_status = so.status
    elif flt(per_delivered, 2) < 100 and flt(per_billed, 2) < 100:
        new_status = "To Deliver and Bill"
    elif flt(per_delivered, 2) < 100 and flt(per_billed, 2) >= 100:
        new_status = "To Deliver"
    elif flt(per_delivered, 2) >= 100 and flt(per_billed, 2) < 100:
        new_status = "To Bill"
    elif flt(per_delivered, 2) >= 100 and flt(per_billed, 2) >= 100:
        new_status = "Completed"
    else:
        new_status = so.status

    # Update SO header
    frappe.db.set_value(
        "Sales Order",
        sales_order_name,
        {
            "per_billed": per_billed,
            "billing_status": billing_status,
            "status": new_status,
        },
        update_modified=False,
    )

    # Distribute billed_amt across SO items proportionally
    net_total = flt(so.net_total) or grand_total
    for item in so.items:
        item_amount = flt(item.net_amount) or flt(item.amount)
        item_billed = flt(item_amount * per_billed / 100, 2) if item_amount else 0
        frappe.db.set_value(
            "Sales Order Item",
            item.name,
            "billed_amt",
            item_billed,
            update_modified=False,
        )


def _close_source_quotation_todos(sales_order):
    """Close open follow-up ToDos for all Quotations that sourced this Sales Order."""
    for quotation_name in get_source_quotation_names(sales_order):
        close_quotation_todos(quotation_name)


def _close_create_sales_order_todos(sales_order):
    """Close 'Create Sales Order' ToDos on source Quotations when SO is submitted."""
    for quotation_name in get_source_quotation_names(sales_order):
        todos = frappe.db.get_all(
            "ToDo",
            filters={
                "reference_type": "Quotation",
                "reference_name": quotation_name,
                "status": "Open",
                "description": ["like", "%Create Sales Order%"],
            },
            fields=["name"],
        )
        for t in todos:
            frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
        if todos:
            frappe.logger("kaiten_erp").info(
                f"Closed {len(todos)} 'Create Sales Order' ToDo(s) for Quotation {quotation_name} on SO {sales_order.name} submit"
            )


# ---------------------------------------------------------------------------
# Payment Milestone ToDo helpers
# ---------------------------------------------------------------------------

def _get_accounts_manager_users():
    """Return list of enabled Accounts Manager user emails."""
    rows = frappe.db.sql(
        """
        SELECT DISTINCT u.name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` hr ON hr.parent = u.name AND hr.parenttype = 'User'
        WHERE hr.role = 'Accounts Manager'
          AND u.enabled = 1
          AND u.name NOT IN ('Administrator', 'Guest')
        """,
        as_dict=True,
    )
    return [r.name for r in rows]


def _milestone_todo_description(sales_order_name, milestone_label, amount, customer_name, k_number):
    """Build a standardised ToDo description for a Payment Milestone."""
    k_part = f" ({k_number})" if k_number else ""
    amt_fmt = frappe.utils.fmt_money(amount, currency="INR")
    return (
        f"Create Sales Invoice & Payment Entry"
        f" - {milestone_label} {amt_fmt}"
        f" - {customer_name}{k_part}"
        f" | {sales_order_name}"
    )


def _get_so_customer_info(sales_order_doc):
    """Return (customer_name, k_number) for a submitted Sales Order document."""
    customer_name = (
        sales_order_doc.get("customer_name")
        or frappe.db.get_value("Customer", sales_order_doc.customer, "customer_name")
        or sales_order_doc.customer
        or ""
    )
    k_number = ""
    job_file = sales_order_doc.get("custom_job_file")
    if job_file:
        k_number = frappe.db.get_value("Job File", job_file, "k_number") or ""
    return customer_name, k_number


def _open_milestone_todos(sales_order_name, milestone_label):
    """Return Open Accounts Manager ToDos for a specific milestone on this SO."""
    return frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Sales Order",
            "reference_name": sales_order_name,
            "role": "Accounts Manager",
            "status": "Open",
            "description": ["like", f"% - {milestone_label} %"],
        },
        fields=["name", "description"],
    )


def _close_milestone_todos(sales_order_name, milestone_label):
    """Close all Open Accounts Manager ToDos for a milestone on this SO."""
    todos = _open_milestone_todos(sales_order_name, milestone_label)
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)


def _close_all_milestone_todos(doc):
    """Close all Open Accounts Manager payment milestone ToDos, Stock Manager transfer ToDos,
    and Self Finance SM collect-payment ToDos for this SO."""
    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Sales Order",
            "reference_name": doc.name,
            "role": "Accounts Manager",
            "status": "Open",
        },
        fields=["name"],
    )
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} Accounts Manager milestone ToDo(s) for Sales Order {doc.name} on cancel"
        )
    _close_stock_transfer_todos(doc.name)
    # Self Finance SM collect-payment ToDo
    _sf_close_collect_todos(doc)
    # Self Finance: close Collect Final Payment and Transfer Remaining Materials todos
    _sf_close_remaining_transfer_todos(doc.name)
    _close_final_payment_sm_todos(doc.name)


# ---------------------------------------------------------------------------
# Stock Manager Material Transfer ToDo helpers
# ---------------------------------------------------------------------------

def _get_stock_manager_users():
    """Return list of enabled Stock Manager user emails.
    Falls back to Administrator if no dedicated Stock Manager users are configured."""
    rows = frappe.db.sql(
        """
        SELECT DISTINCT u.name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` hr ON hr.parent = u.name AND hr.parenttype = 'User'
        WHERE hr.role = 'Stock Manager'
          AND u.enabled = 1
          AND u.name != 'Guest'
        """,
        as_dict=True,
    )
    users = [r.name for r in rows]
    if not users:
        # Fallback: assign to Administrator so the task is never silently lost
        users = ["Administrator"]
    return users


def _stock_transfer_todo_description(sales_order_name, customer_name, k_number):
    """Build a standardised ToDo description for a Stock Manager material transfer task."""
    k_part = f" ({k_number})" if k_number else ""
    return (
        f"Material Transfer Required"
        f" - {customer_name}{k_part}"
        f" | {sales_order_name}"
    )


def _open_stock_transfer_todos(sales_order_name):
    """Return Open Stock Manager material transfer ToDos for this SO."""
    return frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Sales Order",
            "reference_name": sales_order_name,
            "role": "Stock Manager",
            "status": "Open",
            "description": ["like", "Material Transfer Required%"],
        },
        fields=["name", "description"],
    )


def _close_stock_transfer_todos(sales_order_name):
    """Close all Open Stock Manager material transfer ToDos for this SO."""
    todos = _open_stock_transfer_todos(sales_order_name)
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} Stock Manager transfer ToDo(s) for Sales Order {sales_order_name}"
        )


def _primary_mr_already_transferred(doc):
    """Return True if the primary Material Request for this SO is already Transferred.

    The primary MR is the one created from the Technical Survey linked to the SO.
    If no MR is found, returns False (allow todo creation).
    """
    ts_name = doc.get("custom_technical_survey")
    if not ts_name:
        return False

    mr_data = frappe.db.get_value(
        "Material Request",
        {"custom_source_technical_survey": ts_name, "docstatus": 1},
        "status",
    )
    if not mr_data:
        return False

    return mr_data in ("Transferred", "Received", "Partially Received")


def _create_stock_manager_transfer_todo(doc):
    """
    Create Stock Manager ToDos when the Trance 1 payment milestone is Paid.
    Deduplicates — will not create a second todo if one is already open.

    Gates:
      1. Advance milestone must be Paid (falls through if no Advance row).
      2. Primary Material Request must NOT already be fully transferred.
    """

    milestones = doc.get("custom_payment_plan") or []
    if not milestones:
        return

    # Gate logic: For Bank Loan, require Tranche 1 Paid. For Self Finance, require Advance Paid.
    if _is_bank_loan(doc):
        tranche1_row = next((r for r in milestones if r.milestone == "Tranche 1"), None)
        if not tranche1_row or (tranche1_row.status or "Pending") != "Paid":
            return
    else:
        advance_row = next((r for r in milestones if r.milestone == "Advance"), None)
        if not advance_row or (advance_row.status or "Pending") != "Paid":
            return

    # Gate: skip if the primary Material Request is already fully transferred
    if _primary_mr_already_transferred(doc):
        return

    managers = _get_stock_manager_users()
    if not managers:
        return

    customer_name, k_number = _get_so_customer_info(doc)
    description = _stock_transfer_todo_description(doc.name, customer_name, k_number)

    for user in managers:
        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Sales Order",
                "reference_name": doc.name,
                "allocated_to": user,
                "role": "Stock Manager",
                "status": "Open",
                "description": ["like", "Material Transfer Required%"],
            },
        )
        if existing:
            continue

        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user,
            "reference_type": "Sales Order",
            "reference_name": doc.name,
            "description": description,
            "role": "Stock Manager",
            "priority": "High",
            "status": "Open",
        }).insert(ignore_permissions=True)


def _create_payment_milestone_todos(doc):
    """Create Accounts Manager ToDos for all unpaid milestones with amount > 0 on submit.
    Skipped for Self Finance — handled by _sf_sync_todos chain."""
    if _is_self_finance(doc):
        return
    milestones = doc.get("custom_payment_plan") or []
    if not milestones:
        return

    managers = _get_accounts_manager_users()
    if not managers:
        return

    customer_name, k_number = _get_so_customer_info(doc)

    for row in milestones:
        amount = float(row.amount or 0)
        status = (row.status or "Pending")
        if amount <= 0:
            continue
        # If already Paid on submit, create PE ToDo instead of SI & PE ToDo
        # (Bank Loan: AM creates PE before marking Paid, so skip)
        if status == "Paid":
            if not _is_bank_loan(doc):
                _create_payment_entry_todo(doc, row)
            continue

        description = _milestone_todo_description(
            doc.name, row.milestone, amount, customer_name, k_number
        )

        for user in managers:
            # Deduplication: skip if an open todo for this milestone already exists
            existing = frappe.db.exists(
                "ToDo",
                {
                    "reference_type": "Sales Order",
                    "reference_name": doc.name,
                    "allocated_to": user,
                    "role": "Accounts Manager",
                    "status": "Open",
                    "description": ["like", f"% - {row.milestone} %"],
                },
            )
            if existing:
                continue

            frappe.get_doc({
                "doctype": "ToDo",
                "allocated_to": user,
                "reference_type": "Sales Order",
                "reference_name": doc.name,
                "description": description,
                "role": "Accounts Manager",
                "priority": "Medium",
                "status": "Open",
            }).insert(ignore_permissions=True)


def _sync_payment_milestone_todos(doc):
    """
    Called on_update_after_submit. Syncs open Accounts Manager ToDos with the
    current state of each Payment Milestone row.
    Skipped for Self Finance — handled by _sf_sync_todos chain.

    Rules per row:
    - status == 'Paid'              → close all open todos for that milestone
    - amount == 0 AND no invoice/PE → close all open todos for that milestone
    - amount > 0 AND status != 'Paid':
        - if existing open todo has a different amount in description → close + create new
        - if no existing todo at all → create new
        - if existing todo with same amount → do nothing

    After processing all current rows, close todos for milestone names that no longer
    exist in the table (deleted rows).
    """
    if _is_self_finance(doc):
        return
    managers = _get_accounts_manager_users()
    if not managers:
        return

    customer_name, k_number = _get_so_customer_info(doc)
    current_milestones = {row.milestone for row in (doc.get("custom_payment_plan") or [])}

    # ── Handle each current row ──────────────────────────────────────────────
    for row in (doc.get("custom_payment_plan") or []):
        amount = float(row.amount or 0)
        status = row.status or "Pending"
        has_linked_doc = bool(row.get("invoice") or row.get("payment_entry"))

        # 1. Status is Paid → close "Create SI & PE" todos
        #    For non-BL: also create "Create Payment Entry" todo
        #    For Bank Loan: AM already created PE before marking Paid — skip
        if status == "Paid":
            _close_milestone_todos(doc.name, row.milestone)
            if not _is_bank_loan(doc):
                _create_payment_entry_todo(doc, row)
            continue

        # 2. Amount dropped to 0 with no linked invoice/PE → close todos
        if amount <= 0 and not has_linked_doc:
            _close_milestone_todos(doc.name, row.milestone)
            continue

        # 3. Amount > 0 and status != 'Paid' → ensure todo is current
        if amount > 0:
            new_description = _milestone_todo_description(
                doc.name, row.milestone, amount, customer_name, k_number
            )

            existing_todos = _open_milestone_todos(doc.name, row.milestone)

            if existing_todos:
                # Check if description (amount) has changed
                current_desc = existing_todos[0].get("description", "")
                if current_desc != new_description:
                    # Amount changed — close old, create new
                    _close_milestone_todos(doc.name, row.milestone)
                    for user in managers:
                        frappe.get_doc({
                            "doctype": "ToDo",
                            "allocated_to": user,
                            "reference_type": "Sales Order",
                            "reference_name": doc.name,
                            "description": new_description,
                            "role": "Accounts Manager",
                            "priority": "Medium",
                            "status": "Open",
                        }).insert(ignore_permissions=True)
                # else: same description — nothing to do
            else:
                # No open todo yet — create one
                for user in managers:
                    existing = frappe.db.exists(
                        "ToDo",
                        {
                            "reference_type": "Sales Order",
                            "reference_name": doc.name,
                            "allocated_to": user,
                            "role": "Accounts Manager",
                            "status": "Open",
                            "description": ["like", f"% - {row.milestone} %"],
                        },
                    )
                    if existing:
                        continue
                    frappe.get_doc({
                        "doctype": "ToDo",
                        "allocated_to": user,
                        "reference_type": "Sales Order",
                        "reference_name": doc.name,
                        "description": new_description,
                        "role": "Accounts Manager",
                        "priority": "Medium",
                        "status": "Open",
                    }).insert(ignore_permissions=True)

    # ── Close orphaned todos for deleted rows ────────────────────────────────
    all_open_todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Sales Order",
            "reference_name": doc.name,
            "role": "Accounts Manager",
            "status": "Open",
        },
        fields=["name", "description"],
    )
    milestone_options = ["Advance", "Structure", "Final", "Margin", "Tranche 1", "Tranche 2"]
    for todo in all_open_todos:
        desc = todo.get("description", "")
        # Find which milestone this todo belongs to
        todo_milestone = next(
            (m for m in milestone_options if f" - {m} " in desc), None
        )
        if todo_milestone and todo_milestone not in current_milestones:
            frappe.db.set_value("ToDo", todo.name, "status", "Closed", update_modified=False)

    # ── Sync Stock Manager transfer ToDo ─────────────────────────────────────
    _create_stock_manager_transfer_todo(doc)


# ---------------------------------------------------------------------------
# Payment Entry ToDo helpers (created when milestone status → Paid)
# ---------------------------------------------------------------------------

def _payment_entry_todo_description(sales_order_name, milestone_label, amount, customer_name, k_number):
    """Build a standardised ToDo description for a 'Create Payment Entry' task."""
    k_part = f" - {k_number}" if k_number else ""
    amt_fmt = frappe.utils.fmt_money(amount, currency="INR")
    return (
        f"Create Payment Entry for {customer_name}{k_part}"
        f" | {milestone_label} {amt_fmt}"
        f" | {sales_order_name}"
    )


def _open_payment_entry_todos(sales_order_name, milestone_label):
    """Return Open Accounts Manager 'Create Payment Entry' ToDos for a milestone."""
    return frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Sales Order",
            "reference_name": sales_order_name,
            "role": "Accounts Manager",
            "status": "Open",
            "description": ["like", f"Create Payment Entry for% | {milestone_label} %| {sales_order_name}"],
        },
        fields=["name", "description"],
    )


def _close_payment_entry_todos(sales_order_name, milestone_label):
    """Close all Open 'Create Payment Entry' ToDos for a milestone on this SO."""
    todos = _open_payment_entry_todos(sales_order_name, milestone_label)
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    return len(todos)


def _create_payment_entry_todo(doc, row):
    """Create 'Create Payment Entry' ToDos for Accounts Managers when a milestone becomes Paid."""
    amount = float(row.amount or 0)
    if amount <= 0:
        return

    managers = _get_accounts_manager_users()
    if not managers:
        return

    customer_name, k_number = _get_so_customer_info(doc)
    description = _payment_entry_todo_description(
        doc.name, row.milestone, amount, customer_name, k_number
    )

    for user in managers:
        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Sales Order",
                "reference_name": doc.name,
                "allocated_to": user,
                "role": "Accounts Manager",
                "status": "Open",
                "description": ["like", f"Create Payment Entry for% | {row.milestone} %| {doc.name}"],
            },
        )
        if existing:
            continue

        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user,
            "reference_type": "Sales Order",
            "reference_name": doc.name,
            "description": description,
            "role": "Accounts Manager",
            "priority": "High",
            "status": "Open",
        }).insert(ignore_permissions=True)


def _close_structure_payment_todo_if_filled(doc):
    """
    Close the Sales Manager 'Collect Structure Payment' ToDo when the
    Structure milestone row in custom_payment_plan has amount > 0.
    """
    for row in (doc.get("custom_payment_plan") or []):
        if row.milestone == "Structure" and float(row.amount or 0) > 0:
            todos = frappe.db.get_all("ToDo", filters={
                "reference_type": "Sales Order",
                "reference_name": doc.name,
                "role": "Sales Manager",
                "status": "Open",
                "description": ["like", "Collect Structure Payment%"],
            }, fields=["name"])
            for t in todos:
                frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
            return


def _close_final_payment_todo_if_filled(doc):
    """
    Close the Sales Manager 'Collect Final Payment' ToDo when the
    Final milestone row in custom_payment_plan has amount > 0.
    """
    for row in (doc.get("custom_payment_plan") or []):
        if row.milestone == "Final" and float(row.amount or 0) > 0:
            todos = frappe.db.get_all("ToDo", filters={
                "reference_type": "Sales Order",
                "reference_name": doc.name,
                "role": "Sales Manager",
                "status": "Open",
                "description": ["like", "Collect Final Payment%"],
            }, fields=["name"])
            for t in todos:
                frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
            return


def _close_final_payment_sm_todos(sales_order_name):
    """Close SM 'Collect Final Payment' todos for this SO (used on cancel)."""
    todos = frappe.db.get_all("ToDo", filters={
        "reference_type": "Sales Order",
        "reference_name": sales_order_name,
        "role": "Sales Manager",
        "status": "Open",
        "description": ["like", "Collect Final Payment%"],
    }, fields=["name"])
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)


# ---------------------------------------------------------------------------
# Self Finance – Chained ToDo Workflow
# ---------------------------------------------------------------------------
# Flow:
#   Submit (SF) → SM (collect payment) → SM fills amount → AM (create PE)
#   → AM marks Paid → AM ToDo closed → Stock Manager (transfer material)
# ---------------------------------------------------------------------------

_MILESTONE_OPTIONS = ["Advance", "Structure", "Final", "Margin", "Tranche 1", "Tranche 2"]


def _resolve_finance_type(value):
    """Resolve the finance type from a custom_finance_type field value.

    The field may contain a raw finance type ("Self Finance", "Bank Loan")
    from old records, or a Payment Milestone Template name from new records.
    Returns the canonical finance type string.
    """
    value = (value or "").strip()
    if not value:
        return ""
    if value in ("Self Finance", "Bank Loan"):
        return value
    ft = frappe.db.get_value("Payment Milestone Template", value, "finance_type")
    return (ft or "").strip()


def _is_self_finance(doc):
    """Return True if the Sales Order finance type is Self Finance."""
    return _resolve_finance_type(doc.get("custom_finance_type")) == "Self Finance"


def _is_bank_loan(doc):
    """Return True if the Sales Order finance type is Bank Loan."""
    return _resolve_finance_type(doc.get("custom_finance_type")) == "Bank Loan"


def _get_customer_first_name(customer_name):
    """Extract first name from customer_name (e.g. 'Ram Chandra' → 'Ram')."""
    return (customer_name or "").split()[0] if customer_name else ""


# ── SM Collect-Payment ToDo (Self Finance) ───────────────────────────────

def _sf_collect_todo_description(customer_name, sales_order_name):
    return f"Collect payment from {customer_name} | {sales_order_name}"


def _sf_create_collect_payment_todo(doc):
    """On submit (Self Finance): create SM ToDo for job file owner to collect payment."""
    if not _is_self_finance(doc):
        return

    job_file = doc.get("custom_job_file")
    if not job_file:
        return
    owner = frappe.db.get_value("Job File", job_file, "custom_job_file_owner")
    if not owner or not frappe.db.get_value("User", owner, "enabled"):
        return

    customer_name, _ = _get_so_customer_info(doc)
    description = _sf_collect_todo_description(customer_name, doc.name)

    existing = frappe.db.exists("ToDo", {
        "reference_type": "Sales Order",
        "reference_name": doc.name,
        "allocated_to": owner,
        "role": "Sales Manager",
        "status": "Open",
        "description": ["like", "Collect payment from%"],
    })
    if existing:
        return

    frappe.get_doc({
        "doctype": "ToDo",
        "allocated_to": owner,
        "reference_type": "Sales Order",
        "reference_name": doc.name,
        "description": description,
        "role": "Sales Manager",
        "priority": "Medium",
        "status": "Open",
    }).insert(ignore_permissions=True)


def _sf_close_collect_todos(doc):
    """Close SM collect-payment ToDo(s) for this SO."""
    todos = frappe.db.get_all("ToDo", filters={
        "reference_type": "Sales Order",
        "reference_name": doc.name,
        "role": "Sales Manager",
        "status": "Open",
        "description": ["like", "Collect payment from%"],
    }, fields=["name"])
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)


# ── AM Payment-Entry ToDo (Self Finance) ─────────────────────────────────

# Map milestone name → action text for Self Finance AM todos
_SF_MILESTONE_ACTION = {
    "Advance": "Create the {milestone} payment entry of {amount}",
    "Structure": "Create the Sales Invoice and do the payment entry of {amount}",
    "Final": "Create the payment entry of {amount}",
}


def _sf_am_todo_description(customer_first_name, k_number, idx, milestone, amount):
    """Build Self Finance AM description.
    Uses action-based text per milestone, e.g.:
      'Ram - K001. Create the Advance payment entry of ₹20,000'
    Falls back to generic format for unknown milestones.
    """
    amt_fmt = frappe.utils.fmt_money(amount, currency="INR")
    k_part = f" - {k_number}" if k_number else ""
    action_tpl = _SF_MILESTONE_ACTION.get(milestone)
    if action_tpl:
        action = action_tpl.format(milestone=milestone, amount=amt_fmt)
    else:
        action = f"Row {idx} - {milestone} - {amt_fmt}"
    return f"{customer_first_name}{k_part}. {action}"


def _sf_am_todo_like_pattern(milestone):
    """Return a SQL LIKE pattern that matches any SF AM todo for a given milestone."""
    action_tpl = _SF_MILESTONE_ACTION.get(milestone)
    if action_tpl:
        # e.g. "%. Create the Advance payment entry of%"
        prefix = action_tpl.split("{amount}")[0].format(milestone=milestone)
        return f"%. {prefix}%"
    return f"%. Row % - {milestone} -%"


def _sf_open_am_todos(sales_order_name, milestone):
    base_filters = {
        "reference_type": "Sales Order",
        "reference_name": sales_order_name,
        "role": "Accounts Manager",
        "status": "Open",
    }
    new_pattern = _sf_am_todo_like_pattern(milestone)
    todos = frappe.db.get_all("ToDo", filters={**base_filters, "description": ["like", new_pattern]},
                              fields=["name", "description"])
    # Also match legacy "Row X - Milestone - Amount" format for known milestones
    old_pattern = f"%. Row % - {milestone} -%"
    if old_pattern != new_pattern:
        old_todos = frappe.db.get_all("ToDo", filters={**base_filters, "description": ["like", old_pattern]},
                                      fields=["name", "description"])
        seen = {t.name for t in todos}
        todos.extend(t for t in old_todos if t.name not in seen)
    return todos


def _sf_close_am_todos(sales_order_name, milestone):
    todos = _sf_open_am_todos(sales_order_name, milestone)
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    return len(todos)


# ── Self Finance sync (on_update_after_submit) ───────────────────────────

def _sf_sync_todos(doc):
    """
    Self Finance sync — called on every post-submit save.

    1. First row amount > 0 → close SM collect-payment ToDo
    2. Row amount > 0, not Paid → create / update AM ToDo
    3. Row Paid → close AM ToDo (Stock Manager handled separately)
    """
    if not _is_self_finance(doc):
        return

    milestones = doc.get("custom_payment_plan") or []
    if not milestones:
        return

    # 1. Close SM collect-payment ToDo when first milestone has amount
    first_row = min(milestones, key=lambda r: r.idx)
    if float(first_row.amount or 0) > 0:
        _sf_close_collect_todos(doc)

    # 2 & 3. Sync AM ToDos per row
    managers = _get_accounts_manager_users()
    if not managers:
        return

    customer_name, k_number = _get_so_customer_info(doc)
    customer_first_name = _get_customer_first_name(customer_name)
    current_milestones = {row.milestone for row in milestones}

    for row in milestones:
        amount = float(row.amount or 0)
        status = row.status or "Pending"

        # Paid → close AM ToDo
        if status == "Paid":
            _sf_close_am_todos(doc.name, row.milestone)
            continue

        # Amount dropped to 0 → close AM ToDo
        if amount <= 0:
            _sf_close_am_todos(doc.name, row.milestone)
            continue

        # Amount > 0 and not Paid → ensure AM ToDo exists
        new_desc = _sf_am_todo_description(
            customer_first_name, k_number, row.idx, row.milestone, amount
        )
        existing_todos = _sf_open_am_todos(doc.name, row.milestone)

        # Close any stale/old-format todos that don't match the current description
        for t in existing_todos:
            if t.get("description", "") != new_desc:
                frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)

        # Create new todo for each AM user that doesn't already have one
        for user in managers:
            if frappe.db.exists("ToDo", {
                "reference_type": "Sales Order",
                "reference_name": doc.name,
                "allocated_to": user,
                "role": "Accounts Manager",
                "status": "Open",
                "description": new_desc,
            }):
                continue
            frappe.get_doc({
                "doctype": "ToDo",
                "allocated_to": user,
                "reference_type": "Sales Order",
                "reference_name": doc.name,
                "description": new_desc,
                "role": "Accounts Manager",
                "priority": "Medium",
                "status": "Open",
            }).insert(ignore_permissions=True)

    # Close orphaned AM todos for deleted milestone rows
    all_open = frappe.db.get_all("ToDo", filters={
        "reference_type": "Sales Order",
        "reference_name": doc.name,
        "role": "Accounts Manager",
        "status": "Open",
    }, fields=["name", "description"])
    for todo in all_open:
        desc = todo.get("description", "")
        todo_milestone = None
        for m in _MILESTONE_OPTIONS:
            action_tpl = _SF_MILESTONE_ACTION.get(m)
            if action_tpl:
                prefix = action_tpl.split("{amount}")[0].format(milestone=m)
                if prefix in desc:
                    todo_milestone = m
                    break
            elif f" - {m} - " in desc:
                todo_milestone = m
                break
        if todo_milestone and todo_milestone not in current_milestones:
            frappe.db.set_value("ToDo", todo.name, "status", "Closed", update_modified=False)

    # Stock Manager transfer ToDo (fires when first row is Paid)
    _create_stock_manager_transfer_todo(doc)

    # After Structure milestone is Paid, check delivery and trigger next step
    _sf_check_delivery_after_structure_paid(doc)

    # After Final milestone is Paid, create VH todo for Verification Handover
    _sf_create_vh_todo_on_final_paid(doc)


def _sf_check_delivery_after_structure_paid(doc):
    """
    After Structure milestone is Paid (Self Finance), check whether all TS items
    have been delivered:
      (a) All delivered → create VH todo for Project Installation
      (b) Not all delivered → create Stock Manager todo for remaining material transfer
    """
    milestones = doc.get("custom_payment_plan") or []
    structure_row = next((r for r in milestones if r.milestone == "Structure"), None)
    if not structure_row or (structure_row.status or "Pending") != "Paid":
        return

    job_file_name = doc.get("custom_job_file")
    if not job_file_name:
        return

    # Check delivery status on the SO
    per_delivered = float(frappe.db.get_value("Sales Order", doc.name, "per_delivered") or 0)

    if per_delivered >= 100.0:
        # All items delivered — create VH todo for Project Installation
        _sf_create_vh_todo_for_next(job_file_name, "Project Installation", "custom_project_installation")
    else:
        # Not all delivered — create Stock Manager todo for remaining transfer
        _sf_create_remaining_transfer_todo(doc)


def _sf_create_vh_todo_for_next(job_file_name, next_doctype, jf_field):
    """Create a Vendor Head todo to initiate the given next execution doctype.

    Skips if the target document's workflow has already progressed past Draft
    (i.e. the execution step has already been initiated).
    """
    from frappe.utils import nowdate

    next_doc_name = frappe.db.get_value("Job File", job_file_name, jf_field)
    if not next_doc_name:
        return

    # If the target doc is already past Draft, it has been initiated — skip
    wf_state = frappe.db.get_value(next_doctype, next_doc_name, "workflow_state")
    if wf_state and wf_state != "Draft":
        return

    customer_first_name = frappe.db.get_value("Job File", job_file_name, "first_name") or job_file_name

    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent as user"],
    )
    if not vendor_heads:
        return

    description = f"{customer_first_name} - {next_doc_name} - Initiate {next_doctype}"

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
        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user,
            "description": description,
            "reference_type": next_doctype,
            "reference_name": next_doc_name,
            "role": "Vendor Head",
            "priority": "High",
            "status": "Open",
            "date": nowdate(),
        }).insert(ignore_permissions=True)


def _sf_create_remaining_transfer_todo(doc):
    """Create Stock Manager todo to transfer remaining materials (partial delivery)."""
    customer_name, k_number = _get_so_customer_info(doc)
    k_part = f" ({k_number})" if k_number else ""
    description = (
        f"Transfer Remaining Materials"
        f" - {customer_name}{k_part}"
        f" | {doc.name}"
    )

    managers = _get_stock_manager_users()
    for user in managers:
        if frappe.db.exists("ToDo", {
            "reference_type": "Sales Order",
            "reference_name": doc.name,
            "allocated_to": user,
            "role": "Stock Manager",
            "status": "Open",
            "description": ["like", "Transfer Remaining Materials%"],
        }):
            continue
        frappe.get_doc({
            "doctype": "ToDo",
            "allocated_to": user,
            "reference_type": "Sales Order",
            "reference_name": doc.name,
            "description": description,
            "role": "Stock Manager",
            "priority": "High",
            "status": "Open",
        }).insert(ignore_permissions=True)


def _sf_close_remaining_transfer_todos(sales_order_name):
    """Close Stock Manager 'Transfer Remaining Materials' todos for this SO."""
    todos = frappe.db.get_all("ToDo", filters={
        "reference_type": "Sales Order",
        "reference_name": sales_order_name,
        "role": "Stock Manager",
        "status": "Open",
        "description": ["like", "Transfer Remaining Materials%"],
    }, fields=["name"])
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)


def _sf_create_vh_todo_on_final_paid(doc):
    """
    When the Final milestone status becomes 'Paid' (Self Finance),
    create a VH todo for Verification Handover.
    """
    milestones = doc.get("custom_payment_plan") or []
    final_row = next((r for r in milestones if r.milestone == "Final"), None)
    if not final_row or (final_row.status or "Pending") != "Paid":
        return

    job_file_name = doc.get("custom_job_file")
    if not job_file_name:
        return

    _sf_create_vh_todo_for_next(
        job_file_name, "Verification Handover", "custom_verification_handover"
    )


def link_technical_survey_to_sales_order(sales_order):
    """
    Automatically link an approved Technical Survey to the Sales Order
    Uses 3-tier matching to find the correct Technical Survey:
    1. Exact customer match
    2. Fuzzy customer match (handles "Customer Name None" variations)
    3. Lead name match

    Args:
        sales_order: Sales Order document
    """
    # Skip if already linked
    if sales_order.get("custom_technical_survey"):
        return

    source_quotation = get_source_quotation_name(sales_order)
    if source_quotation:
        quotation_ts = frappe.db.get_value(
            "Quotation", source_quotation, "custom_technical_survey"
        )
        if quotation_ts:
            sales_order.custom_technical_survey = quotation_ts
            return

    customer = sales_order.customer
    if not customer:
        return

    # Try to find Lead linked to this customer
    lead = None

    # 1. Exact match
    lead = frappe.db.get_value("Lead", {"customer": customer}, "name")

    # 2. Fuzzy match (customer name might have extra text)
    if not lead:
        leads = frappe.db.sql(
            """
            SELECT name 
            FROM `tabLead` 
            WHERE customer LIKE %s
            LIMIT 1
        """,
            f"%{customer}%",
            as_dict=True,
        )

        if leads:
            lead = leads[0].name

    # 3. Match by lead_name (if customer name matches lead name)
    if not lead:
        customer_name = frappe.db.get_value("Customer", customer, "customer_name")
        if customer_name:
            lead = frappe.db.get_value("Lead", {"lead_name": customer_name}, "name")

    if not lead:
        frappe.msgprint(
            _(
                "No Lead found for customer {0}. Technical Survey will not be linked."
            ).format(customer),
            alert=True,
            indicator="orange",
        )
        return

    # Find approved Technical Survey for this Lead
    technical_survey = frappe.db.get_value(
        "Technical Survey",
        {"custom_lead": lead, "workflow_state": "Approved"},
        "name",
        order_by="modified desc",  # Get the most recent approved TS
    )

    if technical_survey:
        sales_order.custom_technical_survey = technical_survey
        frappe.msgprint(
            _("Linked Technical Survey {0} to Sales Order").format(technical_survey),
            alert=True,
            indicator="green",
        )
    else:
        frappe.msgprint(
            _("No approved Technical Survey found for Lead {0}").format(lead),
            alert=True,
            indicator="orange",
        )


def enforce_final_approved_quotation_rule(sales_order):
    if not sales_order.is_new():
        return

    # If the SO already has an approved TS (synced earlier in validate), allow it
    so_ts = sales_order.get("custom_technical_survey")
    if so_ts:
        ts_state = frappe.db.get_value("Technical Survey", so_ts, "workflow_state")
        if ts_state == "Approved":
            return

    quotation_names = get_source_quotation_names(sales_order)
    if not quotation_names:
        frappe.throw(_("Sales Order can only be created from Final Approved Quotation."))

    for quotation_name in quotation_names:
        quotation = frappe.db.get_value(
            "Quotation",
            quotation_name,
            ["custom_quotation_stage", "custom_technical_survey"],
            as_dict=True,
        )
        if not quotation:
            frappe.throw(
                _("Sales Order can only be created from Final Approved Quotation.")
            )

        # Allow if the quotation has an approved Technical Survey linked
        technical_survey = quotation.get("custom_technical_survey")
        if technical_survey:
            ts_state = frappe.db.get_value(
                "Technical Survey", technical_survey, "workflow_state"
            )
            if ts_state == "Approved":
                continue

        frappe.throw(
            _("Sales Order can only be created from Final Approved Quotation.")
        )


def sync_links_from_source_quotation(sales_order):
    source_quotation = get_source_quotation_name(sales_order)
    if not source_quotation:
        return

    quotation = frappe.db.get_value(
        "Quotation",
        source_quotation,
        ["opportunity", "custom_job_file", "custom_technical_survey", "party_name"],
        as_dict=True,
    )
    if not quotation:
        return

    if quotation.get("opportunity"):
        sales_order.opportunity = quotation.opportunity

    if quotation.get("custom_job_file"):
        sales_order.custom_job_file = quotation.custom_job_file

    if quotation.get("custom_technical_survey"):
        sales_order.custom_technical_survey = quotation.custom_technical_survey

    if quotation.get("party_name") and not sales_order.customer:
        sales_order.customer = quotation.party_name


def get_source_quotation_name(sales_order):
    quotation_names = get_source_quotation_names(sales_order)
    return quotation_names[0] if quotation_names else None


def get_source_quotation_names(sales_order):
    quotation_names = []
    for item in sales_order.get("items") or []:
        quotation_name = item.get("quotation") or item.get("prevdoc_docname")
        if quotation_name and quotation_name not in quotation_names:
            # Verify it is actually a Quotation (prevdoc_docname may lack prevdoc_doctype)
            if frappe.db.exists("Quotation", quotation_name):
                quotation_names.append(quotation_name)
    return quotation_names


def create_material_request_from_technical_survey(sales_order):
    """
    Create Material Request from Technical Survey's System Configuration
    This is the final source of truth for material requirements

    Args:
        sales_order: Sales Order document
    """
    # Check if Technical Survey is linked
    technical_survey_name = sales_order.get("custom_technical_survey")

    if not technical_survey_name:
        frappe.msgprint(
            _(
                "No Technical Survey linked to this Sales Order. Material Request will not be created."
            ),
            alert=True,
            indicator="orange",
        )
        return

    # Get Technical Survey document
    technical_survey = frappe.get_doc("Technical Survey", technical_survey_name)

    # Verify Technical Survey is approved
    if technical_survey.workflow_state != "Approved":
        frappe.msgprint(
            _(
                "Technical Survey {0} is not approved. Material Request will not be created."
            ).format(technical_survey_name),
            alert=True,
            indicator="red",
        )
        return

    # Deduplication guard — skip if a Material Request already exists for this Sales Order
    existing_mr = frappe.db.get_value(
        "Material Request",
        {"custom_source_sales_order": sales_order.name, "docstatus": ["!=", 2]},
        "name",
    )
    if existing_mr:
        frappe.msgprint(
            _("Material Request {0} already exists for this Sales Order. Skipping creation.").format(existing_mr),
            alert=True,
            indicator="orange",
        )
        return

    # Resolve warehouse once — validate SO's set_warehouse belongs to the same company
    _item_warehouse = None
    if sales_order.set_warehouse:
        wh_company = frappe.db.get_value(
            "Warehouse", sales_order.set_warehouse, "company"
        )
        if wh_company == sales_order.company:
            _item_warehouse = sales_order.set_warehouse
    if not _item_warehouse:
        _item_warehouse = get_default_warehouse(sales_order.company)

    # Collect items from System Configuration
    items = []

    # Add Panel items
    if technical_survey.panel and technical_survey.panel_qty_bom:
        try:
            qty = (
                float(technical_survey.panel_qty_bom)
                if technical_survey.panel_qty_bom
                else 0
            )
            if qty > 0:
                items.append(
                    {
                        "item_code": technical_survey.panel,
                        "qty": qty,
                        "uom": frappe.db.get_value(
                            "Item", technical_survey.panel, "stock_uom"
                        )
                        or "Nos",
                        "schedule_date": sales_order.delivery_date
                        or frappe.utils.today(),
                        "warehouse": _item_warehouse,
                        "sales_order": sales_order.name,
                    }
                )
        except (ValueError, TypeError):
            frappe.log_error(
                f"Invalid panel quantity in Technical Survey {technical_survey_name}: {technical_survey.panel_qty_bom}"
            )

    # Add Inverter items
    if technical_survey.inverter and technical_survey.inverter_qty_bom:
        try:
            qty = (
                float(technical_survey.inverter_qty_bom)
                if technical_survey.inverter_qty_bom
                else 0
            )
            if qty > 0:
                items.append(
                    {
                        "item_code": technical_survey.inverter,
                        "qty": qty,
                        "uom": frappe.db.get_value(
                            "Item", technical_survey.inverter, "stock_uom"
                        )
                        or "Nos",
                        "schedule_date": sales_order.delivery_date
                        or frappe.utils.today(),
                        "warehouse": _item_warehouse,
                        "sales_order": sales_order.name,
                    }
                )
        except (ValueError, TypeError):
            frappe.log_error(
                f"Invalid inverter quantity in Technical Survey {technical_survey_name}: {technical_survey.inverter_qty_bom}"
            )

    # Add Battery items
    if technical_survey.battery and technical_survey.battery_qty_bom:
        try:
            qty = (
                float(technical_survey.battery_qty_bom)
                if technical_survey.battery_qty_bom
                else 0
            )
            if qty > 0:
                items.append(
                    {
                        "item_code": technical_survey.battery,
                        "qty": qty,
                        "uom": frappe.db.get_value(
                            "Item", technical_survey.battery, "stock_uom"
                        )
                        or "Nos",
                        "schedule_date": sales_order.delivery_date
                        or frappe.utils.today(),
                        "warehouse": _item_warehouse,
                        "sales_order": sales_order.name,
                    }
                )
        except (ValueError, TypeError):
            frappe.log_error(
                f"Invalid battery quantity in Technical Survey {technical_survey_name}: {technical_survey.battery_qty_bom}"
            )

    # Add BOM items from table_vctx (other BOM items table)
    if technical_survey.table_vctx:
        for bom_item in technical_survey.table_vctx:
            if bom_item.item_code and bom_item.qty:
                try:
                    qty = float(bom_item.qty) if bom_item.qty else 0
                    if qty > 0:
                        items.append(
                            {
                                "item_code": bom_item.item_code,
                                "qty": qty,
                                "uom": bom_item.uom
                                or frappe.db.get_value(
                                    "Item", bom_item.item_code, "stock_uom"
                                )
                                or "Nos",
                                "schedule_date": sales_order.delivery_date
                                or frappe.utils.today(),
                                "warehouse": _item_warehouse,
                                "sales_order": sales_order.name,
                            }
                        )
                except (ValueError, TypeError):
                    frappe.log_error(
                        f"Invalid quantity for item {bom_item.item_code} in Technical Survey {technical_survey_name}: {bom_item.qty}"
                    )

    if not items:
        frappe.msgprint(
            _(
                "No items found in Technical Survey {0}'s System Configuration. Material Request will not be created."
            ).format(technical_survey_name),
            alert=True,
            indicator="orange",
        )
        return

    # Resolve target warehouse — validate SO's set_warehouse belongs to the same company
    target_warehouse = None
    if sales_order.set_warehouse:
        wh_company = frappe.db.get_value(
            "Warehouse", sales_order.set_warehouse, "company"
        )
        if wh_company == sales_order.company:
            target_warehouse = sales_order.set_warehouse
    if not target_warehouse:
        target_warehouse = get_default_warehouse(sales_order.company)

    # Create Material Request
    material_request = frappe.get_doc(
        {
            "doctype": "Material Request",
            "material_request_type": "Material Transfer",
            "schedule_date": sales_order.delivery_date or frappe.utils.today(),
            "company": sales_order.company,
            "set_warehouse": target_warehouse,
            "items": items,
        }
    )

    # Add custom fields to link Technical Survey and Sales Order (will appear in connections tab)
    if frappe.db.has_column("Material Request", "custom_source_technical_survey"):
        material_request.custom_source_technical_survey = technical_survey_name

    if frappe.db.has_column("Material Request", "custom_source_sales_order"):
        material_request.custom_source_sales_order = sales_order.name

    if frappe.db.has_column("Material Request", "custom_source_customer"):
        material_request.custom_source_customer = sales_order.customer

    # Set flag to skip advance payment validation during Sales Order submission
    # The advance invoice will be created AFTER this Material Request
    material_request.flags.ignore_advance_validation = True

    material_request.insert(ignore_permissions=True)

    # Add comment for audit trail
    material_request.add_comment(
        "Info",
        f"Created from Technical Survey: {technical_survey_name} via Sales Order: {sales_order.name}",
    )

    frappe.msgprint(
        _("Material Request {0} created").format(
            material_request.name
        ),
        alert=True,
        indicator="green",
    )

    frappe.db.commit()


def get_default_warehouse(company=None):
    """
    Get default warehouse for the company

    Args:
        company: Company name to filter warehouses by

    Returns:
        str: Default warehouse name
    """
    # Try to get default warehouse from company settings
    default_warehouse = frappe.db.get_single_value(
        "Stock Settings", "default_warehouse"
    )

    # Verify it belongs to the correct company
    if default_warehouse and company:
        wh_company = frappe.db.get_value("Warehouse", default_warehouse, "company")
        if wh_company and wh_company != company:
            default_warehouse = None

    if not default_warehouse:
        # Get a warehouse belonging to the specified company
        filters = {"disabled": 0, "is_group": 0}
        if company:
            filters["company"] = company
        default_warehouse = frappe.db.get_value("Warehouse", filters, "name")

    return default_warehouse


def link_sales_order_to_job_file(sales_order):
    """Set the Job File's sales_order field when a Sales Order is linked to a Job File."""
    job_file = sales_order.get("custom_job_file")
    if not job_file:
        return

    current_so = frappe.db.get_value("Job File", job_file, "sales_order")
    if current_so == sales_order.name:
        return

    frappe.db.set_value(
        "Job File", job_file, "sales_order", sales_order.name, update_modified=False
    )


def unlink_sales_order_from_job_file(sales_order):
    """Clear the Job File's sales_order field when a Sales Order is cancelled."""
    job_file = sales_order.get("custom_job_file")
    if not job_file:
        return

    current_so = frappe.db.get_value("Job File", job_file, "sales_order")
    if current_so != sales_order.name:
        return

    frappe.db.set_value(
        "Job File", job_file, "sales_order", None, update_modified=False
    )
