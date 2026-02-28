// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on('Technical Survey', {
    refresh: function (frm) {
        frm.set_df_property('tilt_deg', 'read_only', 1);
        calculate_tilt_degree(frm, { show_warning: false });
        setup_custom_location_log_link_formatter(frm);
        auto_load_bom_if_missing(frm);

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
        // Filter proposed_system_kw__tier to only show items from "Products" group with BOMs
        frm.set_query('proposed_system_kw__tier', function() {
            return {
                query: 'kaiten_erp.kaiten_erp.api.technical_survey_bom.get_items_with_bom',
                filters: {
                    item_group: 'Products'
                }
            };
        });
        
        // Store available BOM items for filtering
        frm.bom_panel_options = [];
        frm.bom_inverter_options = [];
        frm.bom_battery_options = [];
        
        // Filter panel field to only show panels from the selected BOM
        frm.set_query('panel', function() {
            if (frm.bom_panel_options.length > 0) {
                return {
                    filters: [
                        ['Item', 'name', 'in', frm.bom_panel_options]
                    ]
                };
            }
            return {};
        });
        
        // Filter inverter field to only show inverters from the selected BOM
        frm.set_query('inverter', function() {
            if (frm.bom_inverter_options.length > 0) {
                return {
                    filters: [
                        ['Item', 'name', 'in', frm.bom_inverter_options]
                    ]
                };
            }
            return {};
        });
        
        // Filter battery field to only show batteries from the selected BOM
        frm.set_query('battery', function() {
            if (frm.bom_battery_options.length > 0) {
                return {
                    filters: [
                        ['Item', 'name', 'in', frm.bom_battery_options]
                    ]
                };
            }
            return {};
        });
    },
    
    proposed_system_kw__tier: function(frm) {
        // Fetch BOM items when proposed system is selected
        fetch_bom_for_proposed_system(frm);
    },
    
    panel: function(frm) {
        // Set panel quantity when panel is selected
        set_component_quantity(frm, 'panel', 'panel_qty_bom', 'panel_candidates');
    },
    
    inverter: function(frm) {
        // Set inverter quantity when inverter is selected
        set_component_quantity(frm, 'inverter', 'inverter_qty_bom', 'inverter_candidates');
    },
    
    battery: function(frm) {
        // Set battery quantity when battery is selected
        set_component_quantity(frm, 'battery', 'battery_qty_bom', 'battery_candidates');
    },

    front_height_m: function(frm) {
        calculate_tilt_degree(frm);
    },

    back_height_m: function(frm) {
        calculate_tilt_degree(frm);
    },

    before_workflow_action: async function(frm) {
        await capture_workflow_gps_technical_survey(frm);
    }
});

function auto_load_bom_if_missing(frm) {
    const has_proposed_system = !!frm.doc.proposed_system_kw__tier;
    const has_components =
        !!frm.doc.panel || !!frm.doc.inverter || !!frm.doc.battery;
    const has_bom_rows =
        Array.isArray(frm.doc.table_vctx) && frm.doc.table_vctx.length > 0;
    const has_bom_reference = !!frm.doc.bom_reference;

    // Load BOM once when proposed system exists but dependent fields are blank.
    if (has_proposed_system && !has_components && !has_bom_rows && !has_bom_reference) {
        fetch_bom_for_proposed_system(frm);
    }
}

function calculate_tilt_degree(frm, options) {
    const opts = options || {};
    const show_warning = opts.show_warning !== false;
    const PANEL_LENGTH_FT = 7.2;

    const front_raw = frm.doc.front_height_m;
    const back_raw = frm.doc.back_height_m;

    if (!front_raw || !back_raw) {
        frm.set_value('tilt_deg', '');
        return;
    }

    const front_height = parseFloat(front_raw);
    const back_height = parseFloat(back_raw);

    if (Number.isNaN(front_height) || Number.isNaN(back_height)) {
        frm.set_value('tilt_deg', '');
        if (show_warning) {
            frappe.show_alert({
                message: __('Front Height and Back Height must be numeric values.'),
                indicator: 'orange'
            }, 5);
        }
        return;
    }

    if (back_height <= front_height) {
        frm.set_value('tilt_deg', '');
        if (show_warning) {
            frappe.show_alert({
                message: __('Back Height must be greater than Front Height.'),
                indicator: 'orange'
            }, 5);
        }
        return;
    }

    const height_difference = back_height - front_height;
    const tilt_radians = Math.atan(height_difference / PANEL_LENGTH_FT);
    const tilt_degree = tilt_radians * (180 / Math.PI);
    const rounded_tilt_degree = Math.round(tilt_degree * 100) / 100;

    frm.set_value('tilt_deg', rounded_tilt_degree.toFixed(2));
}

