// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("DISCOM Process Tracker", {
	refresh: function (frm) {
		// Only show download button when Job File is linked
		const showBtn = !!frm.doc.job_file;
		const field = frm.fields_dict && frm.fields_dict.download_customer_site_snapshot_docs;
		if (field && field.$wrapper) {
			field.$wrapper.toggle(showBtn);
		}

		update_custom_bank_loan_visibility(frm);
	},

	onload_post_render: function (frm) {
		// Ensure tab hide/show is applied after the form layout is rendered.
		update_custom_bank_loan_visibility(frm);
	},

	job_file: function (frm) {
		update_custom_bank_loan_visibility(frm);
	},

	download_customer_site_snapshot_docs: function (frm) {
		if (!frm.doc.job_file) {
			frappe.msgprint({
				title: __("Missing Job File"),
				message: __("Please link a Job File first."),
				indicator: "red",
			});
			return;
		}

		frappe.call({
			method:
				"kaiten_erp.kaiten_erp.doctype.discom_process_tracker.discom_process_tracker.download_customer_site_snapshot_docs",
			args: { docname: frm.doc.name },
			freeze: true,
			callback: function (r) {
				if (!r.message || !r.message.b64) {
					frappe.msgprint({
						title: __("Download failed"),
						message: __("No data returned from server."),
						indicator: "red",
					});
					return;
				}

				// Convert base64 -> Blob and trigger download.
				const b64 = r.message.b64;
				const filename = r.message.file_name || "customer_site_snapshot_docs.zip";
				const byteChars = atob(b64);
				const byteNumbers = new Array(byteChars.length);
				for (let i = 0; i < byteChars.length; i++) {
					byteNumbers[i] = byteChars.charCodeAt(i);
				}
				const byteArray = new Uint8Array(byteNumbers);
				const blob = new Blob([byteArray], { type: "application/zip" });
				const url = URL.createObjectURL(blob);

				const a = document.createElement("a");
				a.href = url;
				a.download = filename;
				document.body.appendChild(a);
				a.click();
				a.remove();
				URL.revokeObjectURL(url);
			},
		});
	},
});

function update_custom_bank_loan_visibility(frm) {
	// "Bank Loan" visibility is driven by the linked Job File.
	const jobFile = frm.doc.job_file;
	const tabFieldname = "custom_bank_loan";

	const apply = function (show) {
		const tabFields = get_fields_in_tab(frm, tabFieldname);
		if (!tabFields.length) {
			// If the tab doesn't exist in this environment, do nothing.
			return;
		}

		tabFields.forEach((df) => {
			if (!df || !df.fieldname) return;
			if (df.fieldtype === "Tab Break") {
				frm.set_df_property(df.fieldname, "hidden", !show);
			} else {
				frm.toggle_display(df.fieldname, show);
			}
		});

		// Ensure the UI reflects the new hidden/display state.
		frm.refresh_fields();
	};

	// Default: hide when job file isn't set yet.
	if (!jobFile) {
		apply(false);
		return;
	}

	// Fetch the finance type from Job File.
	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Job File",
			filters: { name: jobFile },
			fieldname: ["custom_finance_type"],
		},
		callback: function (r) {
			// If the call fails / no permission / field missing, keep it hidden.
			if (!r || r.exc) {
				apply(false);
				return;
			}
			const financeType =
				r && r.message && r.message.custom_finance_type
					? r.message.custom_finance_type
					: null;
			apply(financeType === "Bank Loan");
		},
	});
}

function get_fields_in_tab(frm, tabFieldname) {
	if (!frm || !frm.meta || !Array.isArray(frm.meta.fields)) return [];

	const fields = frm.meta.fields;
	const startIdx = fields.findIndex((f) => f && f.fieldname === tabFieldname);
	if (startIdx < 0) return [];

	const out = [];
	for (let i = startIdx; i < fields.length; i++) {
		const df = fields[i];
		if (!df) continue;
		if (i !== startIdx && df.fieldtype === "Tab Break") break;
		out.push(df);
	}
	return out;
}
