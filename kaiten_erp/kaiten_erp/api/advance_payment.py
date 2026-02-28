# Copyright (c) 2025, KaitenSoftware
# Advance Payment API
# Handles creation of Payment Entry for advance payment from Sales Invoice

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime


@frappe.whitelist()
def create_advance_payment_entry(
    sales_invoice,
    amount,
    mode_of_payment,
    reference_no="",
    reference_date="",
    payment_term="",
    structured_amount=0,
    advance_percent=0
):
    """
    Create Payment Entry for advance payment from Sales Invoice
    
    Args:
        sales_invoice: Sales Invoice name
        amount: Amount received
        mode_of_payment: Mode of Payment
        reference_no: Reference/Cheque number
        reference_date: Reference date
        payment_term: Payment term name (for audit)
        structured_amount: System calculated advance amount
        advance_percent: Advance percentage from payment terms
    """
    # Validate
    si = frappe.get_doc("Sales Invoice", sales_invoice)
    
    if si.docstatus != 1:
        frappe.throw(_("Sales Invoice must be submitted"))
    
    if flt(amount) <= 0:
        frappe.throw(_("Amount must be greater than 0"))
    
    if flt(amount) > si.outstanding_amount:
        frappe.throw(
            _("Amount ({0}) cannot exceed outstanding amount ({1})").format(
                amount, si.outstanding_amount
            )
        )
    
    # Validate amount >= structured amount
    if flt(structured_amount) > 0 and flt(amount) < flt(structured_amount):
        frappe.throw(
            _("Advance Amount Received ({0}) must be >= Structured Advance Amount ({1})").format(
                amount, structured_amount
            )
        )
    
    # Get payment account from mode of payment
    payment_account = get_payment_account(mode_of_payment, si.company)
    
    # Create Payment Entry
    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": si.customer,
        "party_name": si.customer_name,
        "company": si.company,
        "posting_date": nowdate(),
        "mode_of_payment": mode_of_payment,
        "paid_amount": flt(amount),
        "received_amount": flt(amount),
        "paid_to": payment_account,
        "paid_to_account_currency": si.currency,
        "reference_no": reference_no,
        "reference_date": reference_date or nowdate(),
        "remarks": _("Advance Payment against {0}. Payment Term: {1}, Advance %: {2}").format(
            sales_invoice, payment_term or "N/A", advance_percent or "N/A"
        )
    })
    
    # Add reference to Sales Invoice
    pe.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": sales_invoice,
        "total_amount": si.grand_total,
        "outstanding_amount": si.outstanding_amount,
        "allocated_amount": flt(amount)
    })
    
    pe.flags.ignore_permissions = True
    pe.insert()
    
    # Log audit
    _log_advance_payment(
        sales_invoice,
        pe.name,
        payment_term,
        structured_amount,
        amount,
        advance_percent
    )
    
    return {
        "status": "success",
        "payment_entry": pe.name,
        "message": _("Payment Entry created successfully")
    }


def get_payment_account(mode_of_payment, company):
    """
    Get default payment account for mode of payment and company
    """
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode_of_payment, "company": company},
        "default_account"
    )
    
    if not account:
        # Fallback to company default receivable account
        account = frappe.db.get_value(
            "Company", company, "default_cash_account"
        ) or frappe.db.get_value(
            "Company", company, "default_bank_account"
        )
    
    if not account:
        frappe.throw(
            _("Please set default account for Mode of Payment {0} in company {1}").format(
                mode_of_payment, company
            )
        )
    
    return account


