function prune_opportunity_toolbar(frm) {
    frm.page.remove_inner_button(__('Supplier Quotation'), __('Create'));
    frm.page.remove_inner_button(__('Request For Quotation'), __('Create'));
}

frappe.ui.form.on('Opportunity', {
    refresh(frm) {
        prune_opportunity_toolbar(frm);
        setTimeout(() => prune_opportunity_toolbar(frm), 150);
    },
});
