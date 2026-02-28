/**
 * Supplier Form - Add Portal User with Auto-linking
 * Adds a button to create vendor portal users and automatically link them to the supplier
 */

frappe.ui.form.on('Supplier', {
    refresh: function (frm) {
        // Add button to create vendor portal users
        if (!frm.is_new()) {
            add_create_portal_user_button(frm);
            add_link_existing_user_button(frm);
        }
    }
});

function add_create_portal_user_button(frm) {
    /**
     * Add "Create Vendor Portal User" button to Supplier form
     * This creates a Contact, User, and automatically links them to the Supplier
     */

    frm.add_custom_button(__('Create Vendor Portal User'), function () {
        // Show dialog to collect user details
        let d = new frappe.ui.Dialog({
            title: __('Create Vendor Portal User'),
            fields: [
                {
                    fieldname: 'user_type',
                    fieldtype: 'Select',
                    label: __('User Type'),
                    options: ['Vendor Manager', 'Vendor Executive'],
                    reqd: 1,
                    default: 'Vendor Manager'
                },
                {
                    fieldname: 'section_break_1',
                    fieldtype: 'Section Break'
                },
                {
                    fieldname: 'first_name',
                    fieldtype: 'Data',
                    label: __('First Name'),
                    reqd: 1
                },
                {
                    fieldname: 'last_name',
                    fieldtype: 'Data',
                    label: __('Last Name')
                },
                {
                    fieldname: 'column_break_1',
                    fieldtype: 'Column Break'
                },
                {
                    fieldname: 'email',
                    fieldtype: 'Data',
                    label: __('Email'),
                    reqd: 1,
                    description: __('This will be the login email')
                },
                {
                    fieldname: 'mobile_no',
                    fieldtype: 'Data',
                    label: __('Mobile Number')
                },
                {
                    fieldname: 'section_break_2',
                    fieldtype: 'Section Break'
                },
                {
                    fieldname: 'send_welcome_email',
                    fieldtype: 'Check',
                    label: __('Send Welcome Email'),
                    default: 1
                }
            ],
            primary_action_label: __('Create User'),
            primary_action: function (values) {
                // Call server-side method to create user
                frappe.call({
                    method: 'kaiten_erp.kaiten_erp.api.supplier_portal.create_vendor_portal_user',
                    args: {
                        supplier_name: frm.doc.name,
                        first_name: values.first_name,
                        last_name: values.last_name,
                        email: values.email,
                        mobile_no: values.mobile_no,
                        user_type: values.user_type,
                        send_welcome_email: values.send_welcome_email
                    },
                    freeze: true,
                    freeze_message: __('Creating portal user...'),
                    callback: function (r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Portal user {0} created and linked to {1}',
                                    [r.message.user_email, frm.doc.name]),
                                indicator: 'green'
                            }, 10);

                            d.hide();
                            frm.reload_doc();

                            // Show success details
                            frappe.msgprint({
                                title: __('Portal User Created'),
                                message: __('User: {0}<br>Contact: {1}<br>Linked to Supplier: {2}',
                                    [r.message.user_email, r.message.contact_name, frm.doc.name]),
                                indicator: 'green'
                            });
                        } else if (r.message && r.message.error) {
                            frappe.msgprint({
                                title: __('Error'),
                                message: r.message.error,
                                indicator: 'red'
                            });
                        }
                    },
                    error: function (r) {
                        frappe.msgprint({
                            title: __('Error'),
                            message: __('Failed to create portal user. Please try again.'),
                            indicator: 'red'
                        });
                    }
                });
            }
        });

        d.show();
    }, __('Portal Users')).addClass('btn-primary');
}

