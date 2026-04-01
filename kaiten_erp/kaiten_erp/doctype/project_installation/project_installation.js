// Copyright (c) 2026, up411@gmail.com and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Installation", {
    onload(frm) {
        if (frm.doc.custom_job_file && (!frm.doc.panel_item || !frm.doc.custom_inverter_item)) {
            fetch_panel_inverter_from_ts(frm);
        }
    },

    custom_job_file(frm) {
        if (!frm.doc.custom_job_file) return;
        fetch_panel_inverter_from_ts(frm);
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
