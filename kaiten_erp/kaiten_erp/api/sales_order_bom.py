# Copyright (c) 2025, Kaiten Erp
# Sales Order creation from Quotation with Technical Survey BOM integration
# Overrides standard make_sales_order to fetch item and BOM from approved Technical Survey

import frappe
from frappe import _
from frappe.utils import nowdate, flt


@frappe.whitelist()
def make_sales_order_from_quotation(source_name, target_doc=None):
    """
    Create Sales Order from Quotation with BOM from approved Technical Survey

    Overrides standard make_sales_order to:
    1. Validate Quotation status is "Advance Approved"
    2. Fetch linked Technical Survey
    3. Get system/product from Technical Survey
    4. Get BOM components from Technical Survey
    5. Create Sales Order with BOM snapshot
    """

    # Get the quotation
    quotation = frappe.get_doc("Quotation", source_name)

    # Validate quotation status
    if quotation.custom_quotation_status != "Advance Approved":
        frappe.throw(
            _(
                "Sales Order can only be created when Quotation status is 'Advance Approved'. Current status: {0}"
            ).format(quotation.custom_quotation_status)
        )

    # Find linked Technical Survey
    technical_survey = get_approved_technical_survey(quotation)

    if not technical_survey:
        frappe.throw(
            _(
                "No Approved Technical Survey found for this Quotation. Please ensure a Technical Survey is approved before creating Sales Order."
            )
        )

    # Get customer
    customer = get_customer_from_quotation(quotation)
    if not customer:
        frappe.throw(
            _(
                "No Customer linked to this Quotation. Please convert Lead to Customer first."
            )
        )

    # Get system item from Technical Survey
    system_item = get_system_item_from_survey(technical_survey)

    # Get BOM components from Technical Survey
    bom_components = get_bom_from_survey(technical_survey)

    # Create Sales Order
    sales_order = create_sales_order(
        quotation=quotation,
        customer=customer,
        technical_survey=technical_survey,
        system_item=system_item,
        bom_components=bom_components,
    )

    # Log audit
    log_sales_order_creation(sales_order, quotation, technical_survey, bom_components)

    return sales_order


def get_approved_technical_survey(quotation):
    """Find the approved Technical Survey linked to this Quotation"""

    # First check if quotation has direct link to Technical Survey
    if quotation.get("custom_technical_survey"):
        survey = frappe.get_doc("Technical Survey", quotation.custom_technical_survey)
        if survey.status == "Approved":
            return survey

    # Otherwise, find via Lead
    lead = quotation.party_name if quotation.quotation_to == "Lead" else None

    if not lead:
        # Try to get lead from customer
        customer = (
            quotation.party_name if quotation.quotation_to == "Customer" else None
        )
        if customer:
            lead = frappe.db.get_value("Customer", customer, "lead_name")

    if lead:
        # Find approved Technical Survey for this Lead
        survey_name = frappe.db.get_value(
            "Technical Survey",
            {"lead": lead, "status": "Approved"},
            "name",
            order_by="creation desc",
        )
        if survey_name:
            return frappe.get_doc("Technical Survey", survey_name)

    return None


def get_customer_from_quotation(quotation):
    """Get customer from quotation"""
    if quotation.quotation_to == "Customer":
        return quotation.party_name

    # For Lead, find linked Customer
    lead_name = quotation.party_name
    customer = frappe.db.get_value("Customer", {"lead_name": lead_name}, "name")
    return customer


def get_system_item_from_survey(technical_survey):
    """Get the main system/package item from Technical Survey"""

    # Try different fields where system might be stored
    system_item = (
        technical_survey.get("proposed_system")
        or technical_survey.get("custom_proposed_system")
        or technical_survey.get("inverter_item")  # Fallback
    )

    if not system_item:
        frappe.throw(
            _(
                "No system/package item found in Technical Survey {0}. Please select a Proposed System."
            ).format(technical_survey.name)
        )

    return system_item


def get_bom_from_survey(technical_survey):
    """Get all BOM components from Technical Survey"""

    bom_components = []

    # 1. Add Panel
    if technical_survey.get("selected_panel") or technical_survey.get(
        "custom_selected_panel"
    ):
        panel = technical_survey.get("selected_panel") or technical_survey.get(
            "custom_selected_panel"
        )
        qty = (
            technical_survey.get("panel_qty_from_bom")
            or technical_survey.get("custom_panel_qty_from_bom")
            or 1
        )
        bom_components.append(
            {"item_code": panel, "qty": flt(qty), "item_type": "Panel", "source_idx": 1}
        )

    # 2. Add Inverter
    if technical_survey.get("selected_inverter") or technical_survey.get(
        "custom_selected_inverter"
    ):
        inverter = technical_survey.get("selected_inverter") or technical_survey.get(
            "custom_selected_inverter"
        )
        qty = (
            technical_survey.get("inverter_qty_from_bom")
            or technical_survey.get("custom_inverter_qty_from_bom")
            or 1
        )
        bom_components.append(
            {
                "item_code": inverter,
                "qty": flt(qty),
                "item_type": "Inverter",
                "source_idx": 2,
            }
        )

    # 3. Add Battery (if exists)
    if technical_survey.get("selected_battery"):
        battery = technical_survey.get("selected_battery")
        qty = technical_survey.get("battery_qty_from_bom") or 1
        bom_components.append(
            {
                "item_code": battery,
                "qty": flt(qty),
                "item_type": "Battery",
                "source_idx": 3,
            }
        )

    # 4. Add Other BOM Items from child table
    if technical_survey.get("bom_other_items"):
        for idx, item in enumerate(technical_survey.bom_other_items):
            if item.item:
                bom_components.append(
                    {
                        "item_code": item.item,
                        "qty": flt(item.qty) or 1,
                        "item_type": "Other",
                        "source_idx": 100 + idx,
                    }
                )

    return bom_components


