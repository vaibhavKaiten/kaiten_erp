# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

# Patch: remove header-level `warehouse` and `supplier_for_po` columns from
# Procurement Consolidation. Warehouse is now set per item in the child table.

import frappe


def execute():
	for col in ("warehouse", "supplier_for_po"):
		if frappe.db.has_column("Procurement Consolidation", col):
			frappe.db.sql(f"ALTER TABLE `tabProcurement Consolidation` DROP COLUMN `{col}`")

	frappe.db.commit()
