frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {
        if (!frm.is_new()) return;
        if (frm.__saleable_item_populated) return;

        // Resolve delivery_note and sales_order from item rows
        let dn_name = null;
        let so_name = null;
        (frm.doc.items || []).forEach(function (item) {
            if (item.delivery_note && !dn_name) dn_name = item.delivery_note;
            if (item.sales_order && !so_name) so_name = item.sales_order;
        });

        if (!dn_name && !so_name) return;

        frm.__saleable_item_populated = true;

        frappe.call({
            method: "kaiten_erp.kaiten_erp.doc_events.sales_invoice_events.get_saleable_item_for_si",
            args: { delivery_note: dn_name, sales_order: so_name },
            callback: function (r) {
                if (!r.message) return;

                var item = r.message;

                frm.clear_table("items");
                var row = frm.add_child("items");
                row.item_code = item.item_code;
                row.item_name = item.item_name;
                row.qty = item.qty;
                row.uom = item.uom;
                row.stock_uom = item.stock_uom;
                row.conversion_factor = 1;
                row.rate = item.rate;
                row.price_list_rate = item.price_list_rate;
                row.description = item.description;
                row.sales_order = item.sales_order;
                if (dn_name) row.delivery_note = dn_name;

                frm.set_value("custom_technical_survey", item.technical_survey);
                frm.set_value("custom_sales_order", item.sales_order);

                frm.refresh_field("items");
                frm.refresh_field("custom_technical_survey");
                frm.refresh_field("custom_sales_order");

                frappe.show_alert({
                    message: __("Items replaced with saleable item from Technical Survey"),
                    indicator: "green"
                }, 5);
            },
            error: function () {
                frm.__saleable_item_populated = false;
            }
        });
    }
});