def create_sales_order(
    quotation, customer, technical_survey, system_item, bom_components
):
    """Create the Sales Order with only the proposed system item (no BOM details)"""

    # Get item details for the system
    item_details = (
        frappe.db.get_value(
            "Item",
            system_item,
            ["item_name", "description", "stock_uom", "item_group"],
            as_dict=True,
        )
        or {}
    )

    # Get rate from quotation item (which has negotiable_mrp from Lead)
    rate = 0
    if quotation.items:
        # Use rate from quotation (negotiable_mrp)
        rate = quotation.items[0].rate if quotation.items else 0

    if not rate:
        rate = (
            frappe.db.get_value(
                "Item Price",
                {"item_code": system_item, "selling": 1},
                "price_list_rate",
            )
            or 0
        )

    # Create Sales Order with ONLY the proposed_system item
    so = frappe.get_doc(
        {
            "doctype": "Sales Order",
            "customer": customer,
            "company": quotation.company,
            "transaction_date": nowdate(),
            "delivery_date": frappe.utils.add_days(nowdate(), 30),
            "order_type": "Sales",
            "currency": quotation.currency,
            "selling_price_list": quotation.selling_price_list,
            "custom_technical_survey": technical_survey.name,
            "items": [
                {
                    "item_code": system_item,
                    "item_name": item_details.get("item_name") or system_item,
                    "description": item_details.get("description") or "",
                    "qty": 1,
                    "rate": rate,
                    "uom": item_details.get("stock_uom") or "Nos",
                    "delivery_date": frappe.utils.add_days(nowdate(), 30),
                }
            ],
        }
    )

    # NOTE: We do NOT populate custom_bom_items table
    # Material Request will fetch detailed items directly from Technical Survey System Configuration

    so.flags.ignore_permissions = True
    so.insert()

    # Add connection link between Sales Order and Technical Survey
    so.add_link("Technical Survey", technical_survey.name, "Sales Order")

    # Update quotation with link to Sales Order
    frappe.db.set_value("Quotation", quotation.name, "custom_sales_order", so.name)

    return so


def log_sales_order_creation(sales_order, quotation, technical_survey, bom_components):
    """Log audit trail for Sales Order creation"""

    # Log on Sales Order
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Sales Order",
            "reference_name": sales_order.name,
            "content": _(
                "Sales Order created from Quotation {0}. "
                "Linked to Technical Survey {1}. "
                "Material Request will fetch detailed BOM from Technical Survey System Configuration."
            ).format(quotation.name, technical_survey.name),
        }
    ).insert(ignore_permissions=True)

    # Log on Quotation
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Quotation",
            "reference_name": quotation.name,
            "content": _(
                "Sales Order {0} created and linked to Technical Survey {1}."
            ).format(sales_order.name, technical_survey.name),
        }
    ).insert(ignore_permissions=True)

    # Log on Technical Survey
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Technical Survey",
            "reference_name": technical_survey.name,
            "content": _(
                "Sales Order {0} created. System Configuration will be used for Material Request."
            ).format(sales_order.name),
        }
    ).insert(ignore_permissions=True)


@frappe.whitelist()
def check_can_make_sales_order(quotation_name):
    """Check if Sales Order can be created from this Quotation"""

    quotation = frappe.get_doc("Quotation", quotation_name)

    result = {"can_create": False, "message": "", "technical_survey": None}

    # Check status
    if quotation.custom_quotation_status != "Advance Approved":
        result["message"] = _(
            "Quotation status must be 'Advance Approved' to create Sales Order. Current: {0}"
        ).format(quotation.custom_quotation_status or "Not set")
        return result

    # Check Technical Survey
    technical_survey = get_approved_technical_survey(quotation)
    if not technical_survey:
        result["message"] = _("No Approved Technical Survey found for this Quotation.")
        return result

    result["can_create"] = True
    result["technical_survey"] = technical_survey.name
    result["message"] = _("Ready to create Sales Order")

    return result
