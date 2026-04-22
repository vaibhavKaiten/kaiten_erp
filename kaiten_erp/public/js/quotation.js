frappe.ui.form.on('Quotation', {
    onload: function (frm) {
        if (frm.is_new()) {
            frappe.after_ajax(() => fill_missing_item_details(frm));
        }
    },

    refresh: function (frm) {
        frm.trigger('apply_stage_ui');
        frm.trigger('set_technical_survey_query');
        frm.trigger('fetch_opportunity_details');
        frm.trigger('apply_negotiated_amount');

        // Follow-up reschedule button (submitted, not Ordered/Lost)
        if (frm.doc.docstatus === 1 && !['Ordered', 'Lost'].includes(frm.doc.status)) {
            frm.add_custom_button(__('Reschedule Follow-up'), function () {
                frappe.prompt(
                    {
                        label: __('New Follow-up Date'),
                        fieldname: 'new_date',
                        fieldtype: 'Date',
                        reqd: 1,
                        default: frm.doc.custom_next_followup_date || frappe.datetime.add_days(frappe.datetime.nowdate(), 4),
                    },
                    function (values) {
                        frappe.call({
                            method: 'kaiten_erp.kaiten_erp.api.quotation_workflow.reschedule_followup',
                            args: { docname: frm.doc.name, new_date: values.new_date },
                            callback: function (r) {
                                frm.reload_doc();
                            }
                        });
                    },
                    __('Reschedule Follow-up'),
                    __('Update')
                );
            }, __('Actions'));
        }
    },

    opportunity: function (frm) {
        frm.trigger('set_technical_survey_query');
        frm.trigger('fetch_opportunity_details');
    },

    custom_job_file: function (frm) {
        frm.trigger('apply_negotiated_amount');
    },

    apply_negotiated_amount: function (frm) {
        // Only draft, must have job file and items
        if (frm.doc.docstatus !== 0) return;
        if (!frm.doc.custom_job_file) return;
        if (!frm.doc.items || frm.doc.items.length === 0) return;
        // Final Approved stage is locked server-side — skip
        if (frm.doc.custom_quotation_stage === 'Final Approved') return;

        frappe.db.get_value('Job File', frm.doc.custom_job_file, 'negotiated_amount', (r) => {
            if (!r || !r.negotiated_amount) return;
            const rate = flt(r.negotiated_amount);
            (frm.doc.items || []).forEach(row => {
                frappe.model.set_value(row.doctype, row.name, 'rate', rate);
                frappe.model.set_value(row.doctype, row.name, 'amount', flt(row.qty || 1) * rate);
            });
            frm.refresh_field('items');
        });
    },

    custom_quotation_stage: function (frm) {
        frm.trigger('apply_stage_ui');
    },

    apply_stage_ui: function (frm) {
        const is_final = frm.doc.custom_quotation_stage === 'Final Approved';
        frm.toggle_reqd('custom_technical_survey', is_final);
    },

    set_technical_survey_query: function (frm) {
        frm.set_query('custom_technical_survey', function () {
            const filters = {
                workflow_state: 'Approved'
            };

            if (frm.doc.opportunity) {
                filters.custom_opportunity = frm.doc.opportunity;
            }

            return { filters };
        });
    },

    fetch_opportunity_details: function (frm) {
        if (!frm.doc.opportunity) return;
        if (frm.doc.items && frm.doc.items.length > 0) return;

        frappe.db.get_value(
            'Opportunity',
            frm.doc.opportunity,
            ['custom_proposed_system', 'opportunity_amount', 'custom_job_file'],
            (r) => {
                if (!r || !r.custom_proposed_system) {
                    return;
                }

                if (r.custom_job_file && !frm.doc.custom_job_file) {
                    frm.set_value('custom_job_file', r.custom_job_file);
                }

                const row = frm.add_child('items');
                frappe.model.set_value(row.doctype, row.name, 'item_code', r.custom_proposed_system)
                    .then(() => {
                        frappe.model.set_value(row.doctype, row.name, 'qty', 1);
                        frappe.model.set_value(row.doctype, row.name, 'rate', r.opportunity_amount || 0);
                        frm.script_manager.trigger('item_code', row.doctype, row.name);
                        frm.refresh_field('items');
                    });
            }
        );
    }
});

function fill_missing_item_details(frm) {
    const needs_fill = (frm.doc.items || []).filter(row => row.item_code && (!row.item_name || !row.uom));
    needs_fill.forEach(row => frm.script_manager.trigger('item_code', row.doctype, row.name));
}
