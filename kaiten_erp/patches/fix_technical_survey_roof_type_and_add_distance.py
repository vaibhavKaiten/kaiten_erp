import frappe


def execute():
    doctype = "Technical Survey"

    # 1. Change roof_type from Data to Select with options
    if frappe.db.exists("DocField", {"parent": doctype, "fieldname": "roof_type"}):
        frappe.db.set_value(
            "DocField",
            {"parent": doctype, "fieldname": "roof_type"},
            {
                "fieldtype": "Select",
                "options": "RCC\nTin Shed\nAsbestos\nMixed\nOther",
            },
        )

    # Commit before DDL to avoid ImplicitCommitError
    frappe.db.commit()

    # Alter the column type in the DB table
    frappe.db.sql(
        "ALTER TABLE `tabTechnical Survey` MODIFY `roof_type` varchar(140) DEFAULT NULL"
    )

    # 2. Add distance field after back_height_m if it doesn't already exist
    if not frappe.db.exists("DocField", {"parent": doctype, "fieldname": "distance"}):
        # Find the idx of back_height_m to insert after it
        back_height_idx = frappe.db.get_value(
            "DocField",
            {"parent": doctype, "fieldname": "back_height_m"},
            "idx",
        )
        if back_height_idx:
            new_idx = back_height_idx + 1
            # Shift subsequent fields
            frappe.db.sql(
                """
                UPDATE `tabDocField`
                SET idx = idx + 1
                WHERE parent = %s AND idx >= %s
                """,
                (doctype, new_idx),
            )
            # Insert the new field
            doc = frappe.get_doc("DocType", doctype)
            field = doc.append("fields", {})
            field.fieldname = "distance"
            field.fieldtype = "Data"
            field.label = "Distance"
            field.idx = new_idx
            field.db_insert()

        frappe.db.commit()

        # Add the column to the DB table
        if not frappe.db.has_column(doctype, "distance"):
            frappe.db.sql(
                "ALTER TABLE `tabTechnical Survey` ADD COLUMN `distance` varchar(140) DEFAULT NULL"
            )

    # Update Property Setter field_order if it exists
    ps_name = "Technical Survey-main-field_order"
    if frappe.db.exists("Property Setter", ps_name):
        import json

        current = frappe.db.get_value("Property Setter", ps_name, "value")
        if current:
            field_order = json.loads(current)
            if "distance" not in field_order:
                try:
                    idx = field_order.index("back_height_m")
                    field_order.insert(idx + 1, "distance")
                    frappe.db.set_value(
                        "Property Setter", ps_name, "value", json.dumps(field_order)
                    )
                except ValueError:
                    pass

    frappe.db.commit()
