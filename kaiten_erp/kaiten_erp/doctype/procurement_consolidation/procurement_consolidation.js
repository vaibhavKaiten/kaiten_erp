// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Consolidated Procurement Item", {
	item_code(frm, cdt, cdn) {
		_set_available_stock(frm, cdt, cdn);
	},
	warehouse(frm, cdt, cdn) {
		_set_available_stock(frm, cdt, cdn);
	},
});

frappe.ui.form.on("Procurement Consolidation", {
	refresh(frm) {
		// "Fetch Approved Material Requests" — available in Draft and Consolidated states
		if (!frm.is_new() && ["Draft", "Consolidated"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Fetch Approved Material Requests"), function () {
				_fetch_approved_mrs(frm);
			});
		}

		// "Create Purchase Order" — available when items exist and not yet Completed
		if (
			!frm.is_new() &&
			frm.doc.items &&
			frm.doc.items.length > 0 &&
			frm.doc.status !== "Completed"
		) {
			frm.add_custom_button(
				__("Create Purchase Order"),
				function () {
					_create_purchase_orders(frm);
				},
				__("Actions")
			);
		}
	},
});

// ---------------------------------------------------------------------------
// Fetch Approved Material Requests
// ---------------------------------------------------------------------------

function _fetch_approved_mrs(frm) {
	frappe.confirm(
		__(
			"This will fetch all approved Purchase Material Requests with pending quantities " +
			"and rebuild the items table. Continue?"
		),
		function () {
			frappe.dom.freeze(__("Fetching and consolidating Material Requests…"));
			frm.call({
				method: "fetch_approved_material_requests",
				doc: frm.doc,
				callback(r) {
					frappe.dom.unfreeze();
					if (r.message) {
						if (r.message.status === "success") {
							frm.reload_doc();
						}
						// no_data case already shows a message from server
					}
				},
				error() {
					frappe.dom.unfreeze();
					frappe.msgprint({
						title: __("Error"),
						message: __("Failed to fetch Material Requests. Check the Error Log."),
						indicator: "red",
					});
				},
			});
		}
	);
}

// ---------------------------------------------------------------------------
// Available stock lookup (per child-table row)
// ---------------------------------------------------------------------------

function _set_available_stock(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.item_code || !row.warehouse) {
		frappe.model.set_value(cdt, cdn, "available_stock", 0);
		return;
	}
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Bin",
			filters: { item_code: row.item_code, warehouse: row.warehouse },
			fieldname: "actual_qty",
		},
		callback(r) {
			const qty = (r.message && r.message.actual_qty) || 0;
			frappe.model.set_value(cdt, cdn, "available_stock", qty);
		},
	});
}

// ---------------------------------------------------------------------------
// Create Purchase Orders (one per supplier)
// ---------------------------------------------------------------------------

function _create_purchase_orders(frm) {
	const selected = (frm.doc.items || []).filter(
		(item) => item.select_item && (item.actual_quantity || 0) > 0
	);

	if (!selected.length) {
		frappe.msgprint({
			title: __("No Items Selected"),
			message: __(
				"Select at least one item (checkbox) with Actual Qty to Order > 0."
			),
			indicator: "orange",
		});
		return;
	}

	// Validate: every selected item must have a supplier
	const missing = selected.filter((item) => !item.supplier);
	if (missing.length) {
		frappe.msgprint({
			title: __("Supplier Required"),
			message: __(
				"Please assign a Supplier to every selected item before creating Purchase Orders. " +
				"Missing for: " +
				missing.map((i) => i.item_code).join(", ")
			),
			indicator: "orange",
		});
		return;
	}

	// Group summary for confirmation dialog
	const by_supplier = {};
	selected.forEach((item) => {
		if (!by_supplier[item.supplier]) by_supplier[item.supplier] = [];
		by_supplier[item.supplier].push(item);
	});

	const supplier_lines = Object.entries(by_supplier)
		.map(
			([sup, items]) =>
				`<b>${sup}</b>: ${items.length} item(s), total qty = ${items
					.reduce((s, i) => s + (i.actual_quantity || 0), 0)
					.toFixed(2)}`
		)
		.join("<br>");

	frappe.confirm(
		__(
			`<b>Create ${Object.keys(by_supplier).length} Purchase Order(s)?</b><br><br>` +
			supplier_lines +
			"<br><br>One Draft PO will be created per supplier."
		),
		function () {
			frappe.dom.freeze(__("Creating Purchase Orders…"));
			frm.call({
				method: "create_purchase_order",
				doc: frm.doc,
				callback(r) {
					frappe.dom.unfreeze();
					if (r.message && r.message.status === "success") {
						const po_links = (r.message.po_names || [])
							.map(
								(po) =>
									`<a href="/app/purchase-order/${po}" target="_blank">${po}</a>`
							)
							.join(", ");
						frappe.msgprint({
							title: __("Purchase Orders Created"),
							message: __(
								`${r.message.po_count} Purchase Order(s) created: ${po_links}`
							),
							indicator: "green",
						});
						frm.reload_doc();
					}
				},
				error() {
					frappe.dom.unfreeze();
					frappe.msgprint({
						title: __("Error"),
						message: __(
							"Failed to create Purchase Orders. Check the Error Log."
						),
						indicator: "red",
					});
				},
			});
		}
	);
}

