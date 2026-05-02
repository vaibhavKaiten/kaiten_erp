# Copyright (c) 2026, Kaiten Software
# DISCOM Process Tracker – Document Center API
#
# Collects ALL files for a DISCOM Process Tracker record:
#   1. Files stored in named Attach fields on the document itself
#      (feasibility_report, quotation, final_quotation, etc.)
#   2. Files fetched from the linked Job File (electricity_bill_photo, aadhar_card, etc.)
#   3. Any additional files attached via the standard Frappe attachment sidebar
#      (attached_to_doctype = "DISCOM Process Tracker", attached_to_name = <name>)
#
# SECURITY:
#   - frappe.has_permission() is checked before returning anything.
#   - Every file URL is resolved server-side; no client-supplied paths are trusted.
#   - ZIP is written to /private/files/ (requires an authenticated session to download).
#   - Files are scoped strictly to this document and its linked Job File.

import base64
import os
import zipfile
from io import BytesIO

import frappe
from frappe import _

# ---------------------------------------------------------------------------
# Field definitions
# ---------------------------------------------------------------------------

# Attach fields that live directly on DISCOM Process Tracker, with their labels.
# HEAD version fields (customer-document fields):
TRACKER_ATTACH_FIELDS = [
    ("feasibility_report",   "Feasibility Report"),
    ("quotation",            "Quotation"),
    ("final_quotation",      "Final Quotation"),
    ("inspection_report",    "Inspection Report"),
    ("commissioning_report", "Commissioning Report"),
]

# Attach fields fetched from Job File (read-only on the tracker).
# These are stored on Job File, not on the tracker itself.
JOB_FILE_ATTACH_FIELDS = [
    ("custom_electricity_bill_photo",       "Electricity Bill Photo"),
    ("custom_aadhar_card",                  "Aadhar Card"),
    ("custom_property_ownership_document",  "Property Ownership Document"),
    ("custom_bank_passbookcheque_",         "Bank Passbook / Cheque"),
    ("custom_pan_card",                     "Pan Card"),
    ("custom_property_photo",               "Property Photo with Geo Tagging"),
]

# Installation-tab Attach fields (HEAD branch version of the tracker)
INSTALLATION_ATTACH_FIELDS = [
    ("foundation_photo",              "Foundation Photo"),
    ("inverter",                      "Inverter"),
    ("front_view",                    "Front View"),
    ("wiring",                        "Wiring"),
    ("rear_view",                     "Rear View"),
    ("earthing",                      "Earthing"),
]

# Customer-document Attach fields (other HEAD branch version)
CUSTOMER_DOC_ATTACH_FIELDS = [
    ("electricity_bill_photo",        "Electricity Bill Photo"),
    ("aadhar_card",                   "Aadhar Card"),
    ("property_ownership_document",   "Property Ownership Document"),
    ("bank_passbook_cheque",          "Bank Passbook / Cheque"),
    ("pan_card",                      "Pan Card"),
    ("property_photo_with_geo_tagging", "Property Photo with Geo Tagging"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_discom_documents(name: str) -> list[dict]:
    """
    Return all documents (files) associated with a DISCOM Process Tracker record.

    Each entry in the returned list has:
        {
            "label":     "Human-readable field label or 'Attachment'",
            "source":    "tracker_field" | "job_file_field" | "attachment",
            "file_name": "original filename",
            "file_url":  "/private/files/... or /files/...",
            "file_size": <int bytes or 0>,
        }

    Security:
        - Validates READ permission on the DISCOM Process Tracker document.
        - Job File files are only included when the tracker has a linked job_file.
        - Sidebar attachments are filtered strictly by attached_to_name = name.
    """
    _assert_permission(name)

    tracker = frappe.get_doc("DISCOM Process Tracker", name)
    results = []

    # 1. Named Attach fields on the tracker itself
    for fieldname, label in TRACKER_ATTACH_FIELDS:
        url = tracker.get(fieldname)
        if url:
            results.append(_make_entry(label, "tracker_field", url))

    # 2. Installation-tab Attach fields (present in one branch of the JSON)
    for fieldname, label in INSTALLATION_ATTACH_FIELDS:
        url = tracker.get(fieldname)
        if url:
            results.append(_make_entry(label, "tracker_field", url))

    # 3. Customer-document Attach fields (present in the other branch)
    for fieldname, label in CUSTOMER_DOC_ATTACH_FIELDS:
        url = tracker.get(fieldname)
        if url:
            results.append(_make_entry(label, "tracker_field", url))

    # 4. Job File Attach fields (fetched / read-only on the tracker)
    if tracker.job_file:
        job_file = frappe.get_doc("Job File", tracker.job_file)
        for fieldname, label in JOB_FILE_ATTACH_FIELDS:
            url = job_file.get(fieldname)
            if url:
                results.append(_make_entry(label, "job_file_field", url))

    # 5. Sidebar / drag-drop attachments on the tracker itself
    sidebar_files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "DISCOM Process Tracker",
            "attached_to_name": name,
        },
        fields=["file_name", "file_url", "file_size"],
        order_by="creation asc",
    )
    for f in sidebar_files:
        # Avoid duplicates: skip if this URL was already captured from a named field
        already_listed = any(r["file_url"] == f.file_url for r in results)
        if not already_listed:
            results.append({
                "label":     "Attachment",
                "source":    "attachment",
                "file_name": f.file_name or _basename(f.file_url),
                "file_url":  f.file_url,
                "file_size": f.file_size or 0,
            })

    return results


