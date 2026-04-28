import frappe
import re
from frappe import _
from frappe.utils import flt, now_datetime


GPS_TEMP_FIELD_CANDIDATES = {
    "latitude": ("gps_latitude", "custom_gps_latitude", "_gps_latitude"),
    "longitude": ("gps_longitude", "custom_gps_longitude", "_gps_longitude"),
    "location": ("gps_location", "custom_gps_location", "_gps_location"),
    "map_link": ("gps_map_link", "custom_gps_map_link", "_gps_map_link"),
}
LOCATION_LOG_TABLE_CANDIDATES = (
    "custom_location_log",
    "custom_location_activity_log",
    "custom_location__history",
    "location_log",
)
CHILD_FIELD_CANDIDATES = {
    "timestamp": ("timestamp", "custom_timestamp", "date_time"),
    "previous_status": ("previous_status", "custom_previous_status"),
    "new_status": ("new_status", "custom_new_status"),
    "location": ("location", "custom_location"),
    "latitude": ("latitude", "custom_latitude"),
    "longitude": ("longitude", "custom_longitude"),
    "map_link": ("map_link", "custom_map_link"),
    "changed_by": ("changed_by", "custom_changed_by"),
}


def log_workflow_location(doc):
    """
    Append a Location Log row on workflow state transitions.

    - Never throws: missing GPS or missing location_log table is silently skipped.
    - Only logs when workflow_state actually changed (DB value vs in-memory).
    - Clears gps_latitude / gps_longitude after logging to prevent stale values.
    - Must NOT call doc.save() or doc.db_update() — runs inside validate().
    """
    if not doc.meta.has_field("workflow_state"):
        return

    # Compare against DB-persisted value to detect actual transitions.
    # get_db_value returns None for new (unsaved) docs.
    db_state = frappe.db.get_value(doc.doctype, doc.name, "workflow_state")
    new_state = doc.workflow_state

    if db_state == new_state:
        return

    # Skip silently if GPS is absent — must never block a workflow transition.
    latitude = _to_float(doc.get("gps_latitude"))
    longitude = _to_float(doc.get("gps_longitude"))

    if not latitude and not longitude:
        # Clear stale fields anyway then bail
        doc.gps_latitude = None
        doc.gps_longitude = None
        return

    # Skip silently if no location log child table exists on this doctype.
    log_table_field = next(
        (
            f for f in LOCATION_LOG_TABLE_CANDIDATES
            if doc.meta.has_field(f) and doc.meta.get_field(f).fieldtype == "Table"
        ),
        None,
    )
    if not log_table_field:
        return

    previous_status = db_state or "New"
    location_str = f"{latitude}, {longitude}"

    doc.append(log_table_field, {
        "date_time": now_datetime(),
        "previous_status": previous_status,
        "new_status": new_state,
        "latitude": latitude,
        "longitude": longitude,
        "location": location_str,
        "changed_by": frappe.session.user,
    })

    # Clear temp GPS fields so they don't persist stale values across saves.
    doc.gps_latitude = None
    doc.gps_longitude = None


def _clear_temp_fields(doc):
    for fieldnames in GPS_TEMP_FIELD_CANDIDATES.values():
        for fieldname in fieldnames:
            if doc.meta.has_field(fieldname):
                doc.set(fieldname, None)
            elif fieldname in doc.__dict__:
                doc.__dict__.pop(fieldname, None)


def _first_existing_field(doc, fieldnames):
    for fieldname in fieldnames:
        if doc.meta.has_field(fieldname):
            return fieldname
    return None


def _get_first_value(doc, fieldnames):
    for fieldname in fieldnames:
        value = doc.get(fieldname)
        if value not in (None, ""):
            return value
    return None


def _set_child_value(child_doc, semantic_name, value):
    for fieldname in CHILD_FIELD_CANDIDATES.get(semantic_name, ()):
        if child_doc.meta.has_field(fieldname):
            child_doc.set(fieldname, value)
            return


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return flt(value)
    except Exception:
        return None


def _extract_coordinates(value):
    if not value:
        return None

    text = str(value)
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)", text)
    if not match:
        return None

    return flt(match.group(1)), flt(match.group(2))
