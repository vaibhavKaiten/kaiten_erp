# Copyright (c) 2025, KaitenSoftware and contributors
# BOM Stock Reservation API
# Handles automatic reservation of BOM materials on Sales Order submission
# Auto-creates Material Request for shortage items instead of blocking submission

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime, add_days


# =============================================================================
# MAIN ENTRY POINTS (Called from hooks)
# =============================================================================


def on_sales_order_submit(doc, method):
    """
    Called when Sales Order is submitted
    Reserves BOM materials for each SO item
    Creates Material Request for shortages instead of blocking
    """
    # Skip if not applicable
    if not should_reserve_stock(doc):
        return

    try:
        result = process_stock_reservation(doc)

        if result["fully_available"]:
            # Case A: All stock available - mark as Confirmed
            frappe.db.set_value(
                "Sales Order",
                doc.name,
                "custom_procurement_status",
                "Confirmed",
                update_modified=False,
            )
            _log_so_action(
                doc.name,
                "Stock Reserved",
                f"All BOM materials reserved. {len(result['reserved_items'])} items.",
            )
        else:
            # Case B: Shortages exist - mark as Pending Procurement
            frappe.db.set_value(
                "Sales Order",
                doc.name,
                "custom_procurement_status",
                "Pending Procurement",
                update_modified=False,
            )

            # Create Material Request for shortages
            mr = create_material_request_for_shortages(doc, result["shortage_items"])

            if mr:
                frappe.db.set_value(
                    "Sales Order",
                    doc.name,
                    "custom_linked_material_request",
                    mr.name,
                    update_modified=False,
                )

                # Create shortage logs for audit
                create_shortage_logs(doc, result["shortage_items"], mr.name)

                _log_so_action(
                    doc.name,
                    "Pending Procurement",
                    f"Material Request {mr.name} created for {len(result['shortage_items'])} shortage items.",
                )

        # Mark SO as having reservations
        frappe.db.set_value(
            "Sales Order", doc.name, "custom_stock_reserved", 1, update_modified=False
        )
        frappe.db.set_value(
            "Sales Order",
            doc.name,
            "custom_reservation_timestamp",
            now_datetime(),
            update_modified=False,
        )

    except Exception as e:
        frappe.log_error(
            title=_("Stock Reservation Failed"),
            message=f"Failed to process stock for Sales Order {doc.name}: {str(e)}",
        )
        frappe.throw(
            _(
                "Failed to process stock reservation. Please check error logs. Error: {0}"
            ).format(str(e)),
            title=_("Reservation Error"),
        )


def on_sales_order_cancel(doc, method):
    """
    Called when Sales Order is cancelled
    Releases all reservations linked to this SO
    """
    from kaiten_erp.kaiten_erp.doctype.stock_reservation_log.stock_reservation_log import (
        release_reservations_for_sales_order,
    )

    count = release_reservations_for_sales_order(doc.name, "Sales Order Cancelled")

    if count:
        _log_so_action(
            doc.name, "Reservations Released", f"Released {count} reservations"
        )


def on_delivery_submit(doc, method):
    """
    Called when Delivery Note is submitted
    Converts reservations to consumed
    """
    # Get linked Sales Order(s)
    sales_orders = set()
    for item in doc.items:
        if item.against_sales_order:
            sales_orders.add(item.against_sales_order)

    for so in sales_orders:
        consume_reservations_for_delivery(so, doc.name, doc.items)


def on_purchase_receipt_submit(doc, method):
    """
    Called when Purchase Receipt is submitted
    Updates pending reservations when new stock arrives from SO-linked MR
    """
    try:
        update_reservations_from_purchase_receipt(doc)
    except Exception as e:
        frappe.log_error(
            title=_("Purchase Receipt Reservation Update Failed"),
            message=f"Failed to update reservations from PR {doc.name}: {str(e)}",
        )


# =============================================================================
# CORE RESERVATION LOGIC
# =============================================================================


def should_reserve_stock(sales_order_doc):
    """
    Check if stock should be reserved for this Sales Order
    """
    # Only reserve if we have items
    if not sales_order_doc.items:
        return False

    return True


