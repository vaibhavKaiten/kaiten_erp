"""
One-off patch: rename Custom Field DB records whose `name` column doesn't match
the expected "{dt}-{fieldname}" pattern. This happens when fixtures were imported
with wrong `name` values in an earlier migration, causing subsequent `bench migrate`
fixture syncs to fail with "A field with the name X already exists in Y".
"""

import frappe


def execute():
    results = frappe.db.sql(
        """
        SELECT name, dt, fieldname
        FROM `tabCustom Field`
        WHERE name != CONCAT(dt, '-', fieldname)
        ORDER BY dt, fieldname
        """,
        as_dict=True,
    )

    print(f"Found {len(results)} mismatched Custom Field record(s):")

    for r in results:
        expected = f"{r.dt}-{r.fieldname}"
        if frappe.db.exists("Custom Field", expected):
            frappe.db.sql("DELETE FROM `tabCustom Field` WHERE name = %s", r.name)
            print(f"  DELETED duplicate: {r.name!r}  (correct name {expected!r} already in DB)")
        else:
            frappe.db.sql(
                "UPDATE `tabCustom Field` SET name = %s WHERE name = %s",
                (expected, r.name),
            )
            print(f"  RENAMED: {r.name!r} → {expected!r}")

    frappe.db.commit()
    print("Done.")
