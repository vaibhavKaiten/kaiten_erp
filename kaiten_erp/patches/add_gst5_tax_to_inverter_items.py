import frappe


def execute():
    item_ids = [
        # Waaree
        "WARI-100-TP", "WARI-80-TP", "WARI-60-TP", "WARI-50-TP", "WARI-30-TP",
        "WARI-25-TP", "WARI-20-TP", "WARI-15-TP", "WARI-12-TP", "WARI-10-TP",
        "WARI-8-TP", "WARI-6-TP", "WARI-5-TP", "WARI-5-SP", "WARI-4-SP", "WARI-3-SP",
        # Pv Blink
        "PVB-30-TP", "PVB-25-TP", "PVB-20-TP", "PVB-18-TP", "PVB-15-TP", "PVB-12-TP",
        "PVB-10-TP", "PVB-8-TP", "PVB-6-TP", "PVB-5-TP",
        "PVB-6-SP", "PVB-5-SP", "PVB-4.6-SP", "PVB-4-SP", "PVB-3.6-SP",
        "PVB-3.3-SP", "PVB-3-SP",
        # V-Sole
        "VSOLE-135-TP", "VSOLE-125-TP", "VSOLE-120-TP", "VSOLE-110-TP", "VSOLE-100-TP",
        "VSOLE-80-TP", "VSOLE-70-TP", "VSOLE-60-TP", "VSOLE-50-TP", "VSOLE-40-TP",
        "VSOLE-35-TP", "VSOLE-30-TP", "VSOLE-25-TP", "VSOLE-20-TP", "VSOLE-18-TP",
        "VSOLE-15-TP", "VSOLE-12-TP", "VSOLE-10-TP", "VSOLE-8-TP", "VSOLE-7-TP",
        "VSOLE-6-TP", "VSOLE-5-TP", "VSOLE-4-TP",
        "VSOLE-6-SP", "VSOLE-5-SP", "VSOLE-4-SP", "VSOLE-3-SP", "VSOLE-2-SP",
        # Luminious
        "LMS-100-TP", "LMS-80-TP", "LMS-60-TP", "LMS-50-TP", "LMS-30-TP",
        "LMS-25-TP", "LMS-20-TP", "LMS-15-TP", "LMS-12-TP", "LMS-10-TP",
        "LMS-8-TP", "LMS-6-TP", "LMS-5-TP",
        "LMS-5-SP", "LMS-4-SP", "LMS-3-SP",
        # Power one
        "PONE-350-TP", "PONE-136-TP", "PONE-125-TP", "PONE-110-TP", "PONE-100-TP",
        "PONE-80-TP", "PONE-60-TP", "PONE-50-TP", "PONE-40-TP", "PONE-30-TP",
        "PONE-25-TP", "PONE-20-TP", "PONE-15-TP", "PONE-12-TP", "PONE-10-TP",
        "PONE-8-TP", "PONE-6-TP", "PONE-5-TP",
        "PONE-6-SP", "PONE-5-SP", "PONE-4-SP", "PONE-3.3-SP", "PONE-3-SP", "PONE-2-SP",
    ]

    tax_template = "GST 5% - RS"
    updated = []
    skipped = []
    not_found = []

    for item_id in item_ids:
        if not frappe.db.exists("Item", item_id):
            not_found.append(item_id)
            continue

        doc = frappe.get_doc("Item", item_id)

        already_exists = any(
            row.item_tax_template == tax_template for row in doc.get("taxes", [])
        )

        if already_exists:
            skipped.append(item_id)
            continue

        doc.append("taxes", {"item_tax_template": tax_template})
        doc.save(ignore_permissions=True)
        updated.append(item_id)

    frappe.db.commit()

    print(f"\n✅ Updated ({len(updated)}): {updated}")
    print(f"⏭️  Skipped - already has template ({len(skipped)}): {skipped}")
    print(f"❌ Not found ({len(not_found)}): {not_found}")
