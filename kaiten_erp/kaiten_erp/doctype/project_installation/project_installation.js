// Copyright (c) 2026, up411@gmail.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Installation", {
    onload(frm) {
        if (frm.doc.custom_job_file && (!frm.doc.panel_item || !frm.doc.custom_inverter_item)) {
            fetch_panel_inverter_from_ts(frm);
        }
        if (frm.doc.custom_job_file && (!frm.doc.structure_type || !frm.doc.anchoring_type || !frm.doc.structure_height_m)) {
            fetch_structure_data_from_mounting(frm);
        }
    },

    custom_job_file(frm) {
        if (!frm.doc.custom_job_file) return;
        fetch_panel_inverter_from_ts(frm);
        fetch_structure_data_from_mounting(frm);
    }
});

function fetch_panel_inverter_from_ts(frm) {
    frappe.db.get_value(
        "Technical Survey",
        { custom_job_file: frm.doc.custom_job_file },
        ["panel", "inverter"]
    ).then(r => {
        if (!r.message) return;
        let d = r.message;
        if (d.panel) frm.set_value("panel_item", d.panel);
        if (d.inverter) frm.set_value("custom_inverter_item", d.inverter);
    });
}

function fetch_structure_data_from_mounting(frm) {
    frappe.db.get_value(
        "Structure Mounting",
        { custom_job_file: frm.doc.custom_job_file },
        ["structure_type", "anchoring_type", "strucutre_height"]
    ).then(r => {
        if (!r.message) return;
        let d = r.message;
        if (d.structure_type) frm.set_value("structure_type", d.structure_type);
        if (d.anchoring_type) frm.set_value("anchoring_type", d.anchoring_type);
        if (d.strucutre_height) frm.set_value("structure_height_m", d.strucutre_height);
    });
}
