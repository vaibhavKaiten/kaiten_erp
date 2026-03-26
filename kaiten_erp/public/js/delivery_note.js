frappe.ui.form.on("Delivery Note", {
    refresh: function (frm) {
        // Only pre-populate on new (unsaved) DNs, and only once per form instance
        if (!frm.is_new()) return;
        if (frm.__ts_items_populated) return;

        // Find the Sales Order from item rows (set by ERPNext when creating DN from SO)
        let so_name = null;
        (frm.doc.items || []).forEach(function (item) {
            if (item.against_sales_order && !so_name) {
                so_name = item.against_sales_order;
            }
        });

        // Fallback: check against_sales_order on the DN header
        if (!so_name && frm.doc.against_sales_order) {
            so_name = frm.doc.against_sales_order;
        }

        // No SO link found — leave form untouched (e.g. direct DN)
        if (!so_name) return;

        // Set flag BEFORE the async call so a concurrent refresh doesn't double-fire
        frm.__ts_items_populated = true;

        frappe.call({
            method: "kaiten_erp.kaiten_erp.doc_events.delivery_note_events.get_remaining_ts_items",
            args: { sales_order_name: so_name },
            callback: function (r) {
                if (!r.message || !r.message.length) return;

                frm.clear_table("items");

                r.message.forEach(function (item) {
                    let row = frm.add_child("items");
                    row.item_code = item.item_code;
                    row.item_name = item.item_name;
                    row.qty = item.qty;
                    row.uom = item.uom;
                    row.stock_uom = item.stock_uom || item.uom;
                    row.conversion_factor = 1;
                    if (frm.doc.set_warehouse) {
                        row.warehouse = frm.doc.set_warehouse;
                    }
                });

                // Track the SO link on the DN header
                frm.doc.against_sales_order = so_name;

                frm.refresh_field("items");
                frm.refresh_field("against_sales_order");

                frappe.show_alert({
                    message: __("Items loaded from Technical Survey (remaining to deliver)"),
                    indicator: "green"
                }, 5);
            },
            error: function (err) {
                // Allow retry if the API errored (clear the flag)
                frm.__ts_items_populated = false;
                frappe.msgprint({
                    title: __("Could not load Technical Survey items"),
                    indicator: "red",
                    message: err.message || __("An error occurred while fetching Technical Survey items.")
                });
            }
        });
    }
});