def process_stock_reservation(sales_order_doc):
    """
    Main reservation function - returns stock status without blocking

    Returns:
        dict: {
            "fully_available": bool,
            "reserved_items": list,
            "shortage_items": list
        }
    """
    from kaiten_erp.kaiten_erp.doctype.stock_reservation_log.stock_reservation_log import (
        create_reservation_log,
        get_available_qty,
    )

    result = {"fully_available": True, "reserved_items": [], "shortage_items": []}

    # Get BOM items from custom_bom_items child table (snapshot from Technical Survey)
    bom_items = get_bom_items_from_sales_order(sales_order_doc)

    if not bom_items:
        # Fallback to traditional BOM explosion
        bom_items = get_bom_items_traditional(sales_order_doc)

    # Get Technical Survey reference
    technical_survey = sales_order_doc.get("custom_technical_survey")

    # Default warehouse
    default_warehouse = get_default_warehouse()

    # Check stock for each BOM item
    for item in bom_items:
        item_code = item.get("item_code")
        required_qty = flt(item.get("qty") or item.get("required_qty"))
        warehouse = item.get("warehouse") or default_warehouse

        if not item_code or not required_qty:
            continue

        # Get available stock
        available_qty = get_available_qty(item_code, warehouse)

        if available_qty >= required_qty:
            # Fully available - create full reservation
            res_data = {
                "sales_order": sales_order_doc.name,
                "sales_order_item": item.get("name") or item.get("item_code"),
                "quotation": sales_order_doc.get("custom_quotation"),
                "technical_survey": technical_survey,
                "bom": item.get("bom"),
                "customer": sales_order_doc.customer,
                "item_code": item_code,
                "warehouse": warehouse,
                "required_qty": required_qty,
                "reserved_qty": required_qty,
                "available_qty": available_qty,
            }
            create_reservation_log(res_data)
            result["reserved_items"].append(res_data)
        else:
            # Shortage exists
            result["fully_available"] = False
            shortage_qty = required_qty - max(0, available_qty)

            shortage_data = {
                "sales_order": sales_order_doc.name,
                "sales_order_item": item.get("name") or item.get("item_code"),
                "quotation": sales_order_doc.get("custom_quotation"),
                "technical_survey": technical_survey,
                "bom": item.get("bom"),
                "customer": sales_order_doc.customer,
                "item_code": item_code,
                "item_name": item.get("item_name")
                or frappe.db.get_value("Item", item_code, "item_name"),
                "warehouse": warehouse,
                "required_qty": required_qty,
                "available_qty": available_qty,
                "shortage_qty": shortage_qty,
                "reserved_qty": max(0, available_qty),  # Reserve whatever is available
            }

            # Create partial reservation if some stock is available
            if available_qty > 0:
                res_data = {**shortage_data, "reserved_qty": available_qty}
                log = create_reservation_log(res_data)
                log.status = "Partially Reserved"
                log.save(ignore_permissions=True)

            result["shortage_items"].append(shortage_data)

    frappe.db.commit()
    return result


def get_bom_items_from_sales_order(sales_order_doc):
    """
    Get BOM items from the Technical Survey System Configuration
    This is the source of truth for material procurement
    """
    bom_items = []

    # Get linked Technical Survey
    technical_survey_name = sales_order_doc.get("custom_technical_survey")

    if not technical_survey_name:
        # Fallback to traditional BOM explosion if no Technical Survey linked
        frappe.log_error(
            title="No Technical Survey Linked",
            message=f"Sales Order {sales_order_doc.name} has no linked Technical Survey. Using traditional BOM.",
        )
        return get_bom_items_traditional(sales_order_doc)

    # Fetch items from Technical Survey System Configuration
    bom_items = get_bom_items_from_technical_survey(technical_survey_name)

    return bom_items


