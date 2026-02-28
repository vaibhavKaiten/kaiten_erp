# Copyright (c) 2025, KaitenSoftware
# Purchase Order GST Hook - Sets item-wise GST rates from Item Tax Templates
# Works WITH India Compliance to ensure mixed rates (5% and 18%) display correctly

import frappe
from frappe import _
from frappe.utils import flt
import json


def apply_item_wise_taxes(doc, method):
    """
    Apply item-wise GST rates from Item Tax Templates to Purchase Order items.
    This sets cgst_rate, sgst_rate, igst_rate on each item row.
    Called on validate of Purchase Order.
    """
    if not doc.items:
        return
    
    # Determine if intra-state or inter-state
    place_of_supply = doc.get("place_of_supply") or ""
    is_intra_state = place_of_supply.startswith("08")  # 08 = Rajasthan
    
    # For each item, get the correct GST rate from Item Tax Template
    for item in doc.items:
        item_code = item.item_code
        
        # Get Item Tax Template from item master
        item_doc = frappe.get_cached_doc("Item", item_code)
        
        if not item_doc.taxes:
            continue
        
        template_name = item_doc.taxes[0].item_tax_template
        if not template_name:
            continue
        
        # Get tax rates from template
        template = frappe.get_cached_doc("Item Tax Template", template_name)
        
        cgst_rate = 0
        sgst_rate = 0
        igst_rate = 0
        
        for tax in template.taxes:
            tax_type = tax.tax_type
            rate = flt(tax.tax_rate)
            
            # Only consider Input taxes for purchase
            if "Input" not in tax_type or "RCM" in tax_type:
                continue
            
            if "CGST" in tax_type:
                cgst_rate = rate
            elif "SGST" in tax_type:
                sgst_rate = rate
            elif "IGST" in tax_type:
                igst_rate = rate
        
        # Set rates on the item row
        # These fields are added by India Compliance
        base_amount = flt(item.base_net_amount) or flt(item.amount)
        
        if is_intra_state:
            item.cgst_rate = cgst_rate
            item.sgst_rate = sgst_rate
            item.cgst_amount = flt(base_amount * cgst_rate / 100, 2)
            item.sgst_amount = flt(base_amount * sgst_rate / 100, 2)
            item.igst_rate = 0
            item.igst_amount = 0
        else:
            item.igst_rate = igst_rate
            item.igst_amount = flt(base_amount * igst_rate / 100, 2)
            item.cgst_rate = 0
            item.sgst_rate = 0
            item.cgst_amount = 0
            item.sgst_amount = 0
        
        # Also set item_tax_template on the PO item
        if not item.get("item_tax_template"):
            item.item_tax_template = template_name
        
        # Set item_tax_rate for ERPNext core tax calculation
        item_tax_rate = {}
        for tax in template.taxes:
            item_tax_rate[tax.tax_type] = flt(tax.tax_rate)
        item.item_tax_rate = json.dumps(item_tax_rate)
    
    # Update taxes table with item_wise_tax_detail
    if doc.taxes:
        update_taxes_with_item_wise_detail(doc)


def update_taxes_with_item_wise_detail(doc):
    """Update taxes table with item-wise breakdown"""
    for tax_row in doc.taxes:
        account = tax_row.account_head
        item_wise_tax_detail = {}
        total_tax = 0
        
        for item in doc.items:
            item_code = item.item_code
            base_amount = flt(item.base_net_amount) or flt(item.amount)
            
            # Get rate from item's item_tax_rate
            item_tax_rate = json.loads(item.item_tax_rate or "{}")
            
            if account in item_tax_rate:
                rate = flt(item_tax_rate[account])
            else:
                rate = flt(tax_row.rate)
            
            tax_amount = flt(base_amount * rate / 100, 2)
            item_wise_tax_detail[item_code] = [rate, tax_amount]
            total_tax += tax_amount
        
        tax_row.item_wise_tax_detail = json.dumps(item_wise_tax_detail)
        tax_row.tax_amount = total_tax
        
        # Recalculate base_tax_amount
        tax_row.base_tax_amount = total_tax


def get_item_tax_rate_for_account(item_code, account_head):
    """Get the tax rate for an item for a specific account head"""
    item_doc = frappe.get_cached_doc("Item", item_code)
    
    if not item_doc.taxes:
        return None
    
    template_name = item_doc.taxes[0].item_tax_template
    if not template_name:
        return None
    
    template = frappe.get_cached_doc("Item Tax Template", template_name)
    
    for tax in template.taxes:
        if tax.tax_type == account_head:
            return flt(tax.tax_rate)
    
    return None


@frappe.whitelist()
def get_item_tax_template_details(item_code):
    """Get tax rates from item's tax template"""
    item_doc = frappe.get_doc("Item", item_code)
    
    if not item_doc.taxes:
        return None
    
    template_name = item_doc.taxes[0].item_tax_template
    if not template_name:
        return None
    
    template = frappe.get_doc("Item Tax Template", template_name)
    
    rates = {}
    for tax in template.taxes:
        rates[tax.tax_type] = flt(tax.tax_rate)
    
    return {
        "template": template_name,
        "rates": rates
    }