def _log_advance_payment(
    sales_invoice,
    payment_entry,
    payment_term,
    structured_amount,
    actual_amount,
    advance_percent
):
    """
    Log advance payment for audit
    """
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Sales Invoice",
        "reference_name": sales_invoice,
        "content": _("Advance Payment Entry {0} created. Payment Term: {1}, Advance %: {2}%, "
                     "Structured Amount: {3}, Actual Amount: {4}").format(
            payment_entry,
            payment_term or "N/A",
            advance_percent or "N/A",
            structured_amount,
            actual_amount
        )
    }).insert(ignore_permissions=True)
    
    # Also log on Payment Entry
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Payment Entry",
        "reference_name": payment_entry,
        "content": _("Created as Advance Payment for {0}. Payment Term: {1}, Advance %: {2}%").format(
            sales_invoice,
            payment_term or "N/A",
            advance_percent or "N/A"
        )
    }).insert(ignore_permissions=True)


@frappe.whitelist()
def get_advance_info_from_invoice(sales_invoice):
    """
    Get advance payment info from Sales Invoice payment schedule
    """
    si = frappe.get_doc("Sales Invoice", sales_invoice)
    
    advance_info = {
        "advance_percent": 0,
        "structured_amount": 0,
        "payment_term": None,
        "due_date": None,
        "grand_total": si.grand_total,
        "outstanding_amount": si.outstanding_amount
    }
    
    if si.payment_schedule:
        # Get first payment term (typically advance)
        first_term = si.payment_schedule[0]
        
        advance_info.update({
            "advance_percent": first_term.invoice_portion or 0,
            "structured_amount": first_term.payment_amount or (si.grand_total * (first_term.invoice_portion / 100)),
            "payment_term": first_term.payment_term,
            "due_date": str(first_term.due_date) if first_term.due_date else None
        })
    
    return advance_info


# =============================================================================
# QUOTATION ADVANCE PAYMENT FUNCTIONS
# =============================================================================

@frappe.whitelist()
def get_advance_info_from_quotation(quotation, payment_terms_template="payment procedure"):
    """
    Get advance payment info from Quotation using specified Payment Terms Template
    
    Args:
        quotation: Quotation name
        payment_terms_template: Name of Payment Terms Template (default: "payment procedure")
    """
    qt = frappe.get_doc("Quotation", quotation)
    
    advance_info = {
        "payment_terms_template": payment_terms_template,
        "advance_percent": 0,
        "structured_amount": 0,
        "payment_term": None,
        "grand_total": qt.grand_total,
        "customer": qt.party_name,
        "company": qt.company,
        "currency": qt.currency
    }
    
    # Fetch payment terms from template
    if not frappe.db.exists("Payment Terms Template", payment_terms_template):
        frappe.throw(
            _("Payment Terms Template '{0}' not found").format(payment_terms_template)
        )
    
    template = frappe.get_doc("Payment Terms Template", payment_terms_template)
    
    if template.terms and len(template.terms) > 0:
        # Get first term (typically advance)
        first_term = template.terms[0]
        
        advance_percent = flt(first_term.invoice_portion or first_term.payment_term_percentage or 0)
        structured_amount = flt(qt.grand_total) * (advance_percent / 100)
        
        advance_info.update({
            "advance_percent": advance_percent,
            "structured_amount": structured_amount,
            "payment_term": first_term.payment_term,
            "due_basis": first_term.due_date_based_on if hasattr(first_term, 'due_date_based_on') else None
        })
    
    return advance_info


