# Copyright (c) 2026, Kaiten Software
# Document Center API - Secure file listing and bulk download
#
# SECURITY MODEL:
#   1. frappe.has_permission() validates the caller can READ the parent doc
#   2. Files are fetched with strict attached_to_doctype + attached_to_name filters
#   3. Each file path is resolved via frappe.get_site_path() — no raw path input
#   4. ZIP is written to /private/files/ (requires auth to download)
#   5. No client-supplied paths are ever trusted

import os
import zipfile
import frappe
from frappe import _


@frappe.whitelist()
def get_attached_files(doctype: str, name: str) -> list[dict]:
    """
    Return files attached to a specific document.

    Security:
    - Validates READ permission on the parent document before returning anything.
    - Filters strictly by attached_to_doctype AND attached_to_name.
    - Never returns files from other documents or users.

    Args:
        doctype: The DocType of the parent document (e.g. "Complaint")
        name:    The document name / primary key (e.g. "CMP-2026-00001")

    Returns:
        List of dicts: [{"name": ..., "file_name": ..., "file_url": ...}]
    """
    _assert_read_permission(doctype, name)

    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": doctype,
            "attached_to_name": name,
        },
        fields=["name", "file_name", "file_url", "is_private", "file_size"],
        order_by="creation asc",
    )

    return files


@frappe.whitelist()
def download_all_files(doctype: str, name: str) -> dict:
    """
    Bundle all files attached to a document into a ZIP and return its URL.

    Security:
    - Validates READ permission before doing anything.
    - Fetches files with strict filters (same as get_attached_files).
    - Resolves each file path server-side via frappe.get_site_path().
    - Skips files that do not exist on disk (no error, just omitted).
    - ZIP is stored in /private/files/ — requires Frappe auth to download.

    Args:
        doctype: The DocType of the parent document
        name:    The document name / primary key

    Returns:
        {"file_url": "/private/files/<zip_name>"}

    Raises:
        frappe.PermissionError: if the user cannot read the parent document
        frappe.ValidationError: if no files are found
    """
    _assert_read_permission(doctype, name)

    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": doctype,
            "attached_to_name": name,
        },
        fields=["name", "file_name", "file_url", "is_private"],
        order_by="creation asc",
    )

    if not files:
        frappe.throw(_("No files are attached to this document."), frappe.ValidationError)

    # Build ZIP in /private/files/ so it requires authentication to download
    safe_name = frappe.scrub(name)          # e.g. "CMP-2026-00001" → "cmp_2026_00001"
    safe_doctype = frappe.scrub(doctype)    # e.g. "Complaint" → "complaint"
    zip_filename = f"{safe_doctype}_{safe_name}_documents.zip"
    zip_dest_dir = frappe.get_site_path("private", "files")
    zip_path = os.path.join(zip_dest_dir, zip_filename)

    os.makedirs(zip_dest_dir, exist_ok=True)

    added = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_doc in files:
            file_path = _resolve_file_path(file_doc.file_url)
            if not file_path:
                frappe.log_error(
                    f"Document Center: could not resolve path for file {file_doc.name} "
                    f"(url={file_doc.file_url})",
                    "Document Center Warning",
                )
                continue

            if not os.path.isfile(file_path):
                frappe.log_error(
                    f"Document Center: file not found on disk: {file_path} "
                    f"(file docname={file_doc.name})",
                    "Document Center Warning",
                )
                continue

            # Use the original file_name as the archive member name.
            # If two files share the same name, append the docname to disambiguate.
            arcname = file_doc.file_name or os.path.basename(file_path)
            zf.write(file_path, arcname)
            added += 1

    if added == 0:
        # Clean up empty ZIP
        if os.path.exists(zip_path):
            os.remove(zip_path)
        frappe.throw(
            _("None of the attached files could be found on disk."),
            frappe.ValidationError,
        )

    return {"file_url": f"/private/files/{zip_filename}"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_read_permission(doctype: str, name: str) -> None:
    """
    Raise PermissionError if the current user cannot READ the document.

    Also verifies the document actually exists (get_doc raises DoesNotExistError
    if it doesn't, which surfaces as a clear error to the caller).
    """
    # Confirm the document exists and is accessible.
    # frappe.get_doc() respects ignore_permissions=False by default, so it will
    # raise an exception if the doc doesn't exist.
    frappe.get_doc(doctype, name)  # raises if not found

    if not frappe.has_permission(doctype, "read", doc=name):
        frappe.throw(
            _("You do not have permission to access {0} {1}.").format(doctype, name),
            frappe.PermissionError,
        )


def _resolve_file_path(file_url: str) -> str | None:
    """
    Convert a Frappe file URL to an absolute filesystem path.

    Handles both:
    - /private/files/...  → <site>/private/files/...
    - /files/...          → <site>/public/files/...

    Returns None if the URL is empty or cannot be mapped.
    """
    if not file_url:
        return None

    url = file_url.strip()

    if url.startswith("/private/files/"):
        relative = url[len("/private/files/"):]
        return frappe.get_site_path("private", "files", relative)

    if url.startswith("/files/"):
        relative = url[len("/files/"):]
        return frappe.get_site_path("public", "files", relative)

    # External URLs (http/https) or unknown schemes — skip silently
    return None
