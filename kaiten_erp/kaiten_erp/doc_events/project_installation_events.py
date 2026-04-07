import frappe


def validate(doc, method=None):
    """Populate read-only structure fields from the linked Structure Mounting via Job File."""
    if not doc.custom_job_file:
        return

    structure_mounting = frappe.db.get_value(
        "Job File", doc.custom_job_file, "custom_structure_mounting"
    )

    if not structure_mounting:
        return

    sm = frappe.db.get_value(
        "Structure Mounting",
        structure_mounting,
        ["structure_type", "anchoring_type", "strucutre_height"],
        as_dict=True,
    )

    if not sm:
        return

    doc.structure_type = sm.structure_type
    doc.anchoring_type = sm.anchoring_type
    doc.structure_height_m = sm.strucutre_height

    # Populate panel and inverter counts from the approved Technical Survey
    ts_name = frappe.db.get_value(
        "Job File", doc.custom_job_file, "custom_technical_survey"
    )
    if not ts_name:
        return

    ts_state, panel_qty, inverter_qty = frappe.db.get_value(
        "Technical Survey",
        ts_name,
        ["workflow_state", "panel_qty_bom", "inverter_qty_bom"],
    )

    if ts_state != "Approved":
        return

    doc.panel_count = panel_qty
    doc.custom_inverter_count = inverter_qty
