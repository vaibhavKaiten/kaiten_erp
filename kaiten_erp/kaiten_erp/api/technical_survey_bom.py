# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def get_bom_payload(proposed_system_item_code):
    """
    Get BOM payload for the proposed system item.
    Returns structure with panel/inverter candidates, quantities, and other items.
    Handles Phantom BOM expansion and correct Item Group categorization.
    """
    if not proposed_system_item_code:
        return {"error": "No proposed system provided"}

    # Find BOM for the proposed system
    bom_name = find_active_bom(proposed_system_item_code)

    if not bom_name:
        return {"error": f"No active BOM found for item {proposed_system_item_code}"}

    # Get flattened BOM items (handling Phantoms references)
    flattened_items = get_flattened_items(bom_name)

    # Categorize items
    panel_items = []
    inverter_items = []
    battery_items = []
    other_items = []

    # Key sets for deduplication of other items (Common components)
    other_items_codes = set()

    panel_qty_sum = 0
    inverter_qty_sum = 0
    battery_qty_sum = 0

    for item in flattened_items:
        # Check Item Group (Handle singular and plural cases)
        ig = item.get("item_group", "")

        if ig in ["Panel", "Panels"]:
            panel_items.append(item)
            panel_qty_sum += item.get("qty", 0)
        elif ig in ["Inverter", "Inverters"]:
            inverter_items.append(item)
            inverter_qty_sum += item.get("qty", 0)
        elif ig in ["Battery", "Batteries"]:
            battery_items.append(item)
            battery_qty_sum += item.get("qty", 0)
        else:
            # Deduplicate other items (Common components should be distinct)
            if item["item_code"] not in other_items_codes:
                other_items.append(item)
                other_items_codes.add(item["item_code"])

    # Determine default selections (if only one option exists)
    default_panel = panel_items[0]["item_code"] if len(panel_items) == 1 else None
    default_inverter = (
        inverter_items[0]["item_code"] if len(inverter_items) == 1 else None
    )
    default_battery = battery_items[0]["item_code"] if len(battery_items) == 1 else None

    return {
        "bom": bom_name,
        "all_items": flattened_items,  # Full list if needed
        "panel_candidates": panel_items,
        "inverter_candidates": inverter_items,
        "battery_candidates": battery_items,
        "default_selected_panel": default_panel,
        "default_selected_inverter": default_inverter,
        "default_selected_battery": default_battery,
        "qty_summary": {
            "panel_qty_from_bom": panel_qty_sum,
            "inverter_qty_from_bom": inverter_qty_sum,
            "battery_qty_from_bom": battery_qty_sum,
        },
        "other_items": other_items,
    }


def get_flattened_items(bom_name):
    """
    Get flattened list of BOM items, handling Phantom BOMs.
    Tries to use BOM Explosion Item table first, falls back to recursion.
    """
    try:
        # Try fetching from BOM Explosion Item (pre-calculated flattened list)
        # Using stock_qty as the quantity field
        exploded_items = frappe.get_all(
            "BOM Explosion Item",
            filters={"parent": bom_name},
            fields=["item_code", "stock_qty", "description", "rate", "amount"],
        )

        if exploded_items:
            result = []
            for row in exploded_items:
                item_doc = frappe.get_cached_doc("Item", row.item_code)
                result.append(
                    {
                        "item_code": row.item_code,
                        "item_name": item_doc.item_name,
                        "item_group": item_doc.item_group,
                        "qty": row.stock_qty,
                        "uom": item_doc.stock_uom,
                        "rate": row.rate or 0,
                        "amount": row.amount or 0,
                        "description": row.description or item_doc.description or "",
                    }
                )
            return result
    except Exception:
        # Fallback if table doesn't exist or error
        pass

    # Manual fallback recursion
    return recurse_bom_items(bom_name)


