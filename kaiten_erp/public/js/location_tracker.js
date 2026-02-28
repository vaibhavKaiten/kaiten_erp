frappe.ui.form.on("Technical Survey", {
    refresh: function(frm) {
        frm._previous_workflow_state = frm.doc.workflow_state;

        // Render map links as clickable in the grid
        if (frm.doc.location_log && frm.doc.location_log.length > 0) {
            setTimeout(function() {
                frm.fields_dict.location_log.grid.wrapper.find(".grid-row").each(function(idx) {
                    var row = frm.doc.location_log[idx];
                    if (row && row.map_link) {
                        var map_cell = $(this).find('[data-fieldname="map_link"]');
                        if (map_cell.length) {
                            map_cell.html('<a href="' + row.map_link + '" target="_blank" style="color:#2490EF;">Open Map</a>');
                        }
                    }
                });
            }, 300);
        }
    },

    // Solar Panel Tilt Calculation
    front_height: function(frm) {
        calculate_tilt(frm);
    },
    back_height: function(frm) {
        calculate_tilt(frm);
    },
    distance: function(frm) {
        calculate_tilt(frm);
    },

    before_workflow_action: async function(frm) {
        frm._previous_workflow_state = frm.doc.workflow_state || "New";
        return new Promise((resolve, reject) => {
            if (navigator.geolocation) {
                frappe.show_alert({message: "Capturing location...", indicator: "blue"});
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        var lat = position.coords.latitude;
                        var lng = position.coords.longitude;
                        frm._captured_location = {
                            latitude: lat,
                            longitude: lng,
                            location: lat + ", " + lng,
                            map_link: "https://www.google.com/maps?q=" + lat + "," + lng
                        };
                        frappe.show_alert({message: "Location captured!", indicator: "green"});
                        resolve();
                    },
                    function(error) {
                        frm._captured_location = {
                            latitude: 0,
                            longitude: 0,
                            location: "Location unavailable",
                            map_link: ""
                        };
                        resolve();
                    },
                    {enableHighAccuracy: true, timeout: 10000, maximumAge: 0}
                );
            } else {
                frm._captured_location = {latitude: 0, longitude: 0, location: "Geolocation not supported", map_link: ""};
                resolve();
            }
        });
    },
    after_workflow_action: function(frm) {
        if (frm._captured_location && frm._previous_workflow_state !== frm.doc.workflow_state) {
            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype: "Test2 Location Log",
                        parent: frm.doc.name,
                        parenttype: "Test2",
                        parentfield: "location_log",
                        timestamp: frappe.datetime.now_datetime(),
                        previous_status: frm._previous_workflow_state || "New",
                        new_status: frm.doc.workflow_state,
                        location: frm._captured_location.location,
                        latitude: frm._captured_location.latitude,
                        longitude: frm._captured_location.longitude,
                        map_link: frm._captured_location.map_link,
                        changed_by: frappe.session.user
                    }
                },
                callback: function(r) {
                    frm.reload_doc();
                    frappe.show_alert({message: "Location logged!", indicator: "green"});
                }
            });
        }
    }
});

function calculate_tilt(frm) {
    var front_height = frm.doc.front_height || 0;
    var back_height = frm.doc.back_height || 0;
    var distance = frm.doc.distance || 0;

    // Calculate height difference (always higher - lower)
    var height_diff = Math.abs(back_height - front_height);
    frm.set_value("height_difference", height_diff);

    // Validate inputs
    if (front_height <= 0 || back_height <= 0 || distance <= 0) {
        frm.set_value("tilt_degree", 0);
        return;
    }

    if (front_height === back_height) {
        // Flat panel, no tilt
        frm.set_value("tilt_degree", 90);
        frappe.show_alert({
            message: "Panel is flat (0° tilt + 90° = 90°)",
            indicator: "blue"
        });
        return;
    }

    // Calculate tilt angle using arctan (right triangle)
    // tan(θ) = opposite / adjacent = height_diff / distance
    // θ = arctan(height_diff / distance)
    var tilt_radians = Math.atan(height_diff / distance);
    var tilt_degrees = tilt_radians * (180 / Math.PI);

    // Add 90 degrees (assumed 90° cut from shorter pole)
    var actual_angle = tilt_degrees + 90;

    // Round to 2 decimal places
    actual_angle = Math.round(actual_angle * 100) / 100;

    frm.set_value("tilt_degree", actual_angle);

    frappe.show_alert({
        message: "Tilt Angle: " + actual_angle + "° (includes +90° for riser pipe)",
        indicator: "green"
    });
}

