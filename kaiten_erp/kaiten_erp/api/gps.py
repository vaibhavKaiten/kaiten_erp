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
    if not doc.meta.has_field("workflow_state"):
        return

    if not doc.has_value_changed("workflow_state"):
        return

    old_doc = doc.get_doc_before_save()
    previous_status = old_doc.workflow_state if old_doc and old_doc.workflow_state else "New"
    new_status = doc.workflow_state or "New"

    if previous_status == new_status:
        return

    log_table_field = _first_existing_field(doc, LOCATION_LOG_TABLE_CANDIDATES)
    if not log_table_field:
        frappe.throw(
            _("Missing location log table field in {0}. Expected one of: {1}").format(
                doc.doctype, ", ".join(LOCATION_LOG_TABLE_CANDIDATES)
            ),
            title=_("Configuration Error"),
        )

    latitude = _get_first_value(doc, GPS_TEMP_FIELD_CANDIDATES["latitude"])
    longitude = _get_first_value(doc, GPS_TEMP_FIELD_CANDIDATES["longitude"])
    location = _get_first_value(doc, GPS_TEMP_FIELD_CANDIDATES["location"])
    map_link = _get_first_value(doc, GPS_TEMP_FIELD_CANDIDATES["map_link"])

    latitude = _to_float(latitude)
    longitude = _to_float(longitude)

    # Recover coordinates from location/map URL when numeric fields are empty/zero.
    parsed_lat, parsed_lng = _extract_coordinates(location) or _extract_coordinates(map_link) or (None, None)
    if (latitude is None or longitude is None) and parsed_lat is not None and parsed_lng is not None:
        latitude, longitude = parsed_lat, parsed_lng
    elif latitude == 0 and longitude == 0 and parsed_lat is not None and parsed_lng is not None:
        latitude, longitude = parsed_lat, parsed_lng

    if latitude is None or longitude is None:
        frappe.throw(
            _("GPS location is mandatory before workflow transition."),
            title=_("Location Required"),
        )

    map_link = map_link or f"https://www.google.com/maps?q={latitude},{longitude}"
    location = map_link

    log_row = doc.append(log_table_field, {})
    _set_child_value(log_row, "timestamp", now_datetime())
    _set_child_value(log_row, "previous_status", previous_status)
    _set_child_value(log_row, "new_status", new_status)
    _set_child_value(log_row, "location", location)
    _set_child_value(log_row, "latitude", latitude)
    _set_child_value(log_row, "longitude", longitude)
    _set_child_value(log_row, "map_link", map_link)
    _set_child_value(log_row, "changed_by", frappe.session.user)

    _clear_temp_fields(doc)


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
