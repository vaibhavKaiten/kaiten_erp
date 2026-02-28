/**
 * Client-side logic for Lead DocType - Vendor Assignment Fields
 * Handles vendor field filtering based on Territory
 */

frappe.ui.form.on('Job File', {
    refresh: function (frm) {
        setup_vendor_fields(frm);
    },

    // When Assignment Territory changes
    custom_assignment_territory: function (frm) {
        handle_territory_change(frm);
    },

    // When standard territory changes (fallback)
    territory: function (frm) {
        if (!frm.doc.custom_assignment_territory) {
            handle_territory_change(frm);
        }
    }
});

/**
 * Get the territory value from custom or standard field
 */
function get_territory_value(frm) {
    return frm.doc.custom_assignment_territory || frm.doc.territory;
}

/**
 * Handle territory change - clear vendor fields and re-setup
 */
function handle_territory_change(frm) {
    const territory = get_territory_value(frm);

    // Clear vendor fields when territory changes
    if (frm.doc.custom_assigned_technical_supplier || frm.doc.custom_assigned_meter_supplier) {
        frm.set_value('custom_assigned_technical_supplier', '');
        frm.set_value('custom_assigned_meter_supplier', '');
    }

    // Re-setup the fields
    setup_vendor_fields(frm);
}

/**
 * Setup vendor fields with proper filtering based on territory
 */
function setup_vendor_fields(frm) {
    const territory = get_territory_value(frm);

    if (!territory) {
        // Territory not selected - fields will be hidden by depends_on
        return;
    }

    if (frm.fields_dict.custom_assigned_technical_supplier) {
        frm.set_query('custom_assigned_technical_supplier', function () {
            return {
                query: 'kaiten_erp.kaiten_erp.api.lead_vendor.get_technical_vendors',
                filters: {
                    'territory': territory
                }
            };
        });

        frm.set_df_property('custom_assigned_technical_supplier', 'description',
            'Select Survey Vendor assigned to ' + territory);
    }


    if (frm.fields_dict.custom_assigned_meter_supplier) {
        frm.set_query('custom_assigned_meter_supplier', function () {
            return {
                query: 'kaiten_erp.kaiten_erp.api.lead_vendor.get_meter_vendors',
                filters: {
                    'territory': territory
                }
            };
        });

        frm.set_df_property('custom_assigned_meter_supplier', 'description',
            'Select Meter Vendor assigned to ' + territory);
    }
}
