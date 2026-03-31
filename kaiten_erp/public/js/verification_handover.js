// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on('Verification Handover', {
    refresh: function (frm) {
        setup_custom_location_log_link_formatter_verification_handover(frm);
    },

    before_workflow_action: async function(frm) {
        await capture_workflow_gps_verification_handover(frm);
    }
});

function setup_custom_location_log_link_formatter_verification_handover(frm) {
    const table_field_name = (frm.fields_dict && frm.fields_dict.custom_location_log)
        ? 'custom_location_log'
        : ((frm.fields_dict && frm.fields_dict.custom_location_activity_log)
            ? 'custom_location_activity_log'
            : ((frm.fields_dict && frm.fields_dict.custom_location__history)
                ? 'custom_location__history'
                : 'location_log'));
    const table_field = frm.fields_dict && frm.fields_dict[table_field_name];
    if (!table_field || !table_field.grid) {
        return;
    }

    const location_field = table_field.grid.get_field('location');
    if (!location_field) {
        return;
    }

    location_field.formatter = function(value) {
        if (!value) {
            return '';
        }

        const raw = String(value).trim();
        let url = raw;

        if (!/^https?:\/\//i.test(url)) {
            const match = raw.match(/(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)/);
            if (match) {
                url = `https://www.google.com/maps?q=${match[1]},${match[2]}`;
            } else {
                return frappe.utils.escape_html(raw);
            }
        }

        const safe_url = frappe.utils.escape_html(url);
        return `<a href="${safe_url}" target="_blank" rel="noopener noreferrer">${__('Open Map')}</a>`;
    };

    frm.refresh_field(table_field_name);
}

async function capture_workflow_gps_verification_handover(frm) {
    if (!navigator.geolocation) {
        frappe.throw(__('GPS is not supported in this browser. Workflow transition is blocked.'));
    }

    frappe.dom.freeze(__('Capturing GPS location...'));

    try {
        const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0
            });
        });

        const latitude = Number(position.coords.latitude.toFixed(7));
        const longitude = Number(position.coords.longitude.toFixed(7));
        const location = `Lat: ${latitude}, Lng: ${longitude}`;
        const map_link = `https://www.google.com/maps?q=${latitude},${longitude}`;

        frm.doc.gps_latitude = latitude;
        frm.doc.gps_longitude = longitude;
        frm.doc.gps_location = location;
        frm.doc.gps_map_link = map_link;
        frm.doc.custom_gps_latitude = latitude;
        frm.doc.custom_gps_longitude = longitude;
        frm.doc.custom_gps_location = location;
        frm.doc.custom_gps_map_link = map_link;
        frm.doc._gps_latitude = latitude;
        frm.doc._gps_longitude = longitude;
        frm.doc._gps_location = location;
        frm.doc._gps_map_link = map_link;

        await set_gps_value_if_exists_verification_handover(frm, 'gps_latitude', latitude);
        await set_gps_value_if_exists_verification_handover(frm, 'custom_gps_latitude', latitude);
        await set_gps_value_if_exists_verification_handover(frm, 'gps_longitude', longitude);
        await set_gps_value_if_exists_verification_handover(frm, 'custom_gps_longitude', longitude);
        await set_gps_value_if_exists_verification_handover(frm, 'gps_location', location);
        await set_gps_value_if_exists_verification_handover(frm, 'custom_gps_location', location);
        await set_gps_value_if_exists_verification_handover(frm, 'gps_map_link', map_link);
        await set_gps_value_if_exists_verification_handover(frm, 'custom_gps_map_link', map_link);
    } catch (error) {
        frappe.throw(get_workflow_gps_error_message_verification_handover(error));
    } finally {
        frappe.dom.unfreeze();
    }
}

async function set_gps_value_if_exists_verification_handover(frm, fieldname, value) {
    if (frm.fields_dict && frm.fields_dict[fieldname]) {
        await frm.set_value(fieldname, value);
    }
}

function get_workflow_gps_error_message_verification_handover(error) {
    if (error && error.code === error.PERMISSION_DENIED) {
        return __('GPS permission denied. Allow location access to change workflow state.');
    }

    if (error && error.code === error.POSITION_UNAVAILABLE) {
        return __('GPS position unavailable. Try again in an open outdoor area.');
    }

    if (error && error.code === error.TIMEOUT) {
        return __('GPS request timed out. Please retry workflow transition.');
    }

    return __('Unable to capture GPS location. Workflow transition is blocked.');
}
