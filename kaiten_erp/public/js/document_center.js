/**
 * Document Center - Reusable module for displaying and downloading
 * files attached to any Frappe document.
 *
 * USAGE (in any form script):
 *
 *   frappe.ui.form.on('My DocType', {
 *       refresh: function(frm) {
 *           kaiten.document_center.setup(frm);
 *       }
 *   });
 *
 * REQUIREMENTS (add to the DocType via Customize Form or JSON):
 *   - A Tab Break field  : fieldname = "documents_tab",  label = "All Documents"
 *   - An HTML field      : fieldname = "documents_html"  (inside the tab)
 *
 * SECURITY:
 *   - All filtering is done server-side.
 *   - The client never passes file paths or constructs URLs.
 *   - The "Download All" button calls the server which validates permissions
 *     before building the ZIP.
 */

window.kaiten = window.kaiten || {};

kaiten.document_center = (function () {
    "use strict";

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * Set up the Document Center tab on a form.
     *
     * @param {frappe.ui.form.Form} frm  - The current form instance.
     */
    function setup(frm) {
        if (frm.is_new()) {
            // No files can be attached to an unsaved document.
            _render_empty(frm, __("Save the document first to see attached files."));
            return;
        }

        _load_files(frm);
        _add_download_button(frm);
    }

    // -----------------------------------------------------------------------
    // Private helpers
    // -----------------------------------------------------------------------

    /**
     * Fetch attached files from the server and render the table.
     */
    function _load_files(frm) {
        frappe.call({
            method: "kaiten_erp.kaiten_erp.api.document_center.get_attached_files",
            args: {
                doctype: frm.doctype,
                name: frm.docname,
            },
            callback: function (r) {
                if (r.exc) {
                    // Permission error or server error — show message, hide table.
                    _render_empty(frm, __("Could not load documents."));
                    return;
                }

                const files = r.message || [];
                if (files.length === 0) {
                    _render_empty(frm, __("No files are attached to this document."));
                } else {
                    _render_table(frm, files);
                }
            },
        });
    }

    /**
     * Render a table of files inside the documents_html field.
     *
     * @param {frappe.ui.form.Form} frm
     * @param {Array<{name, file_name, file_url, file_size}>} files
     */
    function _render_table(frm, files) {
        const rows = files
            .map(function (f) {
                const size_label = f.file_size ? _format_size(f.file_size) : "—";
                // file_url is a server-provided path — never constructed client-side.
                const download_url = f.file_url;
                return `
                    <tr>
                        <td style="padding:8px 12px; vertical-align:middle;">
                            <span class="fa fa-file-o" style="margin-right:6px; color:#6c757d;"></span>
                            ${frappe.utils.escape_html(f.file_name || f.name)}
                        </td>
                        <td style="padding:8px 12px; vertical-align:middle; color:#6c757d;">
                            ${size_label}
                        </td>
                        <td style="padding:8px 12px; vertical-align:middle; text-align:right;">
                            <a href="${frappe.utils.escape_html(download_url)}"
                               target="_blank"
                               rel="noopener noreferrer"
                               class="btn btn-xs btn-default">
                                <span class="fa fa-download"></span> ${__("Download")}
                            </a>
                        </td>
                    </tr>`;
            })
            .join("");

        const html = `
            <div style="margin: 12px 0;">
                <table class="table table-bordered table-hover" style="margin-bottom:0;">
                    <thead style="background:#f5f7fa;">
                        <tr>
                            <th style="padding:8px 12px; font-weight:600;">${__("File Name")}</th>
                            <th style="padding:8px 12px; font-weight:600; width:120px;">${__("Size")}</th>
                            <th style="padding:8px 12px; font-weight:600; width:130px; text-align:right;">${__("Action")}</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
                <p style="margin-top:8px; color:#6c757d; font-size:12px;">
                    ${files.length} ${files.length === 1 ? __("file") : __("files")} ${__("attached to this document")}
                </p>
            </div>`;

        frm.fields_dict["documents_html"] &&
            frm.fields_dict["documents_html"].$wrapper.html(html);
    }

    /**
     * Render a placeholder message when there are no files or an error occurred.
     */
    function _render_empty(frm, message) {
        const html = `
            <div style="margin:12px 0; padding:24px; text-align:center;
                        background:#f9f9f9; border:1px dashed #d1d8dd; border-radius:4px;
                        color:#6c757d;">
                <span class="fa fa-folder-open-o" style="font-size:24px; display:block; margin-bottom:8px;"></span>
                ${frappe.utils.escape_html(message)}
            </div>`;

        frm.fields_dict["documents_html"] &&
            frm.fields_dict["documents_html"].$wrapper.html(html);
    }

    /**
     * Add the "Download All Documents" button to the form toolbar.
     * The button is only added once (idempotent on refresh).
     */
    function _add_download_button(frm) {
        // Avoid duplicate buttons on repeated refresh calls.
        if (frm._document_center_btn_added) return;
        frm._document_center_btn_added = true;

        frm.add_custom_button(__("Download All Documents"), function () {
            _download_all(frm);
        }, __("Documents"));
    }

    /**
     * Call the server to build a ZIP and open it in a new tab.
     */
    function _download_all(frm) {
        frappe.call({
            method: "kaiten_erp.kaiten_erp.api.document_center.download_all_files",
            args: {
                doctype: frm.doctype,
                name: frm.docname,
            },
            freeze: true,
            freeze_message: __("Preparing ZIP archive…"),
            callback: function (r) {
                if (r.exc || !r.message) return; // server already showed error

                const file_url = r.message.file_url;
                if (file_url) {
                    window.open(file_url, "_blank", "noopener,noreferrer");
                }
            },
        });
    }

    /**
     * Format a byte count into a human-readable string.
     *
     * @param {number} bytes
     * @returns {string}
     */
    function _format_size(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    }

    // -----------------------------------------------------------------------
    // Expose public API
    // -----------------------------------------------------------------------
    return { setup: setup };
})();
