// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Job File", {
    setup: function (frm) {
        // Filter proposed_system to only show items from "Products" group with BOMs
        frm.set_query('proposed_system', function () {
            return {
                query: 'kaiten_erp.kaiten_erp.api.technical_survey_bom.get_items_with_bom',
                filters: {
                    item_group: 'Products'
                }
            };
        });
    },

    proposed_system: function (frm) {
        // Fetch and populate item price into mrp field when proposed_system is selected
        if (frm.doc.proposed_system) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Price',
                    filters: {
                        item_code: frm.doc.proposed_system,
                        selling: 1
                    },
                    fieldname: 'price_list_rate'
                },
                callback: function (r) {
                    if (r.message && r.message.price_list_rate) {
                        frm.set_value('mrp', r.message.price_list_rate);
                    } else {
                        // If no selling price found, try to get standard rate from Item
                        frappe.call({
                            method: 'frappe.client.get_value',
                            args: {
                                doctype: 'Item',
                                filters: {
                                    name: frm.doc.proposed_system
                                },
                                fieldname: 'standard_rate'
                            },
                            callback: function (r) {
                                if (r.message && r.message.standard_rate) {
                                    frm.set_value('mrp', r.message.standard_rate);
                                }
                            }
                        });
                    }
                }
            });
        } else {
            // Clear mrp if proposed_system is cleared
            frm.set_value('mrp', 0);
        }
    }
});
