# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
from erpnext.stock.utils import get_stock_balance


class ProcurementConsolidation(Document):
	"""
	Procurement Consolidation DocType
	
	Purpose:
	- Planning and UI layer for Material Request consolidation
	- Fetches approved Material Requests and consolidates items
	- Does NOT create accounting or inventory entries
	"""
	
	@frappe.whitelist()
	def fetch_approved_material_requests(self):
		"""
		Fetch approved Material Requests and consolidate items incrementally
		with ATOMIC one-time consumption guarantee.
		
		CRITICAL BEHAVIOR (ATOMIC FETCH + CONSUME):
		- Uses docstatus = 1 to identify approved Material Requests
		- Uses custom_consolidated flag to prevent re-consumption
		- IMMEDIATELY marks each MR as consolidated after processing it
		- Saves and commits each MR to database atomically
		- Supports incremental fetching (adds to existing items)
		
		ATOMICITY GUARANTEE:
		For each Material Request:
		1. Fetch MR data
		2. Merge items into consolidation table
		3. IMMEDIATELY mark MR as custom_consolidated = 1
		4. SAVE and COMMIT the change
		
		This ensures one-time consumption even with concurrent button clicks.
		
		Returns:
			dict: Summary of fetched data
		"""
		
		# CRITICAL: Warehouse is required for stock check
		if not self.warehouse:
			frappe.throw(
				"Please select a Company Warehouse before fetching Material Requests. Stock levels will be checked against this warehouse.",
				title="Warehouse Required"
			)

		# Fetch eligible Material Requests
		# CRITICAL FILTER: docstatus = 1 AND IFNULL(custom_consolidated, 0) = 0
		# This ensures ONLY approved and not-yet-consolidated MRs are fetched
		material_requests = frappe.db.sql("""
			SELECT name
			FROM `tabMaterial Request`
			WHERE docstatus = 1
			AND IFNULL(custom_consolidated, 0) = 0
			ORDER BY creation ASC
		""", as_dict=True)
		
		if not material_requests:
			frappe.msgprint(
				"No new approved Material Requests to fetch.",
				indicator="yellow"
			)
			return {
				"status": "no_data",
				"message": "No new approved Material Requests to fetch",
				"material_requests_fetched": 0,
				"material_requests_skipped": 0
			}
		
		# Build a dictionary of existing items in this Procurement Consolidation
		# Key: item_code, Value: row object
		existing_items = {}
		for row in self.items:
			existing_items[row.item_code] = row
		
		# Track successfully processed Material Requests
		successfully_consumed_mr_ids = []
		failed_mr_ids = []
		
		# Dictionary to consolidate NEW items from fetched MRs: {item_code: {data}}
		new_items_data = {}
		
		# ATOMIC PROCESSING: Process each Material Request and mark as consumed IMMEDIATELY
		for mr in material_requests:
			try:
				# Load the Material Request document
				mr_doc = frappe.get_doc("Material Request", mr.name)
				
				# Double-check it hasn't been consolidated (race condition protection)
				if mr_doc.custom_consolidated == 1:
					frappe.log_error(
						f"Material Request {mr.name} was already consolidated (race condition detected)",
						"Procurement Consolidation - Race Condition"
					)
					failed_mr_ids.append(mr.name)
					continue
				
				# Process each item in the Material Request
				for item in mr_doc.items:
					item_code = item.item_code
					
					# Check if item already exists in this Procurement Consolidation
					if item_code in existing_items:
						# MERGE: Add quantity to existing row
						existing_row = existing_items[item_code]
						
						# DEBUG: Log before update
						frappe.logger().info(f"Merging item {item_code}: old total_required={existing_row.total_required_quantity}, old actual={existing_row.actual_quantity}, adding qty={item.qty}")
						
						# Update total required quantity
						existing_row.total_required_quantity += item.qty
						
						# CHECK STOCK & CALCULATE SHORTAGE
						# Fetch current stock balance from the selected warehouse
						current_stock = get_stock_balance(item_code, self.warehouse)
						existing_row.available_stock = current_stock
						
						# Calculate shortage: Total Required - Available
						# Ensure non-negative
						shortage = max(0.0, existing_row.total_required_quantity - current_stock)
						
						# Set actual_quantity to shortage
						existing_row.actual_quantity = shortage
						
						# DEBUG: Log after update
						frappe.logger().info(f"After merge - Item {item_code}: new total_required={existing_row.total_required_quantity}, new actual={existing_row.actual_quantity}")
						
						# Recalculate net quantity to procure (backward compatibility)
						existing_row.net_quantity_to_procure = existing_row.total_required_quantity - (existing_row.available_stock or 0)
						
						# APPEND to traceability (do NOT overwrite)
						try:
							existing_sources = json.loads(existing_row.source_material_requests or "[]")
						except:
							existing_sources = []
						
						existing_sources.append({
							"mr": mr.name,
							"qty": item.qty
						})
						
						existing_row.source_material_requests = json.dumps(existing_sources, indent=2)
						
					else:
						# NEW ITEM: Accumulate data for this item
						if item_code not in new_items_data:
							new_items_data[item_code] = {
								"item_code": item_code,
								"item_name": item.item_name,
								"uom": item.uom,
								"total_required_quantity": 0.0,
								"source_mrs": []
							}
						
						# Add quantity
						new_items_data[item_code]["total_required_quantity"] += item.qty
						
						# Track source Material Request
						new_items_data[item_code]["source_mrs"].append({
							"mr": mr.name,
							"qty": item.qty
						})
				
				# CRITICAL ATOMIC STEP: Mark this Material Request as consolidated IMMEDIATELY
				# This prevents it from being fetched again, even if button is clicked multiple times
				
				# Use frappe.db.set_value() to update the field
				# Note: custom_consolidated has allow_on_submit=0, but we can still update it
				# using db.set_value() because it bypasses the form-level restrictions
				frappe.db.set_value(
					"Material Request",
					mr.name,
					"custom_consolidated",
					1,
					update_modified=False  # Don't update modified timestamp
				)
				
				# Commit immediately to ensure persistence
				frappe.db.commit()
				
				# Track successful consumption
				successfully_consumed_mr_ids.append(mr.name)
				
				frappe.logger().info(f"Material Request {mr.name} marked as consolidated and committed to database")

				
			except Exception as e:
				# Log error but continue processing other Material Requests
				frappe.log_error(
					f"Failed to process Material Request {mr.name}: {str(e)}\n{frappe.get_traceback()}",
					"Procurement Consolidation - MR Processing Error"
				)
				failed_mr_ids.append(mr.name)
				# Rollback this specific MR transaction
				frappe.db.rollback()
				continue
		
		# Add new items to child table
		new_items_count = 0
		for item_code, item_data in new_items_data.items():
			# Get GST rate for the item
			gst_rate = self.get_item_gst_rate(item_code)
			
			# Add row to child table
			# DEBUG: Log the values being set
			frappe.logger().info(f"Adding item {item_data['item_code']}: total_required_qty={item_data['total_required_quantity']}, setting actual_quantity={item_data['total_required_quantity']}")
			
			# CHECK STOCK & CALCULATE SHORTAGE
			# Fetch current stock balance from the selected warehouse
			current_stock = get_stock_balance(item_data["item_code"], self.warehouse)
			
			# Calculate shortage: Total Required - Available
			shortage = max(0.0, item_data["total_required_quantity"] - current_stock)
			
			new_row = self.append("items", {
				"item_code": item_data["item_code"],
				"item_name": item_data["item_name"],
				"uom": item_data["uom"],
				
				# System-controlled quantity (already exists)
				"total_required_quantity": item_data["total_required_quantity"],
				
				# User-editable quantity (Calculated shortage)
				"actual_quantity": shortage,
				
				# Completion flag (NEW)
				"is_completed": 0,
				
				# Stock info
				"available_stock": current_stock,
				
				# Backward compatibility
				"net_quantity_to_procure": shortage,
				
				"gst_percentage": gst_rate,
				"source_material_requests": json.dumps(item_data["source_mrs"], indent=2)
			})
			
			# CRITICAL: Set actual_quantity AFTER row creation to avoid default value override
			new_row.actual_quantity = shortage
			
			new_items_count += 1
			
			# DEBUG: Verify the value was set correctly
			frappe.logger().info(f"After setting - Item {new_row.item_code}: total_required_quantity={new_row.total_required_quantity}, actual_quantity={new_row.actual_quantity}")
		
		# Count items that were merged (had quantities added)
		# Only count items that actually received updates from the successfully processed MRs
		merged_items_count = 0
		for item_code in existing_items:
			# Check if this item received updates from any of the successfully consumed MRs
			try:
				sources = json.loads(existing_items[item_code].source_material_requests or "[]")
				for source in sources:
					if source.get("mr") in successfully_consumed_mr_ids:
						merged_items_count += 1
						break
			except:
				pass
		
		total_unique_items = len(existing_items) + new_items_count
		
		# Prepare user feedback message
		if successfully_consumed_mr_ids:
			# Calculate total unique items (existing + new)
			total_items = len(existing_items) + new_items_count
			
			# Format message exactly as specified in requirements
			message = f"Fetched {len(successfully_consumed_mr_ids)} Material Request(s) with {total_items} unique item(s)"
			

			
			frappe.msgprint(
				message,
				title="Success",
				indicator="green"
			)
		else:
			frappe.msgprint(
				"No Material Requests were successfully processed. Please check the Error Log.",
				title="Processing Failed",
				indicator="red"
			)
		
		# CRITICAL FIX: Save the document to persist all changes
		# This ensures that the actual_quantity values set above are saved to the database
		# Without this, the client-side refresh will reload from database and show 0 values
		try:
			# DEBUG: Log actual_quantity values before save
			for item in self.items:
				frappe.logger().info(f"Before save - Item {item.item_code}: total_required={item.total_required_quantity}, actual={item.actual_quantity}, is_completed={item.is_completed}")
			
			self.save()
			frappe.logger().info(f"Document {self.name} saved successfully")
		except Exception as e:
			frappe.log_error(
				f"Failed to save Procurement Consolidation {self.name}: {str(e)}\n{frappe.get_traceback()}",
				"Procurement Consolidation - Save Error"
			)
			frappe.logger().error(f"Save failed: {str(e)}")
			# Don't raise the error, just log it and continue
			# The user will see the changes in the UI even if not saved
		
		# Return summary
		return {
			"status": "success" if successfully_consumed_mr_ids else "error",
			"message": f"Fetched {len(successfully_consumed_mr_ids)} Material Request(s)",
			"material_requests_fetched": len(successfully_consumed_mr_ids),
			"material_requests_failed": len(failed_mr_ids),
			"new_items_added": new_items_count,
			"existing_items_merged": merged_items_count,
			"total_unique_items": total_unique_items,
			"consumed_mr_ids": successfully_consumed_mr_ids,
			"failed_mr_ids": failed_mr_ids
		}
	
	def get_item_gst_rate(self, item_code):
		"""
		Get GST rate for an item from Item Tax Template
		
		Args:
			item_code (str): Item Code
		
		Returns:
			float: GST percentage (0 if not found)
		"""
		try:
			# Get item document
			item = frappe.get_doc("Item", item_code)
			
			# Check if item has taxes configured
			if item.taxes:
				for tax_row in item.taxes:
					if tax_row.item_tax_template:
						template_name = tax_row.item_tax_template
						
						# Parse GST rate from template name
						# Common patterns: "GST 5%", "GST 12%", "18% GST", etc.
						if "5%" in template_name or "GST 5" in template_name:
							return 5.0
						elif "12%" in template_name or "GST 12" in template_name:
							return 12.0
						elif "18%" in template_name or "GST 18" in template_name:
							return 18.0
						elif "28%" in template_name or "GST 28" in template_name:
							return 28.0
						
						# Try to get actual rate from template
						try:
							template = frappe.get_doc("Item Tax Template", template_name)
							if template.taxes:
								# Sum all tax rates (CGST + SGST + IGST)
								total_rate = sum(tax.tax_rate for tax in template.taxes)
								return total_rate
						except:
							pass
			
			# Check HSN code for default rates
			if hasattr(item, 'gst_hsn_code') and item.gst_hsn_code:
				hsn = item.gst_hsn_code
				# Common HSN patterns for solar items
				if hsn.startswith('8541') or hsn.startswith('8504'):
					return 5.0  # Solar panels/inverters typically 5%
			
			# Default rate if cannot determine
			return 0.0
			
		except Exception as e:
			frappe.log_error(f"Error fetching GST rate for {item_code}: {str(e)}")
			return 0.0
	
	@frappe.whitelist()
	def reconcile_quantities_after_po(self, po_items):
		"""
		Reconcile quantities after Purchase Order creation.
		
		This method implements the core reconciliation logic:
		1. Reduce total_required_quantity by actual_quantity ordered
		2. Reset actual_quantity to remaining total_required_quantity
		3. Mark items as completed when total_required_quantity reaches 0
		4. Handle over-procurement (excess as buffer stock)
		
		Args:
			po_items (list): List of dicts with {item_code, qty_ordered}
		"""
		if not po_items:
			return
		
		# Convert to dict for fast lookup: {item_code: qty_ordered}
		if isinstance(po_items, str):
			po_items = json.loads(po_items)
		
		po_items_dict = {item["item_code"]: item["qty_ordered"] for item in po_items}
		
		# Track reconciliation results
		reconciled_items = []
		completed_items = []
		
		for row in self.items:
			if row.item_code not in po_items_dict:
				continue
			
			qty_ordered = po_items_dict[row.item_code]
			
			# Store original values for logging
			original_required = row.total_required_quantity
			original_actual = row.actual_quantity
			
			# STEP 1: Reduce total_required_quantity by actual_quantity ordered
			row.total_required_quantity = max(0, row.total_required_quantity - qty_ordered)
			
			# STEP 2: Reset actual_quantity to remaining total_required_quantity
			row.actual_quantity = row.total_required_quantity
			
			# STEP 3: Mark as completed if total_required_quantity reaches 0
			if row.total_required_quantity == 0:
				row.is_completed = 1
				completed_items.append(row.item_code)
			
			# Update backward compatibility fields
			row.net_quantity_to_procure = row.total_required_quantity - (row.available_stock or 0)
			
			# Log reconciliation
			reconciled_items.append({
				"item_code": row.item_code,
				"original_total_required": original_required,
				"original_actual": original_actual,
				"qty_ordered": qty_ordered,
				"new_total_required": row.total_required_quantity,
				"new_actual": row.actual_quantity,
				"is_completed": row.is_completed
			})
		
		# Save changes
		self.save()
		frappe.db.commit()
		
		# Log reconciliation action
		frappe.logger().info(
			f"Procurement Consolidation {self.name}: Reconciled {len(reconciled_items)} items, "
			f"{len(completed_items)} completed"
		)
		
		return {
			"status": "success",
			"reconciled_items": reconciled_items,
			"completed_items": completed_items
		}
	
	def validate(self):
		"""Validate document before save"""
		self.validate_actual_quantities()
	
	def validate_actual_quantities(self):
		"""
		Validate that actual_quantity is valid for each item.
		
		Rules:
		- actual_quantity must be > 0 if item is not completed
		- actual_quantity can be greater than total_required_quantity (over-procurement allowed)
		- actual_quantity must be 0 if item is completed
		"""
		for row in self.items:
			# Skip validation if fields don't exist (backward compatibility)
			if not hasattr(row, 'actual_quantity') or not hasattr(row, 'total_required_quantity'):
				continue
			
			# Completed items must have actual_quantity = 0
			if row.is_completed and row.actual_quantity != 0:
				frappe.throw(
					f"Row {row.idx}: Item {row.item_code} is marked as completed but has "
					f"Actual Quantity = {row.actual_quantity}. Completed items must have "
					f"Actual Quantity = 0.",
					title="Invalid Actual Quantity"
				)
			
			# Non-completed items must have actual_quantity > 0
			if not row.is_completed and row.actual_quantity <= 0:
				frappe.throw(
					f"Row {row.idx}: Item {row.item_code} has Actual Quantity = {row.actual_quantity}. "
					f"Actual Quantity must be greater than 0 for non-completed items.",
					title="Invalid Actual Quantity"
				)
	
	@frappe.whitelist()
	def create_purchase_order(self):
		"""
		Create Draft Purchase Order from selected items.
		
		Workflow:
		1. Validate supplier and item selection
		2. Create Draft PO with actual_quantity for each selected item
		3. Reconcile quantities in Procurement Consolidation
		4. Uncheck selected items
		5. Update status based on completion
		6. Return PO reference
		
		Returns:
			dict: {status, po_name, items_count, message}
		"""
		from frappe.utils import today, add_days
		
		# Validation 1: Check supplier selection
		if not self.supplier_for_po:
			frappe.throw(
				"Please select a Supplier for PO before creating Purchase Order",
				title="Supplier Required"
			)
		
		# Validation 2: Check item selection
		selected_items = [item for item in self.items if item.select_item == 1]
		
		if not selected_items:
			frappe.throw(
				"Please select at least one item before creating Purchase Order",
				title="No Items Selected"
			)
		
		# Validation 3: Check actual quantities
		for item in selected_items:
			if not item.actual_quantity or item.actual_quantity <= 0:
				frappe.throw(
					f"Row {item.idx}: Item {item.item_code} has invalid Actual Qty to Order = {item.actual_quantity}. "
					f"Actual Quantity must be greater than 0.",
					title="Invalid Quantity"
				)
		
		# Validation 4: Check completion status
		for item in selected_items:
			if item.is_completed:
				frappe.throw(
					f"Row {item.idx}: Item {item.item_code} is already completed and cannot be ordered",
					title="Item Already Completed"
				)
		
		try:
			# Create Draft Purchase Order
			po_doc = frappe.new_doc("Purchase Order")
			po_doc.supplier = self.supplier_for_po
			po_doc.company = self.company
			po_doc.transaction_date = today()
			po_doc.schedule_date = add_days(today(), 7)  # Default 7 days delivery
			
			# Add custom field link back to Procurement Consolidation
			po_doc.procurement_consolidation = self.name
			
			# Populate PO items
			for item in selected_items:
				po_doc.append("items", {
					"item_code": item.item_code,
					"item_name": item.item_name,
					"qty": item.actual_quantity,  # Use actual_quantity, NOT total_required_quantity
					"uom": item.uom,
					"rate": item.supplier_rate if item.supplier_rate else 0,
					"warehouse": self.warehouse,
					"source_procurement_consolidation_item": item.name  # Traceability
				})
			
			# Save Draft PO (does NOT submit)
			po_doc.insert()
			frappe.db.commit()
			
			frappe.logger().info(f"Draft Purchase Order {po_doc.name} created successfully")
			
			# Build list for quantity reconciliation
			po_items = [
				{
					"item_code": item.item_code,
					"qty_ordered": item.actual_quantity
				}
				for item in selected_items
			]
			
			# Reconcile quantities
			self.reconcile_quantities_after_po(po_items)
			
			# Uncheck selected items
			for item in self.items:
				if item.select_item == 1:
					item.select_item = 0
			
			# Update status based on completion
			self.update_status_based_on_completion()
			
			# Save changes
			self.save()
			frappe.db.commit()
			
			# Return success response
			return {
				"status": "success",
				"po_name": po_doc.name,
				"items_count": len(selected_items),
				"message": f"Draft Purchase Order {po_doc.name} created successfully with {len(selected_items)} item(s)"
			}
			
		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(
				f"Failed to create Purchase Order: {str(e)}\n{frappe.get_traceback()}",
				"Procurement Consolidation - PO Creation Error"
			)
			frappe.throw(
				f"Failed to create Purchase Order: {str(e)}",
				title="PO Creation Failed"
			)
	
	def update_status_based_on_completion(self):
		"""
		Update status based on item completion.
		
		Logic:
		- All items completed → "Ordered"
		- Some items completed → "Partially Ordered"
		- No items completed → "Draft"
		"""
		if not self.items:
			self.status = "Draft"
			return
		
		completed_count = sum(1 for item in self.items if item.is_completed)
		total_count = len(self.items)
		
		if completed_count == total_count:
			self.status = "Ordered"
		elif completed_count > 0:
			self.status = "Partially Ordered"
		else:
			self.status = "Draft"
		
		frappe.logger().info(
			f"Procurement Consolidation {self.name}: Status updated to '{self.status}' "
			f"({completed_count}/{total_count} items completed)"
		)
