# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Milestone Invoice Manager
Handles creation of milestone-based Sales Invoices and payment validation
for Sales Order workflow progression
"""

import frappe
from frappe import _
from frappe.utils import nowdate, flt, get_link_to_form, add_days, getdate


def create_milestone_invoice(source_doc, milestone_type, items, description=""):
    """
    Create a milestone-based Sales Invoice

    Args:
        source_doc: Source document (Sales Order, Delivery Note, etc.)
        milestone_type: Type of milestone ("Advance Payment", "Delivery", "Final Payment")
        items: List of items to include in the invoice
        description: Additional description for the invoice

    Returns:
        Sales Invoice document
    """
    # Determine source doctype and get customer info
    source_doctype = source_doc.doctype

    if source_doctype == "Sales Order":
        customer = source_doc.customer
        company = source_doc.company
        currency = source_doc.currency
        sales_order = source_doc.name
    elif source_doctype == "Delivery Note":
        customer = source_doc.customer
        company = source_doc.company
        currency = source_doc.currency
        # Get Sales Order from Delivery Note items
        sales_order = None
        if source_doc.items and len(source_doc.items) > 0:
            sales_order = source_doc.items[0].against_sales_order
    else:
        frappe.throw(_("Unsupported source document type: {0}").format(source_doctype))

    # Create Sales Invoice
    sales_invoice = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "customer": customer,
            "company": company,
            "currency": currency,
            "posting_date": nowdate(),
            "due_date": nowdate(),
            "custom_milestone_type": milestone_type,
            "remarks": _("{0} for {1} {2}. {3}").format(
                milestone_type, source_doctype, source_doc.name, description
            ),
            "items": items,
        }
    )

    # Link to Sales Order if available
    if sales_order:
        sales_invoice.custom_sales_order = sales_order

    # Link to Job File if available
    if sales_order:
        job_file_name = frappe.db.get_value(
            "Job File", {"sales_order": sales_order}, "name"
        )
        if job_file_name:
            sales_invoice.custom_job_file = job_file_name

            # Also try to link Technical Survey if available on Job File
            # Assuming logic to find Technical Survey from Job File
            technical_survey_name = frappe.db.get_value(
                "Technical Survey", {"custom_job_file": job_file_name}, "name"
            )
            if technical_survey_name:
                sales_invoice.custom_technical_survey = technical_survey_name

    sales_invoice.flags.ignore_permissions = True
    sales_invoice.insert()

    # Add comment for audit trail
    sales_invoice.add_comment(
        "Info",
        _("Milestone Invoice created from {0}: {1}. Milestone: {2}").format(
            source_doctype, source_doc.name, milestone_type
        ),
    )

    frappe.msgprint(
        _(
            "Sales Invoice {0} created in draft mode for milestone: {1}. You can adjust the amount before submitting."
        ).format(sales_invoice.name, milestone_type),
        alert=True,
        indicator="blue",
    )

    return sales_invoice


def check_payment_status(invoice_name):
    """
    Check if a Sales Invoice is fully paid via Payment Entry

    Args:
        invoice_name: Name of the Sales Invoice

    Returns:
        bool: True if submitted AND fully paid, False otherwise
    """
    if not invoice_name:
        return False

    # Check if invoice exists and is submitted
    if not frappe.db.exists("Sales Invoice", invoice_name):
        return False

    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    # Invoice must be submitted (not draft)
    if invoice.docstatus != 1:
        return False

    # Check outstanding amount - must be fully paid
    outstanding = flt(invoice.outstanding_amount)

    return outstanding <= 0


def assign_todo_to_accounts_managers(
    reference_doc, milestone_name, description="", due_date=None
):
    """
    Create To-Do tasks for all users with Accounts Manager role

    Args:
        reference_doc: Reference document (Sales Invoice)
        milestone_name: Name of the milestone (e.g., "Advance Payment", "Delivery", "Final Payment")
        description: Additional description for the To-Do
    """
    # Get all users with Accounts Manager role
    accounts_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Accounts Manager", "parenttype": "User"},
        fields=["parent as user"],
    )

    if not accounts_managers:
        frappe.log_error(
            "No users found with Accounts Manager role for To-Do assignment",
            "Milestone Invoice Manager",
        )
        return

    # Create To-Do for each Accounts Manager
    for manager in accounts_managers:
        user = manager.user

        # Skip disabled users
        if frappe.db.get_value("User", user, "enabled") == 0:
            continue

        # Check if ToDo already exists to prevent duplicate assignments
        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Sales Invoice",
                "reference_name": reference_doc.name,
                "allocated_to": user,
                "status": "Open",
                "description": ["like", "%Collect Advance Payment%"],
            },
        )

        if existing:
            continue

        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": user,
                "description": _(
                    "Collect Advance Payment for Sales Invoice {0}. {1}"
                ).format(reference_doc.name, description),
                "reference_type": "Sales Invoice",
                "reference_name": reference_doc.name,
                "priority": "High",
                "status": "Open",
                "date": due_date or nowdate(),
            }
        )

        todo.flags.ignore_permissions = True
        todo.insert()

    frappe.msgprint(
        _("To-Do 'Collect Advance Payment' assigned to Accounts Managers"),
        alert=True,
        indicator="blue",
    )


def assign_todo_to_execution_managers(
    title, description, reference_doctype, reference_name
):
    """
    Create To-Do tasks for all users with Execution Manager role
    """
    execution_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Execution Manager", "parenttype": "User"},
        fields=["parent as user"],
    )

    if not execution_managers:
        return

    for manager in execution_managers:
        user = manager.user
        if frappe.db.get_value("User", user, "enabled") == 0:
            continue

        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": reference_doctype,
                "reference_name": reference_name,
                "allocated_to": user,
                "status": "Open",
                "description": description,
            },
        )

        if existing:
            continue

        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": user,
                "description": description,
                "reference_type": reference_doctype,
                "reference_name": reference_name,
                "priority": "High",
                "status": "Open",
            }
        )
        todo.flags.ignore_permissions = True
        todo.insert()


def get_milestone_invoice(sales_order_name, milestone_type):
    """
    Get the milestone invoice reference from Sales Order

    Args:
        sales_order_name: Name of the Sales Order
        milestone_type: Type of milestone ("advance", "delivery", "final")

    Returns:
        str: Invoice name or None
    """
    if not sales_order_name:
        return None

    field_map = {
        "advance": "custom_advance_invoice",
        "delivery": "custom_delivery_invoice",
        "final": "custom_final_invoice",
    }

    field_name = field_map.get(milestone_type.lower())

    if not field_name:
        return None

    if not frappe.db.has_column("Sales Order", field_name):
        return None

    return frappe.db.get_value("Sales Order", sales_order_name, field_name)


def update_payment_status_on_sales_order(sales_order_name):
    """
    Update payment status flags on Sales Order based on invoice payment status

    Args:
        sales_order_name: Name of the Sales Order
    """
    if not sales_order_name:
        return

    sales_order = frappe.get_doc("Sales Order", sales_order_name)

    # Check advance payment
    if (
        hasattr(sales_order, "custom_advance_invoice")
        and sales_order.custom_advance_invoice
    ):
        advance_paid = check_payment_status(sales_order.custom_advance_invoice)
        if hasattr(sales_order, "custom_advance_paid"):
            frappe.db.set_value(
                "Sales Order",
                sales_order_name,
                "custom_advance_paid",
                1 if advance_paid else 0,
                update_modified=False,
            )

    # Check delivery payment
    if (
        hasattr(sales_order, "custom_delivery_invoice")
        and sales_order.custom_delivery_invoice
    ):
        delivery_paid = check_payment_status(sales_order.custom_delivery_invoice)
        if hasattr(sales_order, "custom_delivery_paid"):
            frappe.db.set_value(
                "Sales Order",
                sales_order_name,
                "custom_delivery_paid",
                1 if delivery_paid else 0,
                update_modified=False,
            )

            # Trigger to-do for Structure Mounting if delivery paid
            if delivery_paid:
                job_file_name = frappe.db.get_value(
                    "Job File", {"sales_order": sales_order_name}, "name"
                )

                # Check 2: link on Sales Order
                if not job_file_name:
                    job_file_name = sales_order.get("custom_job_file")

                # Check 3: Fallback - search by Customer
                if not job_file_name and sales_order.customer:
                    job_files = frappe.get_all(
                        "Job File",
                        filters={"customer": sales_order.customer},
                        order_by="creation desc",
                        limit=1,
                    )
                    if job_files:
                        job_file_name = job_files[0].name
                        frappe.msgprint(
                            _("Job File found for customer: {0}").format(job_file_name),
                            alert=True,
                        )

                if job_file_name:
                    structure_mounting = frappe.db.get_value(
                        "Job File", job_file_name, "custom_structure_mounting"
                    )
                    if structure_mounting:
                        assign_todo_to_execution_managers(
                            "Payment at the time of delivery is done. Action Required.",
                            _(
                                "Payment at the time of delivery is done by the customer. Take action on the structure mounting (linked to {0})."
                            ).format(structure_mounting),
                            "Structure Mounting",
                            structure_mounting,
                        )

    # Check final payment
    if (
        hasattr(sales_order, "custom_final_invoice")
        and sales_order.custom_final_invoice
    ):
        final_paid = check_payment_status(sales_order.custom_final_invoice)
        if hasattr(sales_order, "custom_final_paid"):
            frappe.db.set_value(
                "Sales Order",
                sales_order_name,
                "custom_final_paid",
                1 if final_paid else 0,
                update_modified=False,
            )

    frappe.db.commit()


# ============================================================================
# SALES ORDER HOOKS
# ============================================================================


def create_advance_invoice(doc, method=None):
    """
    Create advance payment invoice when Sales Order is submitted
    Called via hook on Sales Order on_submit

    Amount is calculated from Payment Terms Template (e.g., 10% of grand total)
    """
    # Check if advance invoice already exists
    if hasattr(doc, "custom_advance_invoice") and doc.custom_advance_invoice:
        return

    # Calculate advance amount from Payment Terms Template
    advance_amount = doc.grand_total  # Default to full amount
    advance_percentage = 0

    if doc.payment_terms_template:
        # Get the first payment term (Advance)
        payment_terms = frappe.get_all(
            "Payment Terms Template Detail",
            filters={"parent": doc.payment_terms_template},
            fields=["invoice_portion", "description"],
            order_by="idx asc",
            limit=1,
        )

        if payment_terms and len(payment_terms) > 0:
            advance_percentage = flt(payment_terms[0].invoice_portion)
            advance_amount = (doc.grand_total * advance_percentage) / 100

            frappe.logger().info(
                f"Advance invoice for SO {doc.name}: {advance_percentage}% of {doc.grand_total} = {advance_amount}"
            )

    # Create invoice item for advance amount
    items = [
        {
            "item_code": "Advance Payment",
            "item_name": "Advance Payment",
            "description": _("Advance payment ({0}%) for Sales Order {1}").format(
                advance_percentage or 100, doc.name
            ),
            "qty": 1,
            "uom": "Nos",
            "rate": advance_amount,
            "amount": advance_amount,
        }
    ]

    # Create the invoice
    try:
        invoice = create_milestone_invoice(
            doc,
            "Advance Payment",
            items,
            description=_(
                "Payment required before material transfer. Amount: {0}% of total"
            ).format(advance_percentage or 100),
        )

        # Update Sales Order with invoice reference
        if hasattr(doc, "custom_advance_invoice"):
            frappe.db.set_value(
                "Sales Order",
                doc.name,
                "custom_advance_invoice",
                invoice.name,
                update_modified=False,
            )

        # Update Job File Financial Status
        job_file_name = frappe.db.get_value(
            "Job File", {"sales_order": doc.name}, "name"
        )
        if job_file_name:
            frappe.db.set_value(
                "Job File",
                job_file_name,
                {
                    "advance_invoice_number": invoice.name,
                    "advance_invoice_amount": invoice.grand_total,
                    "advance_paid_amount": 0,
                    "advance_outstanding_amount": invoice.outstanding_amount,
                    "advance_invoice_status": "Unpaid",
                },
                update_modified=False,
            )

        # Assign To-Do to Accounts Managers
        assign_todo_to_accounts_managers(
            invoice,
            "Advance Payment",
            description=_("Customer: {0}, Advance Amount ({1}%): {2}").format(
                doc.customer,
                advance_percentage or 100,
                frappe.utils.fmt_money(advance_amount, currency=doc.currency),
            ),
            due_date=invoice.due_date,
        )

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(
            frappe.get_traceback(),
            _("Failed to create advance invoice for Sales Order {0}").format(doc.name),
        )
        frappe.throw(_("Failed to create advance invoice: {0}").format(str(e)))


def validate_advance_payment(doc, method=None):
    """
    Validate that advance payment is received before allowing Material Request submission
    Called via hook on Material Request validate

    NOTE: This validation is skipped for Material Requests created automatically during
    Sales Order submission, as the advance invoice is created AFTER the Material Request.
    """
    # Skip validation if this is being created during Sales Order submission
    if hasattr(doc, "flags") and doc.flags.get("ignore_advance_validation"):
        return

    # Only validate Material Transfer type
    if doc.doctype == "Material Request":
        if doc.material_request_type != "Material Transfer":
            return
    elif doc.doctype == "Stock Entry":
        if doc.purpose != "Material Transfer":
            return
    else:
        return

    # Get linked Sales Order
    sales_order = None

    if doc.get("custom_source_sales_order"):
        sales_order = doc.custom_source_sales_order

    # If not found on header and it's Stock Entry, try to find from items linked to Material Request
    if not sales_order and doc.doctype == "Stock Entry" and doc.items:
        mr_lists = [d.material_request for d in doc.items if d.material_request]
        if mr_lists:
            # Check first found MR
            sales_order = frappe.db.get_value(
                "Material Request", mr_lists[0], "custom_source_sales_order"
            )

    if not sales_order:
        # Try to find from custom fields or items
        return

    # Check if advance invoice exists and is paid
    advance_invoice = get_milestone_invoice(sales_order, "advance")

    if not advance_invoice:
        frappe.throw(
            _(
                "Cannot submit Material Request. Advance invoice not yet created for Sales Order {0}"
            ).format(sales_order)
        )

    if not check_payment_status(advance_invoice):
        # Allow if override approved in Job File
        job_file_name = frappe.db.get_value(
            "Job File", {"sales_order": sales_order}, "name"
        )
        if job_file_name:
            override_approved = frappe.db.get_value(
                "Job File", job_file_name, "advance_override_approved"
            )
            if override_approved:
                # frappe.msgprint(_("Allowing Material Transfer with override approval."), alert=True, indicator="orange")
                return

        frappe.throw(
            _(
                "Cannot submit Material Request. Advance payment not received for Sales Invoice {0} and no Override Approved."
            ).format(advance_invoice)
        )


# ============================================================================
# PAYMENT ENTRY HOOKS
# ============================================================================


def update_payment_status(doc, method=None):
    """
    Update payment status flags when Payment Entry is submitted
    Called via hook on Payment Entry on_submit
    """
    # Check if this payment is linked to any Sales Invoice
    if not doc.references:
        return

    for reference in doc.references:
        if reference.reference_doctype == "Sales Invoice":
            invoice_name = reference.reference_name

            check_and_update_job_file_advance(invoice_name)

            # Get linked Sales Order from the invoice
            sales_order = frappe.db.get_value(
                "Sales Invoice", invoice_name, "custom_sales_order"
            )

            if sales_order:
                # Update payment status on Sales Order
                update_payment_status_on_sales_order(sales_order)

                frappe.msgprint(
                    _("Payment status updated for Sales Order {0}").format(sales_order),
                    alert=True,
                    indicator="green",
                )


def check_and_update_job_file_advance(invoice_name):
    """
    Update Job File financial status and trigger workflows based on payment
    """
    # Find Job File linked to this invoice
    # Either directly linked (custom_job_file) or via Sales Order
    job_file_name = frappe.db.get_value(
        "Sales Invoice", invoice_name, "custom_job_file"
    )

    if not job_file_name:
        sales_order = frappe.db.get_value(
            "Sales Invoice", invoice_name, "custom_sales_order"
        )
        if sales_order:
            job_file_name = frappe.db.get_value(
                "Job File", {"sales_order": sales_order}, "name"
            )

    if not job_file_name:
        return

    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    paid_amount = invoice.grand_total - invoice.outstanding_amount
    status = "Unpaid"
    if invoice.outstanding_amount <= 0:
        status = "Paid"
    elif paid_amount > 0:
        status = "Partly Paid"

    # Update Job File
    frappe.db.set_value(
        "Job File",
        job_file_name,
        {
            "advance_paid_amount": paid_amount,
            "advance_outstanding_amount": invoice.outstanding_amount,
            "advance_invoice_status": status,
        },
        update_modified=False,
    )

    # Handle Partial Payment Workflow
    if status == "Partly Paid":
        # Create To-Do for Execution Manager: "Advance Partially Paid – Execution Approval Required"
        description = _(
            "Advance Partially Paid (Outstanding: {0}). Execution Approval Required."
        ).format(
            frappe.utils.fmt_money(
                invoice.outstanding_amount, currency=invoice.currency
            )
        )
        assign_todo_to_execution_managers(
            "Advance Partially Paid – Execution Approval Required",
            description,
            "Job File",
            job_file_name,
        )

    # Handle Full Payment Workflow
    if status == "Paid":
        # Close "Collect Advance Payment" To-Do
        todos = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": "Sales Invoice",
                "reference_name": invoice_name,
                "status": "Open",
                "description": ["like", "%Collect Advance Payment%"],
            },
        )
        for todo in todos:
            frappe.db.set_value("ToDo", todo.name, "status", "Closed")


# ============================================================================
# SCHEDULED TASKS (DAILY)
# ============================================================================


def check_advance_payments_daily():
    """
    Daily check for Advance Payment compliance:
    1. Check if Advance Invoice exists for active Sales Orders. If not, create it.
    2. If Invoice exists but is unpaid and overdue, mark To-Do as overdue (logic handles this via date field).
    """
    # 1. Get all Open Sales Orders that should have Advance Invoice
    sales_orders = frappe.get_all(
        "Sales Order",
        filters={"status": ["in", ["To Deliver", "To Bill"]]},
        fields=[
            "name",
            "payment_terms_template",
            "custom_advance_invoice",
            "customer",
            "grand_total",
            "company",
            "currency",
        ],
    )

    for so in sales_orders:
        if not so.custom_advance_invoice:
            # Check if Payment Terms requires advance
            if so.payment_terms_template:
                payment_terms = frappe.get_all(
                    "Payment Terms Template Detail",
                    filters={"parent": so.payment_terms_template},
                    fields=["invoice_portion", "description"],
                    order_by="idx asc",
                    limit=1,
                )
                if (
                    payment_terms
                    and payment_terms[0].description
                    and "Advance" in payment_terms[0].description
                ):  # Heuristic check or just assume first term is advance
                    # Create missing invoice
                    frappe.log_error(
                        f"Missing Advance Invoice for SO {so.name}. Auto-creating.",
                        "Daily Scheduler",
                    )
                    doc = frappe.get_doc("Sales Order", so.name)
                    create_advance_invoice(doc)
