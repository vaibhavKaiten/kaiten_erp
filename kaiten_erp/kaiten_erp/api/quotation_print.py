# Copyright (c) 2026, Kaiten Software
# Solar Quotation Print Format - Data helpers
# Used by the Jinja print format template

import frappe
from frappe.utils import flt, fmt_money


@frappe.whitelist()
def get_quotation_bom_data(quotation_name):
    """
    Fetch BOM items for all items in a Quotation.
    For each item in the quotation's items table, find its active BOM
    and return the flattened BOM components with make/brand and warranty.

    Returns a dict with:
      - bom_rows: list of BOM component rows (item_name, description, brand, warranty, qty, uom)
      - commercial_rows: list of commercial offer rows (item_name, amount, percentage)
      - project_estimates: computed project estimate values
      - subsidy_amount: computed subsidy
    """
    doc = frappe.get_doc("Quotation", quotation_name)
    return _build_print_data(doc)


def get_quotation_print_data(doc):
    """
    Jinja-callable helper. Accepts a Quotation doc object.
    Returns the same structure as get_quotation_bom_data.
    """
    return _build_print_data(doc)


def _build_print_data(doc):
    """Core logic to build all print data from a Quotation doc."""
    from kaiten_erp.kaiten_erp.api.technical_survey_bom import (
        find_active_bom,
        get_flattened_items,
    )

    bom_rows = []
    commercial_rows = []
    total_pre_gst = flt(doc.net_total or 0)

    # ── BOM Section ──────────────────────────────────────────────────────────
    # For each item in the quotation, expand its BOM
    for idx, item in enumerate(doc.items or []):
        item_code = item.item_code
        if not item_code:
            continue

        bom_name = find_active_bom(item_code)
        if not bom_name:
            # No BOM — show the item itself as a single row
            item_doc = frappe.get_doc("Item", item_code, ignore_permissions=True)
            bom_rows.append({
                "s_no": len(bom_rows) + 1,
                "item_name": item_doc.item_name or item_code,
                "description": item_doc.description or "",
                "brand": item_doc.brand or "Standard",
                "warranty": _get_item_warranty(item_doc),
                "qty": flt(item.qty),
                "uom": item.uom or item_doc.stock_uom or "Nos.",
                "rate": flt(item.rate),
                "amount": flt(item.amount),
            })
            continue

        flat_items = get_flattened_items(bom_name)
        for comp in flat_items:
            comp_item_doc = frappe.get_doc(
                "Item", comp["item_code"], ignore_permissions=True
            )
            bom_rows.append({
                "s_no": len(bom_rows) + 1,
                "item_name": comp_item_doc.item_name or comp["item_code"],
                "description": comp.get("description") or comp_item_doc.description or "",
                "brand": comp_item_doc.brand or "Standard",
                "warranty": _get_item_warranty(comp_item_doc),
                "qty": flt(comp.get("qty", 1)),
                "uom": comp.get("uom") or comp_item_doc.stock_uom or "Nos.",
                "rate": flt(comp.get("rate", 0)),
                "amount": flt(comp.get("amount", 0)),
            })

    # ── Commercial Offer Section ──────────────────────────────────────────────
    # Show each quotation item with its percentage breakdown
    # Percentages: Panels+Inverter+Battery = 70%, Structure+Wiring = 20%, Installation = 10%
    for item in doc.items or []:
        item_code = item.item_code
        if not item_code:
            continue
        item_doc = frappe.get_doc("Item", item_code, ignore_permissions=True)
        item_amount = flt(item.amount)

        # Breakdown rows for this item
        panels_amount = round(item_amount * 0.70, 2)
        structure_amount = round(item_amount * 0.20, 2)
        installation_amount = round(item_amount * 0.10, 2)

        commercial_rows.append({
            "item_name": item_doc.item_name or item_code,
            "item_amount": item_amount,
            "panels_amount": panels_amount,
            "structure_amount": structure_amount,
            "installation_amount": installation_amount,
        })

    # ── Project Estimates ─────────────────────────────────────────────────────
    project_estimates = _compute_project_estimates(doc, total_pre_gst)

    # ── Subsidy ───────────────────────────────────────────────────────────────
    subsidy = _compute_subsidy(doc)

    return {
        "bom_rows": bom_rows,
        "commercial_rows": commercial_rows,
        "project_estimates": project_estimates,
        "subsidy_amount": subsidy,
        "net_total": total_pre_gst,
        "grand_total": flt(doc.grand_total or 0),
        "net_payable": flt(doc.grand_total or 0) - subsidy,
    }


