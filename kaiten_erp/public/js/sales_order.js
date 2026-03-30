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
    },

    custom_finance_type: function(frm) {
        // Clear existing rows first
        frm.clear_table('custom_payment_plan');

        if (!frm.doc.custom_finance_type) {
            frm.refresh_field('custom_payment_plan');
            return;
        }

        // Fetch the Payment Milestone Template and populate custom_payment_plan
        frappe.db.get_doc('Payment Milestone Template', frm.doc.custom_finance_type)
            .then(template => {
                if (!template || !template.payment_milestone) return;

                template.payment_milestone.forEach(row => {
                    let child = frm.add_child('custom_payment_plan');
                    child.milestone      = row.milestone;
                    child.payment_source = row.payment_source;
                    child.amount         = row.amount;
                    child.stage          = row.stage;
                    child.status         = row.status;
                });

                frm.refresh_field('custom_payment_plan');
            });
    }
});