def recurse_bom_items(bom_name, qty_multiplier=1):
    """
    Recursively fetch BOM items, expanding sub-assemblies (Phantoms).
    """
    items = []
    try:
        bom_doc = frappe.get_doc("BOM", bom_name)
        for row in bom_doc.items:
            # If item has a BOM (sub-assembly/phantom), recurse
            if row.bom_no:
                sub_items = recurse_bom_items(row.bom_no, qty_multiplier * row.qty)
                items.extend(sub_items)
            else:
                # Leaf item
                item_doc = frappe.get_cached_doc("Item", row.item_code)
                items.append(
                    {
                        "item_code": row.item_code,
                        "item_name": item_doc.item_name,
                        "item_group": item_doc.item_group,
                        "qty": row.qty * qty_multiplier,
                        "uom": row.uom,
                        "rate": row.rate or 0,
                        "amount": row.amount or 0,
                        "description": item_doc.description or "",
                    }
                )
    except Exception:
        pass
    return items


def find_active_bom(item_code):
    """
    Find the active BOM for an item.
    Prefers submitted & default active BOM, falls back to any submitted active BOM,
    then falls back to draft BOMs.

    Args:
        item_code: Item code

    Returns:
        str: BOM name or None
    """
    # Try to find submitted default active BOM
    default_bom = frappe.db.get_value(
        "BOM",
        filters={"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        fieldname="name",
    )

    if default_bom:
        return default_bom

    # Fallback to any submitted active BOM
    submitted_bom = frappe.db.get_all(
        "BOM",
        filters={"item": item_code, "is_active": 1, "docstatus": 1},
        fields=["name"],
        order_by="modified desc",
        limit=1,
    )

    if submitted_bom:
        return submitted_bom[0].name

    # Fallback to draft BOMs (for development/testing)
    draft_bom = frappe.db.get_all(
        "BOM",
        filters={"item": item_code, "is_active": 1, "docstatus": 0},
        fields=["name"],
        order_by="modified desc",
        limit=1,
    )

    return draft_bom[0].name if draft_bom else None


@frappe.whitelist()
def get_bom_items_for_dropdown(doctype, txt, searchfield, start, page_len, filters):
    """
    Query function for dropdown to filter items from BOM.
    This approach hides the 'Filters applied for' message.
    """
    allowed_items = filters.get("allowed_items", [])

    if not allowed_items:
        return []

    # Convert to tuple for SQL IN clause
    allowed_items_str = ", ".join([frappe.db.escape(item) for item in allowed_items])

    return frappe.db.sql(
        f"""
        SELECT name, item_name
        FROM `tabItem`
        WHERE name IN ({allowed_items_str})
        AND (name LIKE %(txt)s OR item_name LIKE %(txt)s)
        ORDER BY name
        LIMIT %(start)s, %(page_len)s
    """,
        {"txt": f"%{txt}%", "start": start, "page_len": page_len},
    )


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_items_with_bom(doctype, txt, searchfield, start, page_len, filters):
    """
    Query function to get items from "Products" group that have active BOMs.
    Used for filtering the proposed_system_kw__tier field.

    Args:
        doctype: DocType name (Item)
        txt: Search text
        searchfield: Field to search in
        start: Start index for pagination
        page_len: Number of results per page
        filters: Additional filters (item_group)

    Returns:
        list: List of items with BOMs in format [(item_code, item_name)]
    """
    # Get item_group from filters, default to 'Products'
    item_group = filters.get("item_group", "Products") if filters else "Products"

    # Query to get items that:
    # 1. Belong to the specified item_group (Products)
    # 2. Have at least one active, submitted BOM
    # 3. Match the search text (if provided)
    results = frappe.db.sql(
        """
        SELECT DISTINCT
            i.name,
            i.item_name
        FROM `tabItem` i
        INNER JOIN `tabBOM` b ON b.item = i.name AND b.is_active = 1 AND b.docstatus = 1
        WHERE 
            i.item_group = %(item_group)s
            AND i.disabled = 0
            AND (i.{searchfield} LIKE %(txt)s OR i.item_name LIKE %(txt)s)
        ORDER BY 
            CASE WHEN i.{searchfield} LIKE %(txt)s THEN 0 ELSE 1 END,
            i.item_name
        LIMIT %(start)s, %(page_len)s
    """.format(
            searchfield=searchfield
        ),
        {
            "item_group": item_group,
            "txt": f"%{txt}%",
            "start": start,
            "page_len": page_len,
        },
        as_dict=False,
    )

    return results