def get_bom_items_from_technical_survey(technical_survey_name):
    """
    Fetch detailed BOM items from Technical Survey System Configuration

    Returns list of items with structure:
    [
        {"item_code": "...", "qty": ..., "item_type": "Panel", "warehouse": ...},
        {"item_code": "...", "qty": ..., "item_type": "Inverter", "warehouse": ...},
        ...
    ]
    """
    bom_items = []

    # Get Technical Survey document
    try:
        ts = frappe.get_doc("Technical Survey", technical_survey_name)
    except Exception as e:
        frappe.log_error(
            title="Technical Survey Not Found",
            message=f"Failed to fetch Technical Survey {technical_survey_name}: {str(e)}",
        )
        return []

    # Get default warehouse
    default_warehouse = get_default_warehouse()

    # 1. Add Panel (if exists)
    if ts.get("panel"):
        panel_qty = flt(ts.get("panel_qty_bom") or 0)
        if panel_qty > 0:
            bom_items.append(
                {
                    "item_code": ts.panel,
                    "item_name": frappe.db.get_value("Item", ts.panel, "item_name"),
                    "qty": panel_qty,
                    "warehouse": default_warehouse,
                    "item_type": "Panel",
                    "source_technical_survey": technical_survey_name,
                }
            )

    # 2. Add Inverter (if exists)
    if ts.get("inverter"):
        inverter_qty = flt(ts.get("inverter_qty_bom") or 0)
        if inverter_qty > 0:
            bom_items.append(
                {
                    "item_code": ts.inverter,
                    "item_name": frappe.db.get_value("Item", ts.inverter, "item_name"),
                    "qty": inverter_qty,
                    "warehouse": default_warehouse,
                    "item_type": "Inverter",
                    "source_technical_survey": technical_survey_name,
                }
            )

    # 3. Add Battery (if exists)
    if ts.get("battery"):
        battery_qty = flt(ts.get("battery_qty_bom") or 0)
        if battery_qty > 0:
            bom_items.append(
                {
                    "item_code": ts.battery,
                    "item_name": frappe.db.get_value("Item", ts.battery, "item_name"),
                    "qty": battery_qty,
                    "warehouse": default_warehouse,
                    "item_type": "Battery",
                    "source_technical_survey": technical_survey_name,
                }
            )

    # 4. Add Other BOM Items from child table (table_vctx)
    if ts.get("table_vctx"):
        for item_row in ts.table_vctx:
            if item_row.item_code and flt(item_row.qty or 0) > 0:
                bom_items.append(
                    {
                        "item_code": item_row.item_code,
                        "item_name": item_row.item_name
                        or frappe.db.get_value("Item", item_row.item_code, "item_name"),
                        "qty": flt(item_row.qty),
                        "warehouse": default_warehouse,
                        "item_type": "Other",
                        "source_technical_survey": technical_survey_name,
                    }
                )

    return bom_items


def get_bom_items_traditional(sales_order_doc):
    """
    Fallback: Get BOM items by tracing SO Item → Quotation → Technical Survey → BOM
    """
    bom_items = []

    for item in sales_order_doc.items:
        bom_info = get_bom_for_so_item(item, sales_order_doc)

        if not bom_info.get("bom"):
            # No BOM found, use the selling item itself
            bom_items.append(
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "qty": item.qty,
                    "warehouse": item.warehouse,
                    "bom": None,
                }
            )
        else:
            # Explode BOM and get components
            components = explode_bom(bom_info["bom"], item.qty)
            for comp in components:
                comp["bom"] = bom_info["bom"]
                bom_items.append(comp)

    return bom_items


def get_default_warehouse():
    """Get default warehouse from stock settings"""
    return frappe.db.get_single_value("Stock Settings", "default_warehouse") or None


def create_material_request_for_shortages(sales_order_doc, shortage_items):
    """
    Create a Material Transfer-type Material Request for shortage items
    Links to both Sales Order and Technical Survey
    """
    if not shortage_items:
        return None

    # Get delivery date from SO for schedule_date
    delivery_date = sales_order_doc.get("delivery_date") or add_days(nowdate(), 7)

    # Get Technical Survey reference
    technical_survey = sales_order_doc.get("custom_technical_survey")

    # Create Material Request
    mr = frappe.get_doc(
        {
            "doctype": "Material Request",
            "material_request_type": "Material Transfer",
            "schedule_date": delivery_date,
            "company": sales_order_doc.company,
            "custom_auto_generated": 1,
            "custom_source_sales_order": sales_order_doc.name,
            "custom_source_technical_survey": technical_survey,
            "custom_source_customer": sales_order_doc.customer,
            "items": [],
        }
    )

    # Add shortage items
    for item in shortage_items:
        mr.append(
            "items",
            {
                "item_code": item["item_code"],
                "item_name": item.get("item_name"),
                "qty": item["shortage_qty"],
                "warehouse": item["warehouse"],
                "schedule_date": delivery_date,
                "description": f"Auto-generated for Sales Order {sales_order_doc.name} from Technical Survey {technical_survey}",
            },
        )

    mr.flags.ignore_permissions = True
    # Set flag to skip advance payment validation during Sales Order submission
    # The advance invoice will be created AFTER this Material Request
    mr.flags.ignore_advance_validation = True
    mr.insert()

    # Auto-submit the Material Request
    mr.submit()

    frappe.msgprint(
        _(
            "Material Request {0} created for {1} shortage items from Technical Survey {2}"
        ).format(
            frappe.utils.get_link_to_form("Material Request", mr.name),
            len(shortage_items),
            technical_survey or "N/A",
        ),
        title=_("Procurement Initiated"),
        indicator="blue",
    )

    return mr


