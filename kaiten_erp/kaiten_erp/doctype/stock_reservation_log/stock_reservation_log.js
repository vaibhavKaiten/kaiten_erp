// Copyright (c) 2025, KaitenSoftware and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Reservation Log', {
    refresh: function (frm) {
        set_indicator(frm);
        add_action_buttons(frm);
    }
});


function set_indicator(frm) {
    const status_colors = {
        'Reserved': 'blue',
        'Partially Reserved': 'yellow',
        'Partially Consumed': 'orange',
        'Consumed': 'green',
        'Released': 'grey',
        'Cancelled': 'red'
    };

    const color = status_colors[frm.doc.status] || 'grey';
    frm.page.set_indicator(frm.doc.status, color);
}


function add_action_buttons(frm) {
    if (frm.is_new()) return;

    const is_admin = frappe.user.has_role('System Manager') || frappe.user.has_role('Administrator');
    const is_active = ['Reserved', 'Partially Reserved', 'Partially Consumed'].includes(frm.doc.status);

    // Admin Override - Release reservation
    if (is_admin && is_active) {
        frm.add_custom_button(__('Release Reservation'), function () {
            frappe.prompt({
                fieldtype: 'Small Text',
                label: __('Override Reason (MANDATORY)'),
                fieldname: 'reason',
                reqd: 1
            }, function (values) {
                frappe.call({
                    method: 'kaiten_erp.kaiten_erp.api.bom_stock_reservation.admin_release_reservation',
                    args: {
                        reservation_name: frm.doc.name,
                        reason: values.reason
                    },
                    callback: function (r) {
                        if (r.message && r.message.status === 'success') {
                            frappe.show_alert({
                                message: __('Reservation released'),
                                indicator: 'orange'
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }, __('Admin Override'), __('Release'));
        }, __('Actions')).addClass('btn-warning');
    }

    // View linked Sales Order
    if (frm.doc.sales_order) {
        frm.add_custom_button(__('View Sales Order'), function () {
            frappe.set_route('Form', 'Sales Order', frm.doc.sales_order);
        }, __('Links'));
    }

    // View linked Delivery Note
    if (frm.doc.delivery_note) {
        frm.add_custom_button(__('View Delivery Note'), function () {
            frappe.set_route('Form', 'Delivery Note', frm.doc.delivery_note);
        }, __('Links'));
    }
}