def _get_item_warranty(item_doc):
    """
    Extract warranty info from an Item doc.
    Checks custom_warranty field first, then warranty_period, then description.
    """
    # Try custom warranty field (if exists)
    if hasattr(item_doc, "custom_warranty") and item_doc.custom_warranty:
        return item_doc.custom_warranty
    if hasattr(item_doc, "warranty_period") and item_doc.warranty_period:
        return f"{item_doc.warranty_period} Months"
    # Fallback: check item group for standard warranties
    group = (item_doc.item_group or "").lower()
    if "panel" in group:
        return "Product: 10-12 Yrs | Performance: 25 Yrs"
    if "inverter" in group:
        return "5 Years"
    if "battery" in group or "batteries" in group:
        return "5 Years"
    if "structure" in group or "mounting" in group:
        return "7 Years"
    if "cable" in group or "wire" in group:
        return "3 Years"
    return "As per Manufacturer"


def _compute_project_estimates(doc, total_pre_gst):
    """
    Compute project estimate values based on item capacity.
    Extracts KW from item name (e.g. '3KW' → 3).
    """
    from kaiten_erp.kaiten_erp.api.technical_survey_bom import find_active_bom, get_flattened_items
    import re

    # Determine system capacity from item name
    capacity_kw = 0
    system_name = ""
    panel_count = 0

    for item in doc.items or []:
        if item.item_code:
            item_doc = frappe.get_doc("Item", item.item_code, ignore_permissions=True)
            system_name = item_doc.item_name or item.item_code

            # Extract KW from item name e.g. "3KW On Grid", "5 KW Hybrid"
            match = re.search(r"(\d+(?:\.\d+)?)\s*[Kk][Ww]", system_name)
            if match:
                capacity_kw = flt(match.group(1))

            # Count panels from BOM
            bom_name = find_active_bom(item.item_code)
            if bom_name:
                flat = get_flattened_items(bom_name)
                for comp in flat:
                    comp_doc = frappe.get_doc("Item", comp["item_code"], ignore_permissions=True)
                    if (comp_doc.item_group or "").lower() in ["panel", "panels"]:
                        panel_count += flt(comp.get("qty", 0))

    if not capacity_kw:
        capacity_kw = 3  # default fallback

    # Calculations
    daily_gen = capacity_kw * 4          # 4 peak sun hours
    monthly_gen = capacity_kw * 30
    yearly_gen = capacity_kw * 12 * 30   # = monthly * 12

    # Subsidy
    subsidy = _compute_subsidy_from_kw(capacity_kw)

    # Annual saving @ ₹8/unit
    annual_saving = yearly_gen * 8

    # Final price after subsidy
    final_price = flt(doc.grand_total or 0) - subsidy

    # Payback period
    payback = round(final_price / annual_saving, 1) if annual_saving else 0

    # 25-year lifetime saving
    lifetime_saving = annual_saving * 25

    # Rooftop space: 4 sq ft per panel
    rooftop_space = panel_count * 4 if panel_count else capacity_kw * 100

    return {
        "system_capacity": f"{capacity_kw} KW",
        "system_name": system_name,
        "capacity_kw": capacity_kw,
        "daily_generation": f"{int(daily_gen)} Units/Day",
        "monthly_generation": f"{int(monthly_gen)} Units/Month",
        "yearly_generation": f"{int(yearly_gen)} Units/Year",
        "annual_saving": annual_saving,
        "annual_saving_fmt": f"₹ {int(annual_saving):,}",
        "payback_period": f"~{payback} Years",
        "lifetime_saving": lifetime_saving,
        "lifetime_saving_fmt": f"₹ {int(lifetime_saving):,}+",
        "rooftop_space": f"~{int(rooftop_space)} Sq. Ft.",
        "panel_count": int(panel_count),
    }


def _compute_subsidy(doc):
    """Compute subsidy from quotation items."""
    import re
    for item in doc.items or []:
        if item.item_code:
            item_doc = frappe.get_doc("Item", item.item_code, ignore_permissions=True)
            match = re.search(r"(\d+(?:\.\d+)?)\s*[Kk][Ww]", item_doc.item_name or "")
            if match:
                return _compute_subsidy_from_kw(flt(match.group(1)))
    return 78000  # default 3KW subsidy


def _compute_subsidy_from_kw(capacity_kw):
    """
    PM Surya Ghar subsidy:
    - 1 KW = ₹30,000
    - 2 KW = ₹60,000
    - 3 KW and above = ₹78,000
    """
    if capacity_kw <= 1:
        return 30000
    elif capacity_kw <= 2:
        return 60000
    else:
        return 78000
