frappe.ui.form.on('Quotation', {
    refresh: function (frm) {
        frm.trigger('apply_stage_ui');
        frm.trigger('set_technical_survey_query');
        frm.trigger('fetch_opportunity_details');
    },

    opportunity: function (frm) {
        frm.trigger('set_technical_survey_query');
        frm.trigger('fetch_opportunity_details');
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
                row.item_code = r.custom_proposed_system;
                row.qty = 1;
                row.rate = r.opportunity_amount || 0;
                frm.refresh_field('items');
            }
        );
    }
});