def create_shortage_logs(sales_order_doc, shortage_items, material_request):
    """Create Procurement Shortage Log entries for audit"""
    from kaiten_erp.kaiten_erp.doctype.procurement_shortage_log.procurement_shortage_log import (
        create_shortage_log,
    )

    for item in shortage_items:
        create_shortage_log(
            {
                "sales_order": sales_order_doc.name,
                "material_request": material_request,
                "technical_survey": sales_order_doc.get("custom_technical_survey"),
                "customer": sales_order_doc.customer,
                "project": sales_order_doc.get("project"),
                "item_code": item["item_code"],
                "warehouse": item["warehouse"],
                "required_qty": item["required_qty"],
                "available_qty": item["available_qty"],
                "shortage_qty": item["shortage_qty"],
            }
        )


def get_bom_for_so_item(so_item, sales_order_doc):
    """
    Trace: SO Item → Quotation → Technical Survey → BOM
    Returns dict with bom, quotation, technical_survey
    """
    result = {"bom": None, "quotation": None, "technical_survey": None}

    # Try to get quotation link from SO item or SO header
    quotation = so_item.get("prevdoc_docname") or sales_order_doc.get(
        "custom_quotation"
    )

    if quotation:
        result["quotation"] = quotation

        # Get Technical Survey from Quotation
        tech_survey = frappe.db.get_value(
            "Quotation", quotation, "custom_technical_survey"
        )

        if tech_survey:
            result["technical_survey"] = tech_survey

            # Get BOM from Technical Survey's proposed system
            proposed_system = frappe.db.get_value(
                "Technical Survey", tech_survey, "proposed_system"
            )

            if proposed_system:
                # Find active BOM for this item
                bom = frappe.db.get_value(
                    "BOM",
                    {"item": proposed_system, "is_active": 1, "is_default": 1},
                    "name",
                )
                if bom:
                    result["bom"] = bom

    # Fallback: check if item itself has a default BOM
    if not result["bom"]:
        bom = frappe.db.get_value(
            "BOM", {"item": so_item.item_code, "is_active": 1, "is_default": 1}, "name"
        )
        if bom:
            result["bom"] = bom

    return result


def explode_bom(bom_name, qty_multiplier=1):
    """
    Explode BOM to get all component items
    Returns list of {item_code, required_qty, warehouse}
    """
    if not bom_name:
        return []

    bom_doc = frappe.get_doc("BOM", bom_name)
    components = []

    for item in bom_doc.items:
        required_qty = flt(item.qty) * flt(qty_multiplier)

        # Check if this component has its own BOM (sub-assembly)
        sub_bom = frappe.db.get_value(
            "BOM", {"item": item.item_code, "is_active": 1, "is_default": 1}, "name"
        )

        if sub_bom and item.item_code != bom_doc.item:
            # Recursively explode sub-BOM
            sub_components = explode_bom(sub_bom, required_qty)
            components.extend(sub_components)
        else:
            # Leaf component
            components.append(
                {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "required_qty": required_qty,
                    "qty": required_qty,
                    "warehouse": item.source_warehouse or get_default_warehouse(),
                }
            )

    return components


