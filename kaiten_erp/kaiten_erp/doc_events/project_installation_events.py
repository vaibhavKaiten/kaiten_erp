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