@frappe.whitelist()
def create_advance_payment_from_quotation(
    quotation,
    amount,
    mode_of_payment,
    reference_no="",
    reference_date="",
    payment_term="",
    structured_amount=0,
    advance_percent=0
):
    """
    Create Payment Entry for advance payment from Quotation
    
    Args:
        quotation: Quotation name
        amount: Amount received
        mode_of_payment: Mode of Payment
        reference_no: Reference/Cheque number
        reference_date: Reference date
        payment_term: Payment term name (for audit)
        structured_amount: System calculated advance amount
        advance_percent: Advance percentage from payment terms
    """
    # Validate
    qt = frappe.get_doc("Quotation", quotation)
    
    if qt.docstatus != 1:
        frappe.throw(_("Quotation must be submitted"))
    
    if flt(amount) <= 0:
        frappe.throw(_("Amount must be greater than 0"))
    
    # Get customer from quotation
    customer = None
    customer_name = None
    
    if qt.quotation_to == "Customer":
        customer = qt.party_name
        customer_name = frappe.db.get_value("Customer", customer, "customer_name")
    else:
        # For Lead, try to find an existing Customer linked via Dynamic Link
        # or check if Lead was converted to Customer
        lead_name = qt.party_name
        
        # Check if a Customer exists with this Lead as reference
        customer = frappe.db.get_value(
            "Customer",
            {"lead_name": lead_name},
            "name"
        )
        
        if customer:
            customer_name = frappe.db.get_value("Customer", customer, "customer_name")
        else:
            # No customer found - need to convert Lead first
            frappe.throw(
                _("No Customer found for Lead '{0}'. Please convert the Lead to Customer first.").format(lead_name)
            )
    
    # Get payment account from mode of payment
    payment_account = get_payment_account(mode_of_payment, qt.company)
    
    # Create Payment Entry (unlinked - advance)
    pe = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "party_type": "Customer",
        "party": customer,
        "company": qt.company,
        "posting_date": nowdate(),
        "mode_of_payment": mode_of_payment,
        "paid_amount": flt(amount),
        "received_amount": flt(amount),
        "paid_to": payment_account,
        "paid_to_account_currency": qt.currency,
        "reference_no": reference_no,
        "reference_date": reference_date or nowdate(),
        "custom_quotation": quotation,  # Link to quotation for status update on submit
        "remarks": _("Advance Payment against Quotation {0}. Payment Term: {1}, Advance %: {2}%").format(
            quotation, payment_term or "N/A", advance_percent or "N/A"
        )
    })
    
    pe.flags.ignore_permissions = True
    pe.insert()
    
    # Log audit on Quotation
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Quotation",
        "reference_name": quotation,
        "content": _("Advance Payment Entry {0} created. Payment Term: {1}, Advance %: {2}%, "
                     "Structured Amount: {3}, Actual Amount: {4}").format(
            pe.name,
            payment_term or "N/A",
            advance_percent or "N/A",
            structured_amount,
            amount
        )
    }).insert(ignore_permissions=True)
    
    # Log on Payment Entry
    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Payment Entry",
        "reference_name": pe.name,
        "content": _("Created as Advance Payment for Quotation {0}. Payment Term: {1}, Advance %: {2}%").format(
            quotation,
            payment_term or "N/A",
            advance_percent or "N/A"
        )
    }).insert(ignore_permissions=True)
    
    return {
        "status": "success",
        "payment_entry": pe.name,
        "message": _("Payment Entry created successfully")
    }


# =============================================================================
# PAYMENT ENTRY SUBMIT HOOK
# Changes quotation status to Advance Approved when Payment Entry is submitted
# =============================================================================

def on_payment_entry_submit(doc, method):
    """
    Called when Payment Entry is submitted
    If linked to a quotation, changes quotation status to Advance Approved
    """
    # Check if this Payment Entry has a linked quotation
    quotation = None
    
    # Try to get from custom field first
    if hasattr(doc, 'custom_quotation') and doc.custom_quotation:
        quotation = doc.custom_quotation
    
    # Fallback: check remarks for quotation reference
    if not quotation and doc.remarks and "Quotation" in doc.remarks:
        import re
        match = re.search(r'Quotation ([A-Z]+-[A-Z]+-\d+-\d+)', doc.remarks)
        if match:
            quotation = match.group(1)
    
    if quotation and frappe.db.exists("Quotation", quotation):
        current_status = frappe.db.get_value("Quotation", quotation, "custom_quotation_status")
        
        # Only update if status is Submitted
        if current_status == "Submitted":
            frappe.db.set_value(
                "Quotation", quotation, 
                "custom_quotation_status", "Advance Approved", 
                update_modified=False
            )
            
            # Log the action
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Quotation",
                "reference_name": quotation,
                "content": _("Status changed to 'Advance Approved' after Payment Entry {0} was submitted").format(doc.name)
            }).insert(ignore_permissions=True)


