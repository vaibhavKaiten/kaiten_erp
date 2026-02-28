# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Sales Order event handlers for Technical Survey integration
"""

import frappe
from frappe import _


def validate(doc, method=None):
    """
    Sales Order validate hook
    Called before Sales Order is saved
    """
    enforce_final_approved_quotation_rule(doc)
    sync_links_from_source_quotation(doc)
    link_technical_survey_to_sales_order(doc)


def on_submit(doc, method=None):
    """
    Sales Order on_submit hook - Create Material Request from Technical Survey's System Configuration
    Called after Sales Order is submitted
    """
    create_material_request_from_technical_survey(doc)


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

    quotation_names = get_source_quotation_names(sales_order)
    if not quotation_names:
        frappe.throw(_("Sales Order can only be created from Final Approved Quotation."))

    for quotation_name in quotation_names:
        stage = frappe.db.get_value(
            "Quotation", quotation_name, "custom_quotation_stage"
        )
        if stage != "Final Approved":
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
        quotation_name = item.get("quotation")
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
                        "warehouse": sales_order.set_warehouse
                        or get_default_warehouse(),
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
                        "warehouse": sales_order.set_warehouse
                        or get_default_warehouse(),
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
                        "warehouse": sales_order.set_warehouse
                        or get_default_warehouse(),
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
                                "warehouse": sales_order.set_warehouse
                                or get_default_warehouse(),
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

    # Create Material Request
    material_request = frappe.get_doc(
        {
            "doctype": "Material Request",
            "material_request_type": "Material Transfer",
            "schedule_date": sales_order.delivery_date or frappe.utils.today(),
            "company": sales_order.company,
            "set_warehouse": sales_order.set_warehouse or get_default_warehouse(),
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
        _("Material Request {0} created successfully from Technical Survey {1}").format(
            material_request.name, technical_survey_name
        ),
        alert=True,
        indicator="green",
    )

    frappe.db.commit()


def get_default_warehouse():
    """
    Get default warehouse for the company

    Returns:
        str: Default warehouse name
    """
    # Try to get default warehouse from company settings
    default_warehouse = frappe.db.get_single_value(
        "Stock Settings", "default_warehouse"
    )

    if not default_warehouse:
        # Get any warehouse as fallback
        default_warehouse = frappe.db.get_value("Warehouse", {"disabled": 0}, "name")

    return default_warehouse
