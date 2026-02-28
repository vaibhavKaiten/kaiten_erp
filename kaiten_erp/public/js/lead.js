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
    refresh(frm) {
        prune_lead_toolbar(frm);
        setTimeout(() => prune_lead_toolbar(frm), 150);
    },
});
