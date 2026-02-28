// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on('Project Installation', {
    refresh: function (frm) {
        setup_custom_location_log_link_formatter_project_installation(frm);

        // Override the assignment functionality to filter users based on assigned_vendor
        if (frm.doc.assigned_vendor && !frm.is_new()) {
            // Remove the standard assignment button and add our custom one
            setTimeout(function() {
                // Find and override the assignment button click event
                const $assign_btn = frm.page.wrapper.find('.sidebar-menu').find('[data-label="Assignment"]');
                
                if ($assign_btn.length > 0) {
                    // Remove existing click handlers
                    $assign_btn.off('click');
                    
                    // Add our custom click handler
                    $assign_btn.on('click', function(e) {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        // Get vendor executives for the assigned vendor
                        frappe.call({
                            method: 'kaiten_erp.kaiten_erp.doc_events.technical_survey_events.get_vendor_executives_list',
                            args: {
                                supplier: frm.doc.assigned_vendor
                            },
                            callback: function(r) {
                                if (r.message && r.message.length > 0) {
                                    // Create custom assignment dialog with filtered users
                                    const d = new frappe.ui.Dialog({
                                        title: __('Add to To Do'),
                                        fields: [
                                            {
                                                fieldtype: 'MultiSelectPills',
                                                fieldname: 'assign_to',
                                                label: __('Assign To'),
                                                reqd: true,
                                                get_data: function(txt) {
                                                    // Filter the vendor executives based on search text
                                                    return r.message.filter(user => {
                                                        const search = txt.toLowerCase();
                                                        return user.email.toLowerCase().includes(search) ||
                                                               user.full_name.toLowerCase().includes(search);
                                                    }).map(user => ({
                                                        value: user.email,
                                                        description: user.full_name
                                                    }));
                                                }
                                            },
                                            {
                                                fieldtype: 'Small Text',
                                                fieldname: 'description',
                                                label: __('Comment')
                                            },
                                            {
                                                fieldtype: 'Section Break'
                                            },
                                            {
                                                fieldtype: 'Column Break'
                                            },
                                            {
                                                fieldtype: 'Date',
                                                fieldname: 'date',
                                                label: __('Complete By')
                                            },
                                            {
                                                fieldtype: 'Column Break'
                                            },
                                            {
                                                fieldtype: 'Select',
                                                fieldname: 'priority',
                                                label: __('Priority'),
                                                options: [
                                                    { label: __('Low'), value: 'Low' },
                                                    { label: __('Medium'), value: 'Medium' },
                                                    { label: __('High'), value: 'High' }
                                                ],
                                                default: 'Medium'
                                            },
                                            {
                                                fieldtype: 'Section Break'
                                            },
                                            {
                                                fieldtype: 'HTML',
                                                options: __('Assign this document to')
                                            }
                                        ],
                                        primary_action_label: __('Add'),
                                        primary_action: function() {
                                            const values = d.get_values();
                                            
                                            if (values.assign_to && values.assign_to.length > 0) {
                                                d.hide();
                                                frm.call({
                                                    method: 'frappe.desk.form.assign_to.add',
                                                    args: {
                                                        doctype: frm.doctype,
                                                        name: frm.docname,
                                                        assign_to: values.assign_to,
                                                        description: values.description || '',
                                                        date: values.date,
                                                        priority: values.priority || 'Medium'
                                                    },
                                                    btn: this,
                                                    callback: function(r) {
                                                        // After assignment, ensure users have write access
                                                        frappe.call({
                                                            method: 'kaiten_erp.kaiten_erp.doc_events.technical_survey_events.ensure_assigned_users_have_access',
                                                            args: {
                                                                docname: frm.docname
                                                            },
                                                            callback: function() {
                                                                frm.reload_doc();
                                                            }
                                                        });
                                                    }
                                                });
                                            }
                                        }
                                    });
                                    
                                    d.show();
                                } else {
                                    frappe.msgprint({
                                        title: __('No Users Found'),
                                        message: __('No Vendor Executives found for supplier: {0}', [frm.doc.assigned_vendor]),
                                        indicator: 'orange'
                                    });
                                }
                            }
                        });
                        
                        return false;
                    });
                }
            }, 500); // Small delay to ensure the sidebar is rendered
        }
    },
    
    setup: function(frm) {
        // Set query for assigned_internal_user to filter by vendor executives
        frm.set_query('assigned_internal_user', function() {
            if (frm.doc.assigned_vendor) {
                return {
                    query: 'kaiten_erp.kaiten_erp.doc_events.technical_survey_events.get_vendor_users_for_assignment',
                    filters: {
                        'docname': frm.doc.name,
                        'doctype_name': 'Project Installation'
                    }
                };
            }
            return {};
        });
    },

    before_workflow_action: async function(frm) {
        await capture_workflow_gps_project_installation(frm);
    }
});

async function capture_workflow_gps_project_installation(frm) {
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

        await set_gps_value_if_exists_project_installation(frm, 'gps_latitude', latitude);
        await set_gps_value_if_exists_project_installation(frm, 'custom_gps_latitude', latitude);
        await set_gps_value_if_exists_project_installation(frm, 'gps_longitude', longitude);
        await set_gps_value_if_exists_project_installation(frm, 'custom_gps_longitude', longitude);
        await set_gps_value_if_exists_project_installation(frm, 'gps_location', location);
        await set_gps_value_if_exists_project_installation(frm, 'custom_gps_location', location);
        await set_gps_value_if_exists_project_installation(frm, 'gps_map_link', map_link);
        await set_gps_value_if_exists_project_installation(frm, 'custom_gps_map_link', map_link);
    } catch (error) {
        frappe.throw(get_workflow_gps_error_message_project_installation(error));
    } finally {
        frappe.dom.unfreeze();
    }
}

function setup_custom_location_log_link_formatter_project_installation(frm) {
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

async function set_gps_value_if_exists_project_installation(frm, fieldname, value) {
    if (frm.fields_dict && frm.fields_dict[fieldname]) {
        await frm.set_value(fieldname, value);
    }
}

function get_workflow_gps_error_message_project_installation(error) {
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
