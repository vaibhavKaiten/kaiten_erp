import frappe


def update_profitability(job_file_name):
    """Recalculate and persist profitability fields on a Job File."""
    if not job_file_name:
        return

    selling_price = _get_selling_price(job_file_name)
    material_cost = _get_material_cost(job_file_name)
    gross_profit = selling_price - material_cost
    profit_pct = round((gross_profit / selling_price * 100), 2) if selling_price else 0
    cost_pct = round((material_cost / selling_price * 100), 2) if selling_price else 0

    frappe.db.set_value(
        "Job File",
        job_file_name,
        {
            "custom_total_selling_price": selling_price,
            "custom_total_material_cost": material_cost,
            "custom_gross_profit": gross_profit,
            "custom_profit_percentage": profit_pct,
            "custom_cost_": cost_pct,
        },
        update_modified=False,
    )


def _get_selling_price(job_file_name):
    """Fetch net_total from the latest submitted Sales Order linked to this Job File."""
    result = frappe.get_all(
        "Sales Order",
        filters={"custom_job_file": job_file_name, "docstatus": 1},
        fields=["net_total"],
        order_by="creation desc",
        limit_page_length=1,
    )
    return float(result[0].net_total or 0) if result else 0


def _get_material_cost(job_file_name):
    """Calculate total material cost from the linked Technical Survey items × valuation rate."""
    ts_name = frappe.db.get_value("Job File", job_file_name, "custom_technical_survey")
    if not ts_name:
        return 0

    ts = frappe.get_doc("Technical Survey", ts_name)

    # Collect (item_code, qty) from panel, inverter, battery + BOM table
    items = []
    for field, qty_field in [
        ("panel", "panel_qty_bom"),
        ("inverter", "inverter_qty_bom"),
        ("battery", "battery_qty_bom"),
    ]:
        item_code = ts.get(field)
        qty = ts.get(qty_field)
        if item_code and qty:
            items.append((item_code, float(qty)))

    for row in ts.get("table_vctx") or []:
        if row.item_code and row.qty:
            items.append((row.item_code, float(row.qty)))

    if not items:
        return 0

    rate_map = _get_valuation_rate_map(list({ic for ic, _ in items}))
    return sum(qty * rate_map.get(ic, 0) for ic, qty in items)


def _get_valuation_rate_map(item_codes):
    """
    {item_code: valuation_rate} from tabBin (max across warehouses).
    Falls back to Item.last_purchase_rate for items without stock entries.
    """
    if not item_codes:
        return {}

    placeholders = ", ".join(["%s"] * len(item_codes))
    rows = frappe.db.sql(
        f"""SELECT item_code, MAX(valuation_rate) AS valuation_rate
            FROM `tabBin`
            WHERE item_code IN ({placeholders}) AND valuation_rate > 0
            GROUP BY item_code""",
        item_codes,
        as_dict=True,
    )
    rate_map = {r.item_code: float(r.valuation_rate or 0) for r in rows}

    missing = [ic for ic in item_codes if ic not in rate_map]
    if missing:
        ph2 = ", ".join(["%s"] * len(missing))
        fallback = frappe.db.sql(
            f"""SELECT name AS item_code, last_purchase_rate
                FROM `tabItem`
                WHERE name IN ({ph2}) AND last_purchase_rate > 0""",
            missing,
            as_dict=True,
        )
        for r in fallback:
            rate_map[r.item_code] = float(r.last_purchase_rate or 0)

    return rate_map