@frappe.whitelist()
def download_all_discom_documents(name: str) -> dict:
    """
    Bundle all DISCOM Process Tracker documents into a ZIP and return it as
    a base64-encoded string so the browser can trigger a direct download
    without hitting a raw /private/files/ URL (which would 403).

    Returns:
        {"b64": "<base64 string>", "file_name": "<zip filename>"}
    """
    _assert_permission(name)

    files = get_discom_documents(name)   # already permission-checked

    if not files:
        frappe.throw(_("No documents are attached to this record."), frappe.ValidationError)

    tracker = frappe.get_doc("DISCOM Process Tracker", name)
    # ZIP filename: "{docname} batch file.zip"
    zip_filename = f"{name} batch file.zip"

    zip_buffer = BytesIO()
    added = 0
    used_arcnames: set[str] = set()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry in files:
            file_path = _resolve_file_path(entry["file_url"])
            if not file_path or not os.path.isfile(file_path):
                frappe.log_error(
                    f"DISCOM Document Center: file not found on disk: "
                    f"{entry.get('file_url')} (label={entry.get('label')})",
                    "DISCOM Document Center Warning",
                )
                continue

            # Internal archive name: "{Field Label} - {docname}.{ext}"
            # mirrors the single-download naming convention.
            original = entry.get("file_name") or _basename(entry["file_url"])
            _, ext = os.path.splitext(original)
            arcname = f"{entry['label']} - {name}{ext}"

            # Deduplicate arc names (same label used twice)
            if arcname in used_arcnames:
                arcname = f"{entry['label']} - {name}_{added}{ext}"
            used_arcnames.add(arcname)

            zf.write(file_path, arcname)
            added += 1

    if added == 0:
        frappe.throw(
            _("None of the documents could be found on disk."),
            frappe.ValidationError,
        )

    zip_buffer.seek(0)
    b64 = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")
    return {"b64": b64, "file_name": zip_filename}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assert_permission(name: str) -> None:
    """Raise PermissionError if the current user cannot READ this tracker."""
    frappe.get_doc("DISCOM Process Tracker", name)   # raises DoesNotExistError if missing
    if not frappe.has_permission("DISCOM Process Tracker", "read", doc=name):
        frappe.throw(
            _("You do not have permission to access DISCOM Process Tracker {0}.").format(name),
            frappe.PermissionError,
        )


def _make_entry(label: str, source: str, file_url: str) -> dict:
    """Build a result entry from a file URL stored in a named field."""
    file_name = _basename(file_url)
    file_size = 0

    # Try to get size from the File doctype record
    file_doc = frappe.db.get_value(
        "File",
        {"file_url": file_url},
        ["file_name", "file_size"],
        as_dict=True,
    )
    if file_doc:
        file_name = file_doc.file_name or file_name
        file_size = file_doc.file_size or 0

    return {
        "label":     label,
        "source":    source,
        "file_name": file_name,
        "file_url":  file_url,
        "file_size": file_size,
    }


def _resolve_file_path(file_url: str) -> str | None:
    """Convert a Frappe file URL to an absolute filesystem path."""
    if not file_url:
        return None
    url = file_url.strip()
    if url.startswith("/private/files/"):
        return frappe.get_site_path("private", "files", url[len("/private/files/"):])
    if url.startswith("/files/"):
        return frappe.get_site_path("public", "files", url[len("/files/"):])
    return None   # external URL — skip


def _basename(url: str) -> str:
    """Extract the filename from a URL or path."""
    return os.path.basename((url or "").strip("/")) or "file"
