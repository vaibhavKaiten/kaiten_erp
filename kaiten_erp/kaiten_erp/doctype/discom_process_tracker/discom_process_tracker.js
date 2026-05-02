// Copyright (c) 2026, Kaiten Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("DISCOM Process Tracker", {
	refresh: function (frm) {
		// Only show the legacy ZIP download button when Job File is linked
		const showBtn = !!frm.doc.job_file;
		const field = frm.fields_dict && frm.fields_dict.download_customer_site_snapshot_docs;
		if (field && field.$wrapper) {
			field.$wrapper.toggle(showBtn);
		}

		update_custom_bank_loan_visibility(frm);

		// ── Document Center ──────────────────────────────────────────────
		discom_document_center.render(frm);
	},

	onload_post_render: function (frm) {
		update_custom_bank_loan_visibility(frm);
	},

	job_file: function (frm) {
		update_custom_bank_loan_visibility(frm);
		// Refresh document list when Job File changes (fetched fields update)
		discom_document_center.render(frm);
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

// ============================================================================
// Document Center module (scoped to DISCOM Process Tracker)
// ============================================================================
const discom_document_center = (function () {
	"use strict";

	const HTML_FIELD = "documents_html";
	const DOWNLOAD_BTN_FLAG = "_discom_doc_center_btn";

	// ── Public ───────────────────────────────────────────────────────────────

	function render(frm) {
		if (frm.is_new()) {
			_set_html(frm, _empty_state(__("Save the document first to see attached files.")));
			return;
		}
		_load_and_render(frm);
		_add_toolbar_download_button(frm);
	}

	// ── Private ──────────────────────────────────────────────────────────────

	function _load_and_render(frm) {
		frappe.call({
			method: "kaiten_erp.kaiten_erp.api.discom_document_center.get_discom_documents",
			args: { name: frm.docname },
			callback: function (r) {
				if (r.exc) {
					_set_html(frm, _empty_state(__("Could not load documents.")));
					return;
				}
				const files = r.message || [];
				if (!files.length) {
					_set_html(frm, _empty_state(__("No documents are attached to this record.")));
				} else {
					_set_html(frm, _build_table(files, frm));
					_bind_row_download_buttons(frm);
					_bind_inline_download_button(frm);
				}
			},
		});
	}

	/**
	 * Build the HTML table.
	 * Single-download buttons use data-* attributes; click handlers are bound
	 * after injection so we can use fetch+blob for proper filename control.
	 */
	function _build_table(files, frm) {
		const customer = frappe.utils.escape_html(frm.doc.customer || "");
		const source_badge = {
			tracker_field: { text: __("Document Field"), cls: "indicator-pill blue" },
			job_file_field: { text: __("Job File"), cls: "indicator-pill green" },
			attachment: { text: __("Attachment"), cls: "indicator-pill gray" },
		};

		const rows = files.map(function (f) {
			const badge = source_badge[f.source] || source_badge.attachment;
			const size = f.file_size ? _fmt_size(f.file_size) : "—";
			const fname = frappe.utils.escape_html(f.file_name || f.label || "file");
			const label = frappe.utils.escape_html(f.label || "—");

			// View — open in new tab as-is
			const view_url = frappe.utils.escape_html(f.file_url || "");

			// Derive extension from the original filename
			const raw_name = f.file_name || "";
			const dot_idx = raw_name.lastIndexOf(".");
			const ext = dot_idx >= 0 ? raw_name.slice(dot_idx) : ""; // e.g. ".pdf"

			// Named download: "{Field Label} - {docname}.{ext}"
			const dl_filename = frappe.utils.escape_html(
				`${f.label || "file"} - ${frm.docname}${ext}`
			);

			return `
				<tr>
					<td style="padding:8px 12px; vertical-align:middle;">
						<strong>${label}</strong>
					</td>
					<td style="padding:8px 12px; vertical-align:middle;">
						<span class="fa fa-file-o" style="margin-right:5px; opacity:0.6;"></span>${fname}
					</td>
					<td style="padding:8px 12px; vertical-align:middle;">
						<span class="${badge.cls}" style="font-size:11px;">${badge.text}</span>
					</td>
					<td style="padding:8px 12px; vertical-align:middle; font-size:12px; opacity:0.7;">
						${size}
					</td>
					<td style="padding:8px 12px; vertical-align:middle; text-align:right; white-space:nowrap;">
						<a href="${view_url}" target="_blank" rel="noopener noreferrer"
						   class="btn btn-xs btn-default" style="margin-right:4px;">
							<span class="fa fa-eye"></span> ${__("View")}
						</a>
						<button class="btn btn-xs btn-primary discom-single-dl"
						        data-url="${frappe.utils.escape_html(f.file_url || "")}"
						        data-filename="${dl_filename}">
							<span class="fa fa-download"></span> ${__("Download")}
						</button>
					</td>
				</tr>`;
		}).join("");

		const customerLine = customer
			? `<p style="margin-bottom:10px; font-size:13px;">
				<strong>${__("Customer")}:</strong> ${customer}
			   </p>`
			: "";

		const countLine = `
			<p style="margin-top:8px; font-size:12px; opacity:0.6;">
				${files.length} ${files.length === 1 ? __("document") : __("documents")}
				${__("found for this record")}
			</p>`;

		const bottomBtn = `
			<div style="margin-top:14px; text-align:right;">
				<button id="discom-download-all-btn" class="btn btn-primary btn-sm">
					<span class="fa fa-download" style="margin-right:5px;"></span>
					${__("Download All Documents")}
				</button>
			</div>`;

		return `
			<div style="margin:12px 0;">
				${customerLine}
				<table class="table table-bordered table-hover" style="margin-bottom:0;">
					<thead>
						<tr>
							<th style="padding:8px 12px; font-weight:600; width:200px;">${__("Field / Label")}</th>
							<th style="padding:8px 12px; font-weight:600;">${__("File Name")}</th>
							<th style="padding:8px 12px; font-weight:600; width:140px;">${__("Source")}</th>
							<th style="padding:8px 12px; font-weight:600; width:90px;">${__("Size")}</th>
							<th style="padding:8px 12px; font-weight:600; width:180px; text-align:right;">${__("Action")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
				${countLine}
				${bottomBtn}
			</div>`;
	}

	/**
	 * Bind per-row Download buttons.
	 * Uses fetch + blob so we can set a.download to our custom filename,
	 * which the browser honours regardless of Content-Disposition from the server.
	 */
	function _bind_row_download_buttons(frm) {
		const fd = frm.fields_dict && frm.fields_dict[HTML_FIELD];
		if (!fd || !fd.$wrapper) return;

		fd.$wrapper.find(".discom-single-dl").off("click").on("click", function () {
			const $btn = $(this);
			const file_url = $btn.data("url");
			const filename = $btn.data("filename");

			if (!file_url) return;

			// Fetch through Frappe's authenticated download endpoint so private
			// files are served with a valid session cookie.
			const fetch_url =
				"/api/method/frappe.utils.file_manager.download_file?file_url=" +
				encodeURIComponent(file_url);

			$btn.prop("disabled", true).html(
				'<span class="fa fa-spinner fa-spin"></span>'
			);

			fetch(fetch_url, { credentials: "same-origin" })
				.then(function (res) {
					if (!res.ok) throw new Error("HTTP " + res.status);
					return res.blob();
				})
				.then(function (blob) {
					const url = URL.createObjectURL(blob);
					const a = document.createElement("a");
					a.href = url;
					a.download = filename;
					document.body.appendChild(a);
					a.click();
					a.remove();
					URL.revokeObjectURL(url);
				})
				.catch(function (err) {
					frappe.msgprint({
						title: __("Download failed"),
						message: err.message || __("Could not download the file."),
						indicator: "red",
					});
				})
				.finally(function () {
					$btn.prop("disabled", false).html(
						'<span class="fa fa-download"></span> ' + __("Download")
					);
				});
		});
	}

	/** Bind the bottom "Download All" button after HTML injection */
	function _bind_inline_download_button(frm) {
		const fd = frm.fields_dict && frm.fields_dict[HTML_FIELD];
		if (!fd || !fd.$wrapper) return;
		fd.$wrapper.find("#discom-download-all-btn").off("click").on("click", function () {
			_do_batch_download(frm);
		});
	}

	/** Toolbar button — added once per form session */
	function _add_toolbar_download_button(frm) {
		if (frm[DOWNLOAD_BTN_FLAG]) return;
		frm[DOWNLOAD_BTN_FLAG] = true;
		frm.add_custom_button(__("Download All Documents"), function () {
			_do_batch_download(frm);
		}, __("Documents"));
	}

	/**
	 * Batch download — calls backend which returns base64 ZIP.
	 * ZIP filename: "{docname} batch file.zip"
	 * ZIP internals: "{Field Label} - {docname}.{ext}" (set server-side)
	 */
	function _do_batch_download(frm) {
		frappe.call({
			method: "kaiten_erp.kaiten_erp.api.discom_document_center.download_all_discom_documents",
			args: { name: frm.docname },
			freeze: true,
			freeze_message: __("Preparing ZIP archive…"),
			callback: function (r) {
				if (r.exc || !r.message) return;
				if (!r.message.b64) {
					frappe.msgprint({
						title: __("Download failed"),
						message: __("No data returned from server."),
						indicator: "red",
					});
					return;
				}

				const b64 = r.message.b64;
				const filename = r.message.file_name || `${frm.docname} batch file.zip`;
				const bytes = atob(b64);
				const buf = new Uint8Array(bytes.length);
				for (let i = 0; i < bytes.length; i++) buf[i] = bytes.charCodeAt(i);

				const blob = new Blob([buf], { type: "application/zip" });
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
	}

	function _empty_state(message) {
		return `
			<div style="margin:12px 0; padding:24px; text-align:center;
			            background:var(--fg-hover-color, rgba(0,0,0,0.04));
			            border:1px dashed var(--border-color, #d1d8dd);
			            border-radius:4px; opacity:0.8;">
				<span class="fa fa-folder-open-o" style="font-size:24px; display:block; margin-bottom:8px;"></span>
				${frappe.utils.escape_html(message)}
			</div>`;
	}

	function _set_html(frm, html) {
		const fd = frm.fields_dict && frm.fields_dict[HTML_FIELD];
		if (fd && fd.$wrapper) fd.$wrapper.html(html);
	}

	function _fmt_size(bytes) {
		if (bytes < 1024) return bytes + " B";
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
		return (bytes / (1024 * 1024)).toFixed(1) + " MB";
	}

	return { render: render };
})();

// ============================================================================
// Bank Loan tab visibility (unchanged from original)
// ============================================================================

function update_custom_bank_loan_visibility(frm) {
	const jobFile = frm.doc.job_file;
	const tabFieldname = "custom_bank_loan";

	const apply = function (show) {
		const tabFields = get_fields_in_tab(frm, tabFieldname);
		if (!tabFields.length) return;

		tabFields.forEach((df) => {
			if (!df || !df.fieldname) return;
			if (df.fieldtype === "Tab Break") {
				frm.set_df_property(df.fieldname, "hidden", !show);
			} else {
				frm.toggle_display(df.fieldname, show);
			}
		});

		frm.refresh_fields();
	};

	if (!jobFile) {
		apply(false);
		return;
	}

	frappe.call({
		method: "frappe.client.get_value",
		args: {
			doctype: "Job File",
			filters: { name: jobFile },
			fieldname: ["custom_finance_type"],
		},
		callback: function (r) {
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
