function prune_lead_toolbar(frm) {
    // Remove "Add to Prospect"
    frm.page.remove_inner_button(__('Add to Prospect'), __('Action'));
    frm.page.remove_inner_button(__('Add to Prospect'));

    // Drop the entire Create dropdown (removes all make options)
    frm.page.remove_inner_button(__('Customer'), __('Create'));
    frm.page.remove_inner_button(__('Opportunity'), __('Create'));
    frm.page.remove_inner_button(__('Quotation'), __('Create'));
    frm.page.remove_inner_button(__('Prospect'), __('Create'));
    frm.page.remove_inner_button(('Create'));
    frm.page.inner_toolbar
        .find('.menu-btn-group .dropdown:has(.dropdown-toggle:contains("Create"))')
        .remove();
}

frappe.ui.form.on('Lead', {
    setup(frm) {
        frm.set_query('custom_active_sales_manager', function () {
            return {
                query: 'kaiten_erp.kaiten_erp.api.assignment_filter.get_active_sales_managers_for_territory',
                filters: { territory: frm.doc.territory || '' }
            };
        });
    },

    refresh(frm) {
        prune_lead_toolbar(frm);
        setTimeout(() => prune_lead_toolbar(frm), 150);
    },

    territory(frm) {
        if (frm.doc.custom_active_sales_manager) {
            frm.set_value('custom_active_sales_manager', '');
        }
        frm.set_query('custom_active_sales_manager', function () {
            return {
                query: 'kaiten_erp.kaiten_erp.api.assignment_filter.get_active_sales_managers_for_territory',
                filters: { territory: frm.doc.territory || '' }
            };
        });
    },

    custom_pincode(frm) {
        const pincode = (frm.doc.custom_pincode || '').trim();
        if (!pincode || pincode.length !== 6 || !/^\d{6}$/.test(pincode)) return;

        fetch(`https://api.postalpincode.in/pincode/${pincode}`)
            .then(res => res.json())
            .then(data => {
                if (data && data[0] && data[0].Status === 'Success') {
                    const po = data[0].PostOffice[0];
                    if (po.District) frm.set_value('city', po.District);
                    if (po.State) frm.set_value('state', po.State);
                    frm.set_value('country', 'India');
                }
            })
            .catch(() => {
                frappe.show_alert({ message: __('Could not fetch pincode details'), indicator: 'orange' });
            });
    },
});
