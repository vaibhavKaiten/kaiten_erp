import json

with open("apps/kaiten_erp/kaiten_erp/fixtures/custom_field.json") as f:
    fixture_fields = json.load(f)

conflicts = []
for field in fixture_fields:
    fixture_name = field["name"]
    dt = field["dt"]
    fieldname = field["fieldname"]
    existing = frappe.db.get_all("Custom Field", filters={"dt": dt, "fieldname": fieldname}, fields=["name"])
    for e in existing:
        if e["name"] != fixture_name:
            conflicts.append(e["name"])

print(f"Found {len(conflicts)} conflicts:")
for name in conflicts:
    print(f"  {name}")

# Delete all conflicting records
for name in conflicts:
    frappe.delete_doc("Custom Field", name, force=True)
    print(f"  Deleted: {name}")

frappe.db.commit()
print("Done.")