def consume_reservations_for_delivery(sales_order, delivery_note, dn_items):
    """
    Consume reservations when delivery is made
    """
    # Get all active reservations for this SO
    reservations = frappe.get_all(
        "Stock Reservation Log",
        filters={
            "sales_order": sales_order,
            "status": ["in", ["Reserved", "Partially Reserved", "Partially Consumed"]],
        },
        fields=["name", "item_code", "reserved_qty", "consumed_qty"],
    )

    # Map delivered items
    delivered = {}
    for item in dn_items:
        if item.against_sales_order == sales_order:
            key = item.item_code
            delivered[key] = delivered.get(key, 0) + flt(item.qty)

    # Consume reservations
    for res in reservations:
        if res.item_code in delivered:
            qty_to_consume = min(
                delivered[res.item_code], res.reserved_qty - (res.consumed_qty or 0)
            )

            if qty_to_consume > 0:
                doc = frappe.get_doc("Stock Reservation Log", res.name)
                doc.consume(qty_to_consume, delivery_note)
                delivered[res.item_code] -= qty_to_consume


def update_reservations_from_purchase_receipt(purchase_receipt_doc):
    """
    When Purchase Receipt is submitted, update pending reservations for linked Sales Orders
    """
    from kaiten_erp.kaiten_erp.doctype.stock_reservation_log.stock_reservation_log import (
        get_available_qty,
    )

    # Check if any items are from Material Requests linked to Sales Orders
    for item in purchase_receipt_doc.items:
        if not item.material_request:
            continue

        # Get the Material Request
        mr = frappe.get_doc("Material Request", item.material_request)

        # Check if MR is linked to a Sales Order
        sales_order = mr.get("custom_source_sales_order")
        if not sales_order:
            continue

        # Update Procurement Shortage Logs
        shortage_logs = frappe.get_all(
            "Procurement Shortage Log",
            filters={
                "sales_order": sales_order,
                "material_request": item.material_request,
                "item_code": item.item_code,
                "status": ["in", ["Pending", "Partially Fulfilled"]],
            },
            pluck="name",
        )

        for log_name in shortage_logs:
            log = frappe.get_doc("Procurement Shortage Log", log_name)
            log.fulfill(
                item.qty,
                purchase_receipt=purchase_receipt_doc.name,
                purchase_order=item.purchase_order,
            )

        # Update partial Stock Reservation Logs
        partial_reservations = frappe.get_all(
            "Stock Reservation Log",
            filters={
                "sales_order": sales_order,
                "item_code": item.item_code,
                "status": "Partially Reserved",
            },
            pluck="name",
        )

        for res_name in partial_reservations:
            res = frappe.get_doc("Stock Reservation Log", res_name)
            new_available = get_available_qty(res.item_code, res.warehouse)
            needed = res.required_qty - res.reserved_qty

            if new_available >= needed:
                # Can now fully reserve
                res.reserved_qty = res.required_qty
                res.status = "Reserved"
                res.save(ignore_permissions=True)

                _log_so_action(
                    sales_order,
                    "Reservation Updated",
                    f"Item {item.item_code} now fully reserved after PR {purchase_receipt_doc.name}",
                )

    # Check if all items for related Sales Orders are now fully reserved
    check_and_update_so_status_after_receipt(purchase_receipt_doc)


def check_and_update_so_status_after_receipt(purchase_receipt_doc):
    """
    Check if all reservations for linked Sales Orders are complete
    and update status to Ready for Delivery
    """
    # Get unique Sales Orders from PR items
    sales_orders = set()
    for item in purchase_receipt_doc.items:
        if item.material_request:
            so = frappe.db.get_value(
                "Material Request", item.material_request, "custom_source_sales_order"
            )
            if so:
                sales_orders.add(so)

    for so in sales_orders:
        # Check if any shortages still pending
        pending_shortages = frappe.db.count(
            "Procurement Shortage Log",
            {"sales_order": so, "status": ["in", ["Pending", "Partially Fulfilled"]]},
        )

        # Check if any reservations still partial
        partial_reservations = frappe.db.count(
            "Stock Reservation Log", {"sales_order": so, "status": "Partially Reserved"}
        )

        if pending_shortages == 0 and partial_reservations == 0:
            # All items are now available
            current_status = frappe.db.get_value(
                "Sales Order", so, "custom_procurement_status"
            )
            if current_status == "Pending Procurement":
                frappe.db.set_value(
                    "Sales Order",
                    so,
                    "custom_procurement_status",
                    "Ready for Delivery",
                    update_modified=False,
                )
                _log_so_action(
                    so,
                    "Ready for Delivery",
                    f"All shortage items received. PR: {purchase_receipt_doc.name}",
                )

                frappe.msgprint(
                    _("Sales Order {0} is now Ready for Delivery").format(
                        frappe.utils.get_link_to_form("Sales Order", so)
                    ),
                    title=_("Procurement Complete"),
                    indicator="green",
                )


