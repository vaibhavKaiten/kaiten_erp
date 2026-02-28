// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on('Procurement Consolidation', {
    refresh: function (frm) {
        // Add "Fetch Approved Material Requests" button
        // Only show in Draft status
        if (frm.doc.status === 'Draft' && !frm.is_new()) {
            frm.add_custom_button(__('Fetch Approved Material Requests'), function () {
                fetch_approved_material_requests(frm);
            });
        }

        // Add "Create Purchase Order" button
        // Show when there are items and supplier is selected
        if (frm.doc.items && frm.doc.items.length > 0 && !frm.is_new()) {
            frm.add_custom_button(__('Create Purchase Order'), function () {
                create_purchase_order_from_selected(frm);
            }, __('Actions'));
        }
    }
});

/**
 * Fetch Approved Material Requests
 * Calls server-side method to consolidate Material Request items
 */
function fetch_approved_material_requests(frm) {
    frappe.confirm(
        __('This will fetch all approved Material Requests and consolidate items. Any existing items in the table will be cleared. Continue?'),
        function () {
            // Show loading indicator
            frappe.dom.freeze(__('Fetching and consolidating Material Requests...'));

            // Call server-side method
            frm.call({
                method: 'fetch_approved_material_requests',
                doc: frm.doc,
                callback: function (r) {
                    frappe.dom.unfreeze();

                    if (r.message) {
                        const result = r.message;

                        if (result.status === 'success') {
                            // Show success message
                            frappe.msgprint({
                                title: __('Success'),
                                message: __(result.message),
                                indicator: 'green'
                            });

                            // Refresh the form to show populated items
                            frm.refresh_field('items');
                            frm.dirty();

                        } else if (result.status === 'no_data') {
                            // No data found
                            frappe.msgprint({
                                title: __('No Data'),
                                message: __(result.message),
                                indicator: 'orange'
                            });
                        }
                    }
                },
                error: function (r) {
                    frappe.dom.unfreeze();
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to fetch Material Requests. Please check the console for details.'),
                        indicator: 'red'
                    });
                    console.error('Fetch error:', r);
                }
            });
        }
    );
}

/**
 * Create Purchase Order from Selected Items
 * Validates supplier selection and item selection before PO creation
 */
function create_purchase_order_from_selected(frm) {
    // Validation 1: Check if supplier is selected
    if (!frm.doc.supplier_for_po) {
        frappe.msgprint({
            title: __('Supplier Required'),
            message: __('Please select a Supplier for PO before creating Purchase Order.'),
            indicator: 'orange'
        });
        return;
    }

    // Validation 2: Check if any items are selected
    const selected_items = frm.doc.items.filter(item => item.select_item === 1);

    if (selected_items.length === 0) {
        frappe.msgprint({
            title: __('No Items Selected'),
            message: __('Please select at least one item using the checkbox before creating Purchase Order.'),
            indicator: 'orange'
        });
        return;
    }

    // Validation 3: Check if selected items have actual quantities to order
    const items_without_qty = selected_items.filter(item =>
        !item.actual_quantity || item.actual_quantity <= 0
    );

    if (items_without_qty.length > 0) {
        frappe.msgprint({
            title: __('Invalid Quantities'),
            message: __('Some selected items have zero or invalid Actual Qty to Order. Please set quantities before creating Purchase Order.'),
            indicator: 'orange'
        });
        return;
    }

    // Show summary and confirmation
    const total_items = selected_items.length;
    const total_qty = selected_items.reduce((sum, item) => sum + (item.actual_quantity || 0), 0);

    frappe.confirm(
        __('Create Purchase Order for Supplier: {0}<br><br>Selected Items: {1}<br>Total Actual Qty to Order: {2}<br><br>Continue?',
            [frm.doc.supplier_for_po, total_items, total_qty.toFixed(2)]),
        function () {
            // Show loading indicator
            frappe.dom.freeze(__('Creating Draft Purchase Order...'));

            // Call server-side method
            frm.call({
                method: 'create_purchase_order',
                doc: frm.doc,
                callback: function (r) {
                    frappe.dom.unfreeze();

                    if (r.message && r.message.status === 'success') {
                        // Show success message with PO link
                        frappe.msgprint({
                            title: __('Purchase Order Created'),
                            message: __('Draft Purchase Order <a href="/app/purchase-order/{0}" target="_blank">{0}</a> created successfully.<br><br>Items: {1}<br><br>Quantities have been reconciled in Procurement Consolidation.',
                                [r.message.po_name, r.message.items_count]),
                            indicator: 'green'
                        });

                        // Refresh form to show updated quantities and status
                        frm.reload_doc();
                    }
                },
                error: function (r) {
                    frappe.dom.unfreeze();
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to create Purchase Order. Please check the error log for details.'),
                        indicator: 'red'
                    });
                    console.error('PO Creation Error:', r);
                }
            });
        }
    );
}
