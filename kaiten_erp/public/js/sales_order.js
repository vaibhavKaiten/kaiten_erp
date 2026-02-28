// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sales Order', {
    setup: function(frm) {
        // Filter item_code in Sales Order Item child table to only show items from "Products" group with BOMs
        frm.set_query('item_code', 'items', function() {
            return {
                query: 'kaiten_erp.kaiten_erp.api.technical_survey_bom.get_items_with_bom',
                filters: {
                    item_group: 'Products'
                }
            };
        });
    }
});
