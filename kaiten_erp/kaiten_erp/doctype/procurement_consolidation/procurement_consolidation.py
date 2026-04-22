# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json


class ProcurementConsolidation(Document):
	"""
	Procurement Consolidation — Central aggregation and PO-creation engine.

	Workflow:
	  1. Click "Fetch Approved Material Requests" → pulls all approved
	     Purchase MRs with pending quantities.  Items are grouped by item_code.
	  2. User reviews quantities, sets Actual Qty to Order, assigns Supplier
	     and Warehouse per row.
	  3. Click "Create Purchase Order" → one Draft PO per distinct supplier.
	  4. Status progresses: Draft → Consolidated → PO Created → Completed.
	"""

	# ------------------------------------------------------------------
	# Fetch
	# ------------------------------------------------------------------

	@frappe.whitelist()
	def fetch_approved_material_requests(self):
		"""
		Aggregate pending items from all approved Purchase Material Requests.

		Selection criteria:
		  - docstatus = 1 (submitted)
		  - material_request_type = 'Purchase'
		  - At least one item where qty − ordered_qty > 0

		Items are grouped by item_code. Existing rows in the child table are
		cleared and rebuilt on every fetch.
		"""

		# Fetch all pending items from approved Purchase MRs that have NOT been
		# consolidated into another Procurement Consolidation yet.
		pending_rows = frappe.db.sql(
			"""
			SELECT
				mri.name          AS mr_item_name,
				mr.name           AS mr_name,
				mri.item_code,
				mri.item_name,
				mri.uom,
				mri.qty                              AS required_qty,
				IFNULL(mri.ordered_qty, 0)           AS ordered_qty
			FROM `tabMaterial Request Item` mri
			JOIN `tabMaterial Request` mr ON mr.name = mri.parent
			WHERE mr.docstatus = 1
			  AND mr.material_request_type = 'Purchase'
			  AND (mri.qty - IFNULL(mri.ordered_qty, 0)) > 0
			  AND IFNULL(mr.custom_consolidated, 0) = 0
			ORDER BY mr.creation ASC, mri.idx ASC
			""",
			as_dict=True,
		)

		if not pending_rows:
			frappe.msgprint(
				"No pending approved Purchase Material Requests found.",
				indicator="yellow",
			)
			return {
				"status": "no_data",
				"message": "No pending approved Purchase Material Requests found.",
			}

		# Aggregate by item_code
		items_map = {}  # {item_code: {…aggregated data…}}

		for row in pending_rows:
			item_code = row.item_code
			pending_qty = row.required_qty - row.ordered_qty  # always > 0 per WHERE clause

			if item_code not in items_map:
				items_map[item_code] = {
					"item_code": item_code,
					"item_name": row.item_name,
					"uom": row.uom,
					"total_required_quantity": 0.0,
					"source_mrs": [],
				}

			items_map[item_code]["total_required_quantity"] += pending_qty
			items_map[item_code]["source_mrs"].append({
				"mr": row.mr_name,
				"mr_item": row.mr_item_name,
				"qty": pending_qty,
			})

		# Rebuild child table
		self.items = []

		for item_code, data in items_map.items():
			gst_rate = self.get_item_gst_rate(item_code)
			total_qty = data["total_required_quantity"]

			self.append("items", {
				"item_code": item_code,
				"item_name": data["item_name"],
				"uom": data["uom"],
				"total_required_quantity": total_qty,
				"available_stock": 0,
				"actual_quantity": total_qty,   # editable by user
				"net_quantity_to_procure": total_qty,
				"is_completed": 0,
				"gst_percentage": gst_rate,
				"source_material_requests": json.dumps(data["source_mrs"], indent=2),
			})

		unique_mr_names = list({row.mr_name for row in pending_rows})
		unique_mrs = len(unique_mr_names)

		# Save the rebuilt items table first (without changing status via ORM,
		# because the DB may still have old select options until bench migrate runs).
		self.save()

		# Update status directly in DB to bypass ORM select-option validation.
		# This is safe — MariaDB stores select fields as VARCHAR, not ENUM.
		frappe.db.set_value(
			"Procurement Consolidation", self.name, "status", "Consolidated", update_modified=False
		)

		# Mark each fetched Material Request as consolidated:
		#  - custom_consolidated = 1  → excludes it from future fetch queries
		#  - status = "Consolidated"  → visually communicates it is locked for
		#    normal purchase, so it can only be actioned via Procurement Consolidation.
		# frappe.db.set_value is used to bypass ORM select-option validation,
		# which is safe because MariaDB stores Select fields as VARCHAR.
		for mr_name in unique_mr_names:
			frappe.db.set_value(
				"Material Request",
				mr_name,
				{
					"custom_consolidated": 1,
					"status": "Consolidated",
				},
				update_modified=False,
			)

		frappe.db.commit()

		frappe.msgprint(
			f"Fetched {unique_mrs} Material Request(s) with {len(items_map)} unique item(s).",
			title="Success",
			indicator="green",
		)
		return {
			"status": "success",
			"message": f"Fetched {unique_mrs} MR(s), {len(items_map)} unique item(s).",
			"mr_count": unique_mrs,
			"item_count": len(items_map),
		}

	# ------------------------------------------------------------------
	# Purchase Order creation
	# ------------------------------------------------------------------

	@frappe.whitelist()
	def create_purchase_order(self):
		"""
		Create one Draft Purchase Order per distinct supplier from the
		selected items in the child table.

		Rules:
		- Item must be selected (select_item = 1).
		- actual_quantity must be > 0.
		- A supplier must be assigned on the row.
		- Items with the same supplier are grouped into a single PO.
		"""
		from frappe.utils import today, add_days

		selected_items = [
			item for item in self.items
			if item.select_item == 1 and (item.actual_quantity or 0) > 0
		]

		if not selected_items:
			frappe.throw(
				"Please select at least one item with a quantity > 0 before creating a Purchase Order.",
				title="No Items Selected",
			)

		# Validate every selected item has supplier and warehouse
		missing_supplier = [item.item_code for item in selected_items if not item.supplier]
		if missing_supplier:
			frappe.throw(
				f"Please assign a Supplier for: {', '.join(missing_supplier)}",
				title="Supplier Required",
			)

		missing_warehouse = [item.item_code for item in selected_items if not item.warehouse]
		if missing_warehouse:
			frappe.throw(
				f"Please assign a Warehouse for: {', '.join(missing_warehouse)}",
				title="Warehouse Required",
			)

		# Group by supplier
		by_supplier = {}
		for item in selected_items:
			by_supplier.setdefault(item.supplier, []).append(item)

		created_pos = []

		try:
			for supplier, items in by_supplier.items():
				po = frappe.get_doc({
					"doctype": "Purchase Order",
					"supplier": supplier,
					"company": self.company,
					"transaction_date": today(),
					"schedule_date": add_days(today(), 7),
				})

				# Link back to this Procurement Consolidation if field exists
				if frappe.db.has_column("Purchase Order", "custom_procurement_consolidation"):
					po.custom_procurement_consolidation = self.name

				for item in items:
					po_item = {
						"item_code": item.item_code,
						"item_name": item.item_name,
						"qty": item.actual_quantity,
						"uom": item.uom,
						"rate": item.supplier_rate or 0,
						"warehouse": item.warehouse,
					}
					# Store source MR references if field exists
					if frappe.db.has_column("Purchase Order Item", "custom_source_material_request"):
						try:
							sources = json.loads(item.source_material_requests or "[]")
							if sources:
								po_item["custom_source_material_request"] = sources[0].get("mr", "")
						except Exception:
							pass
					po.append("items", po_item)

				po.insert()
				created_pos.append(po.name)

			# Build set of ordered item_codes (all selected items that went into POs)
			ordered_item_codes = {item.item_code for item in selected_items}

			# Mark ordered items as completed and uncheck selection
			for item in self.items:
				if item.item_code in ordered_item_codes:
					item.is_completed = 1
					item.select_item = 0
				elif item.select_item:
					item.select_item = 0

			# Calculate new status before save
			if not self.items:
				new_status = "Draft"
			else:
				completed = sum(1 for i in self.items if i.is_completed or (i.actual_quantity or 0) == 0)
				new_status = "Completed" if completed == len(self.items) else "PO Created"

			# Save child table changes with a dummy-valid status to bypass ORM
			# validation (DB schema still has old options until bench migrate runs).
			self.status = "Draft"
			self.save()

			# Write real status directly — safe because MariaDB stores Select as VARCHAR.
			frappe.db.set_value(
				"Procurement Consolidation", self.name, "status", new_status, update_modified=False
			)
			frappe.db.commit()

			return {
				"status": "success",
				"po_names": created_pos,
				"po_count": len(created_pos),
				"items_count": len(selected_items),
				"message": f"Created {len(created_pos)} Purchase Order(s): {', '.join(created_pos)}",
			}

		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), "Procurement Consolidation - PO Creation Error")
			frappe.throw(
				f"Failed to create Purchase Order(s). Check the Error Log for details.",
				title="PO Creation Failed",
			)

	# ------------------------------------------------------------------
	# Status management
	# ------------------------------------------------------------------

	def _update_status(self):
		"""
		Derive status from the current state of the items child table.

		Draft         → no items or all have actual_quantity > 0 still pending
		Consolidated  → items fetched but no PO created yet
		PO Created    → at least one item processed into a PO; some may remain
		Completed     → all items processed (actual_quantity = 0 or is_completed)
		"""
		if not self.items:
			self.status = "Draft"
			return

		# "Completed" = all items have been fully ordered
		# We use is_completed flag (set externally) or actual_quantity = 0
		completed = sum(1 for i in self.items if i.is_completed or (i.actual_quantity or 0) == 0)
		total = len(self.items)

		if completed == total:
			self.status = "Completed"
		elif self.status in ("PO Created",):
			pass  # Keep PO Created once set, unless fully completed
		else:
			self.status = "Consolidated"

	# ------------------------------------------------------------------
	# GST helper
	# ------------------------------------------------------------------

	def get_item_gst_rate(self, item_code):
		"""Return the GST tax-rate percentage for an item (0 if unknown)."""
		try:
			item = frappe.get_doc("Item", item_code)
			for tax_row in item.taxes or []:
				template_name = tax_row.item_tax_template or ""
				for pct, label in [(28, "28"), (18, "18"), (12, "12"), (5, "5")]:
					if f"{label}%" in template_name or f"GST {label}" in template_name:
						return float(pct)
				# Try reading rate from the template directly
				if template_name:
					try:
						tmpl = frappe.get_doc("Item Tax Template", template_name)
						total = sum(t.tax_rate for t in tmpl.taxes or [])
						if total:
							return total
					except Exception:
						pass
			# HSN-based fallback for common solar items
			if getattr(item, "gst_hsn_code", None) and item.gst_hsn_code[:4] in ("8541", "8504"):
				return 5.0
		except Exception as exc:
			frappe.log_error(f"GST rate lookup failed for {item_code}: {exc}")
		return 0.0