function setup_custom_location_log_link_formatter(frm) {
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

async function capture_workflow_gps_technical_survey(frm) {
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
        // Always keep transient values so workflow payload carries GPS even if no DB fields exist.
        frm.doc._gps_latitude = latitude;
        frm.doc._gps_longitude = longitude;
        frm.doc._gps_location = location;
        frm.doc._gps_map_link = map_link;

        await set_gps_value_if_exists(frm, 'gps_latitude', latitude);
        await set_gps_value_if_exists(frm, 'custom_gps_latitude', latitude);
        await set_gps_value_if_exists(frm, 'gps_longitude', longitude);
        await set_gps_value_if_exists(frm, 'custom_gps_longitude', longitude);
        await set_gps_value_if_exists(frm, 'gps_location', location);
        await set_gps_value_if_exists(frm, 'custom_gps_location', location);
        await set_gps_value_if_exists(frm, 'gps_map_link', map_link);
        await set_gps_value_if_exists(frm, 'custom_gps_map_link', map_link);
    } catch (error) {
        frappe.throw(get_workflow_gps_error_message_technical_survey(error));
    } finally {
        frappe.dom.unfreeze();
    }
}

async function set_gps_value_if_exists(frm, fieldname, value) {
    if (frm.fields_dict && frm.fields_dict[fieldname]) {
        await frm.set_value(fieldname, value);
    }
}

