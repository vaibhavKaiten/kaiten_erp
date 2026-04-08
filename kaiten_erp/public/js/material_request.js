// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Request", {
    custom_source_sales_order: function (frm) {
        _update_mr_title(frm);
    },
    custom_source_customer: function (frm) {
        _update_mr_title(frm);
    },
});

function _update_mr_title(frm) {
    const get_customer_name = (cb) => {
        const customer_id = frm.doc.custom_source_customer || frm.doc.customer;
        if (customer_id) {
            return frappe.db.get_value("Customer", customer_id, "customer_name", (r) =>
                cb(r && r.customer_name ? r.customer_name : customer_id)
            );
        }
        // Fallback: fetch customer from the linked Sales Order
        if (frm.doc.custom_source_sales_order) {
            return frappe.db.get_value(
                "Sales Order", frm.doc.custom_source_sales_order, "customer",
                (so_r) => {
                    if (!so_r || !so_r.customer) return cb("");
                    frappe.db.get_value("Customer", so_r.customer, "customer_name", (r) =>
                        cb(r && r.customer_name ? r.customer_name : so_r.customer)
                    );
                }
            );
        }
        return cb("");
    };

    const get_k_number = (cb) => {
        if (!frm.doc.custom_source_sales_order) return cb("");
        frappe.db.get_value(
            "Sales Order",
            frm.doc.custom_source_sales_order,
            "custom_job_file",
            (so_r) => {
                if (!so_r || !so_r.custom_job_file) return cb("");
                frappe.db.get_value(
                    "Job File",
                    so_r.custom_job_file,
                    "k_number",
                    (jf_r) => cb(jf_r && jf_r.k_number ? jf_r.k_number : "")
                );
            }
        );
    };

    get_customer_name((customer_name) => {
        get_k_number((k_number) => {
            const parts = [customer_name, k_number, "Material Request"].filter(Boolean);
            if (parts.length > 1) {
                frm.set_value("title", parts.join(" - "));
            }
        });
    });
}