# =============================================================================
# ADMIN OVERRIDE
# =============================================================================


@frappe.whitelist()
def admin_release_reservation(reservation_name, reason):
    """
    Admin override to release a reservation
    Requires System Manager role
    """
    if not frappe.has_permission("Stock Reservation Log", "write"):
        frappe.throw(_("You don't have permission to release reservations"))

    if not reason or reason.strip() == "":
        frappe.throw(_("Override reason is mandatory"))

    doc = frappe.get_doc("Stock Reservation Log", reservation_name)

    doc.is_override = 1
    doc.override_by = frappe.session.user
    doc.override_reason = reason
    doc.override_timestamp = now_datetime()
    doc.release("Admin Override")

    return {"status": "success", "message": _("Reservation released successfully")}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _log_so_action(docname, action, details=""):
    """Log Sales Order action as comment for audit"""
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Info",
            "reference_doctype": "Sales Order",
            "reference_name": docname,
            "content": _("{0}: {1}").format(action, details) if details else action,
        }
    ).insert(ignore_permissions=True)


# =============================================================================
# UTILITY API
# =============================================================================


@frappe.whitelist()
def get_reservation_summary(sales_order):
    """
    Get summary of reservations for a Sales Order
    """
    reservations = frappe.get_all(
        "Stock Reservation Log",
        filters={"sales_order": sales_order},
        fields=[
            "item_code",
            "warehouse",
            "required_qty",
            "reserved_qty",
            "consumed_qty",
            "status",
        ],
    )

    shortages = frappe.get_all(
        "Procurement Shortage Log",
        filters={"sales_order": sales_order},
        fields=["item_code", "warehouse", "shortage_qty", "fulfilled_qty", "status"],
    )

    return {
        "total_reserved_items": len(reservations),
        "reservations": reservations,
        "total_shortage_items": len(shortages),
        "shortages": shortages,
        "reservation_status": {
            "reserved": len([r for r in reservations if r.status == "Reserved"]),
            "partially_reserved": len(
                [r for r in reservations if r.status == "Partially Reserved"]
            ),
            "consumed": len([r for r in reservations if r.status == "Consumed"]),
            "released": len([r for r in reservations if r.status == "Released"]),
        },
        "shortage_status": {
            "pending": len([s for s in shortages if s.status == "Pending"]),
            "partially_fulfilled": len(
                [s for s in shortages if s.status == "Partially Fulfilled"]
            ),
            "fulfilled": len([s for s in shortages if s.status == "Fulfilled"]),
        },
    }


@frappe.whitelist()
def get_stock_availability_for_bom(sales_order):
    """
    Get stock availability preview for BOM items before submission
    """
    from kaiten_erp.kaiten_erp.doctype.stock_reservation_log.stock_reservation_log import (
        get_available_qty,
    )

    so_doc = frappe.get_doc("Sales Order", sales_order)
    bom_items = get_bom_items_from_sales_order(so_doc)

    if not bom_items:
        bom_items = get_bom_items_traditional(so_doc)

    default_warehouse = get_default_warehouse()
    availability = []

    for item in bom_items:
        item_code = item.get("item_code")
        required_qty = flt(item.get("qty") or item.get("required_qty"))
        warehouse = item.get("warehouse") or default_warehouse

        available_qty = get_available_qty(item_code, warehouse)
        shortage_qty = max(0, required_qty - available_qty)

        availability.append(
            {
                "item_code": item_code,
                "item_name": item.get("item_name"),
                "warehouse": warehouse,
                "required_qty": required_qty,
                "available_qty": available_qty,
                "shortage_qty": shortage_qty,
                "status": "Available" if shortage_qty == 0 else "Shortage",
            }
        )

    return {
        "items": availability,
        "summary": {
            "total_items": len(availability),
            "available": len([i for i in availability if i["status"] == "Available"]),
            "shortages": len([i for i in availability if i["status"] == "Shortage"]),
        },
    }