function get_workflow_gps_error_message_technical_survey(error) {
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

// Initialize namespace
frappe.provide('kaiten_erp.technical_survey');

// Client-side function to retry failed ToDo assignments
kaiten_erp.technical_survey.retry_todo_assignments = function () {
    // Get failed users from frappe.flags (set by server-side)
    const failed_users = frappe.flags.failed_todo_assignments;
    const survey_name = frappe.flags.survey_name;

    if (!failed_users || !survey_name) {
        frappe.msgprint(__('No failed assignments to retry'));
        return;
    }

    // Show confirmation dialog
    frappe.confirm(
        __('Do you want to retry creating ToDo assignments for the failed users?'),
        function () {
            // User clicked Yes - retry the assignments
            frappe.call({
                method: 'kaiten_erp.kaiten_erp.doc_events.technical_survey_events.retry_failed_todo_assignments',
                args: {
                    survey_name: survey_name,
                    failed_users: failed_users
                },
                freeze: true,
                freeze_message: __('Retrying ToDo assignments...'),
                callback: function (r) {
                    if (r.message) {
                        if (r.message.success) {
                            // All retries successful
                            frappe.show_alert({
                                message: r.message.message,
                                indicator: 'green'
                            }, 7);

                            // Clear the flags
                            delete frappe.flags.failed_todo_assignments;
                            delete frappe.flags.survey_name;

                            // Reload the form to show updated assignments
                            cur_frm.reload_doc();
                        } else {
                            // Some still failed
                            frappe.msgprint({
                                title: __('Retry Results'),
                                message: r.message.message,
                                indicator: 'orange'
                            });

                            // Update flags with still-failed users for another retry
                            if (r.message.still_failed && r.message.still_failed.length > 0) {
                                frappe.flags.failed_todo_assignments = r.message.still_failed.map(f => f.user);

                                // Ask if they want to retry again
                                setTimeout(function () {
                                    frappe.confirm(
                                        __('Some assignments still failed. Do you want to try again?'),
                                        function () {
                                            kaiten_erp.technical_survey.retry_todo_assignments();
                                        }
                                    );
                                }, 1000);
                            } else {
                                delete frappe.flags.failed_todo_assignments;
                                delete frappe.flags.survey_name;
                            }
                        }
                    }
                },
                error: function (r) {
                    frappe.msgprint({
                        title: __('Error'),
                        message: __('Failed to retry ToDo assignments. Please contact your system administrator.'),
                        indicator: 'red'
                    });
                }
            });
        },
        function () {
            // User clicked No - do nothing
            frappe.show_alert({
                message: __('Retry cancelled'),
                indicator: 'orange'
            }, 3);
        }
    );
};

// Function to fetch BOM items for the selected proposed system
function fetch_bom_for_proposed_system(frm) {
    const proposed_system = frm.doc.proposed_system_kw__tier;
    
    if (!proposed_system) {
        return;
    }
    
    // Clear existing items first
    frm.set_value('panel', '');
    frm.set_value('panel_qty_bom', '');
    frm.set_value('inverter', '');
    frm.set_value('inverter_qty_bom', '');
    frm.set_value('battery', '');
    frm.set_value('battery_qty_bom', '');
    frm.clear_table('table_vctx');
    
    // Fetch BOM items using the existing API
    frappe.call({
        method: 'kaiten_erp.kaiten_erp.api.technical_survey_bom.get_bom_payload',
        args: {
            proposed_system_item_code: proposed_system
        },
        freeze: true,
        freeze_message: __('Fetching BOM items...'),
        callback: function(r) {
            if (r.message && !r.message.error) {
                const data = r.message;
                
                // Store BOM data for later reference when selecting components
                frm.bom_data = {
                    panel_candidates: data.panel_candidates || [],
                    inverter_candidates: data.inverter_candidates || [],
                    battery_candidates: data.battery_candidates || [],
                    other_items: data.other_items || []
                };
                
                // Store available options for filtering
                frm.bom_panel_options = data.panel_candidates ? data.panel_candidates.map(p => p.item_code) : [];
                frm.bom_inverter_options = data.inverter_candidates ? data.inverter_candidates.map(i => i.item_code) : [];
                frm.bom_battery_options = data.battery_candidates ? data.battery_candidates.map(b => b.item_code) : [];
                
                console.log('Panel options:', frm.bom_panel_options);
                console.log('Inverter options:', frm.bom_inverter_options);
                console.log('Battery options:', frm.bom_battery_options);
                console.log('BOM data stored:', frm.bom_data);
                
                // Refresh the queries for the fields
                frm.fields_dict['panel'].get_query = null;
                frm.fields_dict['inverter'].get_query = null;
                frm.fields_dict['battery'].get_query = null;
                frm.set_query('panel', function() {
                    if (frm.bom_panel_options.length > 0) {
                        return {
                            filters: [
                                ['Item', 'name', 'in', frm.bom_panel_options]
                            ]
                        };
                    }
                    return {};
                });
                frm.set_query('inverter', function() {
                    if (frm.bom_inverter_options.length > 0) {
                        return {
                            filters: [
                                ['Item', 'name', 'in', frm.bom_inverter_options]
                            ]
                        };
                    }
                    return {};
                });
                frm.set_query('battery', function() {
                    if (frm.bom_battery_options.length > 0) {
                        return {
                            filters: [
                                ['Item', 'name', 'in', frm.bom_battery_options]
                            ]
                        };
                    }
                    return {};
                });
                
                // Set BOM reference
                if (data.bom) {
                    frm.set_value('bom_reference', data.bom);
                }
                
                // Set Panel - only auto-fill if there's exactly ONE panel option
                if (data.panel_candidates && data.panel_candidates.length === 1) {
                    frm.set_value('panel', data.panel_candidates[0].item_code);
                    frm.set_value('panel_qty_bom', data.panel_candidates[0].qty || 0);
                } else if (data.panel_candidates && data.panel_candidates.length > 1) {
                    // Multiple panels - leave blank for user selection
                    frm.set_value('panel_qty_bom', '');  // Keep quantity blank until user selects
                    frappe.show_alert({
                        message: __('Multiple panels available ({0}). Please select one.', [data.panel_candidates.length]),
                        indicator: 'blue'
                    }, 5);
                }
                
                // Set Inverter - only auto-fill if there's exactly ONE inverter option
                if (data.inverter_candidates && data.inverter_candidates.length === 1) {
                    frm.set_value('inverter', data.inverter_candidates[0].item_code);
                    frm.set_value('inverter_qty_bom', data.inverter_candidates[0].qty || 0);
                } else if (data.inverter_candidates && data.inverter_candidates.length > 1) {
                    // Multiple inverters - leave blank for user selection
                    frm.set_value('inverter_qty_bom', '');  // Keep quantity blank until user selects
                    frappe.show_alert({
                        message: __('Multiple inverters available ({0}). Please select one.', [data.inverter_candidates.length]),
                        indicator: 'blue'
                    }, 5);
                }
                
                // Set Battery - only auto-fill if there's exactly ONE battery option
                if (data.battery_candidates && data.battery_candidates.length === 1) {
                    frm.set_value('battery', data.battery_candidates[0].item_code);
                    frm.set_value('battery_qty_bom', data.battery_candidates[0].qty || 0);
                } else if (data.battery_candidates && data.battery_candidates.length > 1) {
                    // Multiple batteries - leave blank for user selection
                    frm.set_value('battery_qty_bom', '');  // Keep quantity blank until user selects
                    frappe.show_alert({
                        message: __('Multiple batteries available ({0}). Please select one.', [data.battery_candidates.length]),
                        indicator: 'blue'
                    }, 5);
                }
                
                // Add other items to BOM items table
                if (data.other_items && data.other_items.length > 0) {
                    data.other_items.forEach(function(item) {
                        let child = frm.add_child('table_vctx');
                        child.item_code = item.item_code;
                        child.qty = item.qty || 0;
                        child.uom = item.uom || 'Nos';
                        child.rate = item.rate || 0;
                        child.amount = item.amount || 0;
                        child.item_name = item.item_name || '';
                        child.description = item.description || item.item_name || '';
                    });
                }
                
                // Refresh all fields
                frm.refresh_field('bom_reference');
                frm.refresh_field('panel');
                frm.refresh_field('panel_qty_bom');
                frm.refresh_field('inverter');
                frm.refresh_field('inverter_qty_bom');
                frm.refresh_field('battery');
                frm.refresh_field('battery_qty_bom');
                frm.refresh_field('table_vctx');
                
                frappe.show_alert({
                    message: __('BOM items loaded successfully from {0}', [data.bom]),
                    indicator: 'green'
                }, 5);
            } else {
                const error_msg = r.message ? r.message.error : 'Unknown error';
                frappe.msgprint({
                    title: __('BOM Not Found'),
                    message: __('Could not load BOM: {0}', [error_msg]),
                    indicator: 'orange'
                });
            }
        },
        error: function(r) {
            frappe.msgprint({
                title: __('Error'),
                message: __('Failed to fetch BOM items. Please check if the BOM exists for this item.'),
                indicator: 'red'
            });
        }
    });
}

// Function to set component quantity when a panel/inverter/battery is selected
function set_component_quantity(frm, component_field, qty_field, candidates_key) {
    const selected_item = frm.doc[component_field];
    
    console.log('Setting quantity for:', component_field, 'Selected:', selected_item);
    console.log('BOM data:', frm.bom_data);
    console.log('Candidates key:', candidates_key);
    
    if (!selected_item) {
        console.log('No item selected');
        return;
    }
    
    if (!frm.bom_data || !frm.bom_data[candidates_key]) {
        console.log('BOM data not found for:', candidates_key);
        return;
    }
    
    // Find the selected item in the candidates
    const candidates = frm.bom_data[candidates_key];
    console.log('Candidates:', candidates);
    
    const selected_candidate = candidates.find(item => item.item_code === selected_item);
    console.log('Found candidate:', selected_candidate);
    
    if (selected_candidate) {
        console.log('Setting quantity to:', selected_candidate.qty);
        frm.set_value(qty_field, selected_candidate.qty);
    } else {
        console.log('Candidate not found in array');
    }
}
