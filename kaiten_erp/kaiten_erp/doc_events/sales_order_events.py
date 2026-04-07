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
    _recalculate_job_file_profitability(doc)


def on_submit(doc, method=None):
    """
    Sales Order on_submit hook - Create Material Request from Technical Survey's System Configuration
    Called after Sales Order is submitted
    """
    create_material_request_from_technical_survey(doc)
    _close_source_quotation_todos(doc)
    _create_payment_milestone_todos(doc)
    _recalculate_job_file_profitability(doc)


def on_update_after_submit(doc, method=None):
    """Handle Payment Milestone changes after Sales Order is submitted."""
    _sync_payment_milestone_todos(doc)


def _recalculate_job_file_profitability(doc):
    """Recalculate profitability on the linked Job File, if any."""
    job_file = doc.get("custom_job_file")
    if job_file:
        from kaiten_erp.kaiten_erp.api.profitability import update_profitability
        update_profitability(job_file)


def _close_source_quotation_todos(sales_order):
    """Close open follow-up ToDos for all Quotations that sourced this Sales Order."""
    for quotation_name in get_source_quotation_names(sales_order):
        close_quotation_todos(quotation_name)


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


def _create_payment_milestone_todos(doc):
    """Create Accounts Manager ToDos for all unpaid milestones with amount > 0 on submit."""
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
        if amount <= 0 or status == "Paid":
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

        # 1. Status is Paid → close todos
        if status == "Paid":
            _close_milestone_todos(doc.name, row.milestone)
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
        quotation_name = item.get("quotation") or (
            item.get("prevdoc_docname")
            if item.get("prevdoc_doctype") == "Quotation"
            else None
        )
        if quotation_name and quotation_name not in quotation_names:
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
