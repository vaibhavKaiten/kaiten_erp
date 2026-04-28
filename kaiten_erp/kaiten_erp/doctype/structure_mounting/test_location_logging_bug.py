# Copyright (c) 2026, Kaiten Software
# Bug Condition Exploration Property Test
#
# Task 1: Write bug condition exploration property test
# Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
#
# PURPOSE: This test MUST FAIL on unfixed code.
# Failure confirms the bug exists. The test encodes the expected behavior
# and will PASS after the fix is applied.
#
# BUG SUMMARY (documented from analysis):
#
# Structure Mounting:
#   - `custom_location_activity_log` is defined in fixtures/custom_field.json
#     but is NOT present in the `field_order` array of structure_mounting.json.
#   - The `field_order` array ends with `"location_log"` (a different field).
#   - gps.py searches for `custom_location_activity_log` first in its candidates
#     list, but `doc.meta.has_field("custom_location_activity_log")` returns False
#     because the field is not in field_order (Frappe ORM does not register it).
#   - Result: log_workflow_location() silently skips logging.
#
# Meter Installation:
#   - `custom_location_activity_log` is defined in fixtures/custom_field.json
#     but is NOT present in the `field_order` array of meter_installation.json.
#   - The field_order ends at `"gps_map_link"` with no location log field.
#   - Same root cause as Structure Mounting.
#   - Result: log_workflow_location() silently skips logging.
#
# Meter Commissioning:
#   - `location_log` IS present in field_order and fields array.
#   - However, meter_commissioning.py does NOT call log_workflow_location()
#     in its validate() method (the method is missing entirely).
#   - Result: location log is never populated on workflow transitions.
#
# Project Installation:
#   - `location_log` IS present in field_order and fields array.
#   - `custom_location_activity_log` is defined in fixtures/custom_field.json
#     with `"hidden": 1` for Project Installation.
#   - gps.py finds `custom_location_activity_log` first in its candidates list.
#   - Even if the field is found, hidden=1 means it is not visible in the UI.
#   - Result: location log table may not be populated correctly, and even if it
#     were, the field would be hidden from users.

import frappe
from frappe.tests.utils import FrappeTestCase
from kaiten_erp.kaiten_erp.api.gps import log_workflow_location


class TestLocationLoggingBugCondition(FrappeTestCase):
    """
    Bug condition exploration tests for location logging.

    These tests MUST FAIL on unfixed code — that is the expected outcome.
    They encode the expected behavior and will PASS after the fix is applied.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**
    """

    def _make_structure_mounting(self):
        """Create a minimal Structure Mounting document saved to DB."""
        doc = frappe.get_doc({
            "doctype": "Structure Mounting",
            "workflow_state": "Draft",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc

    def _make_meter_installation(self):
        """Create a minimal Meter Installation document saved to DB."""
        doc = frappe.get_doc({
            "doctype": "Meter Installation",
            "workflow_state": "Draft",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc

    def _make_meter_commissioning(self):
        """Create a minimal Meter Commissioning document saved to DB."""
        doc = frappe.get_doc({
            "doctype": "Meter Commissioning",
            "workflow_state": "Draft",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc

    def _make_project_installation(self):
        """Create a minimal Project Installation document saved to DB."""
        doc = frappe.get_doc({
            "doctype": "Project Installation",
            "workflow_state": "Draft",
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc

    def _simulate_workflow_transition(self, doc, new_state, latitude, longitude):
        """
        Simulate a workflow state transition with GPS coordinates.

        Sets GPS coordinates and changes workflow_state in-memory (DB still has
        the old state), then calls log_workflow_location() directly — exactly
        as validate() would during a real workflow transition.
        """
        doc.gps_latitude = latitude
        doc.gps_longitude = longitude
        doc.workflow_state = new_state
        log_workflow_location(doc)

    def _get_location_log_field(self, doctype):
        """Return the expected location log field name for a given doctype."""
        # Structure Mounting and Meter Installation use custom_location_activity_log
        # Meter Commissioning and Project Installation use location_log
        if doctype in ("Structure Mounting", "Meter Installation"):
            return "custom_location_activity_log"
        return "location_log"

    def tearDown(self):
        """Clean up test documents after each test."""
        frappe.db.rollback()

    # -------------------------------------------------------------------------
    # Test 1: Structure Mounting — custom_location_activity_log must be populated
    # -------------------------------------------------------------------------

    def test_structure_mounting_location_log_populated_on_workflow_transition(self):
        """
        PROPERTY: When a workflow state transition occurs in Structure Mounting
        with GPS coordinates, custom_location_activity_log SHALL be populated.

        BUG CONDITION: custom_location_activity_log is missing from field_order
        in structure_mounting.json, so doc.meta.has_field() returns False and
        log_workflow_location() silently skips logging.

        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (AssertionError)
        EXPECTED OUTCOME AFTER FIX: PASS

        **Validates: Requirements 1.1, 2.1**
        """
        GPS_LAT = 28.6139
        GPS_LON = 77.2090
        INITIAL_STATE = "Draft"
        NEXT_STATE = "Assigned to Vendor"

        doc = self._make_structure_mounting()
        try:
            self._simulate_workflow_transition(doc, NEXT_STATE, GPS_LAT, GPS_LON)

            log_field = self._get_location_log_field("Structure Mounting")
            log_entries = doc.get(log_field)

            # Assert location log is populated
            self.assertGreater(
                len(log_entries), 0,
                f"[BUG] Structure Mounting: '{log_field}' table is empty after "
                f"workflow transition {INITIAL_STATE!r} → {NEXT_STATE!r} with GPS "
                f"({GPS_LAT}, {GPS_LON}). Root cause: '{log_field}' is missing from "
                f"field_order in structure_mounting.json."
            )

            entry = log_entries[0]

            # Assert latitude matches input
            self.assertAlmostEqual(
                float(entry.latitude), GPS_LAT, places=4,
                msg=f"[BUG] Structure Mounting: latitude mismatch. "
                    f"Expected {GPS_LAT}, got {entry.latitude}"
            )

            # Assert longitude matches input
            self.assertAlmostEqual(
                float(entry.longitude), GPS_LON, places=4,
                msg=f"[BUG] Structure Mounting: longitude mismatch. "
                    f"Expected {GPS_LON}, got {entry.longitude}"
            )

            # Assert previous_status matches initial workflow state
            self.assertEqual(
                entry.previous_status, INITIAL_STATE,
                f"[BUG] Structure Mounting: previous_status mismatch. "
                f"Expected {INITIAL_STATE!r}, got {entry.previous_status!r}"
            )

            # Assert new_status matches final workflow state
            self.assertEqual(
                entry.new_status, NEXT_STATE,
                f"[BUG] Structure Mounting: new_status mismatch. "
                f"Expected {NEXT_STATE!r}, got {entry.new_status!r}"
            )

            # Assert changed_by is populated
            self.assertTrue(
                entry.changed_by,
                "[BUG] Structure Mounting: changed_by is empty"
            )

        finally:
            doc.delete(ignore_permissions=True)
            frappe.db.commit()

    # -------------------------------------------------------------------------
    # Test 2: Meter Installation — custom_location_activity_log must be populated
    # -------------------------------------------------------------------------

    def test_meter_installation_location_log_populated_on_workflow_transition(self):
        """
        PROPERTY: When a workflow state transition occurs in Meter Installation
        with GPS coordinates, custom_location_activity_log SHALL be populated.

        BUG CONDITION: custom_location_activity_log is missing from field_order
        in meter_installation.json (field_order ends at gps_map_link), so
        doc.meta.has_field() returns False and log_workflow_location() silently
        skips logging.

        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (AssertionError)
        EXPECTED OUTCOME AFTER FIX: PASS

        **Validates: Requirements 1.2, 2.2**
        """
        GPS_LAT = 19.0760
        GPS_LON = 72.8777
        INITIAL_STATE = "Draft"
        NEXT_STATE = "Assigned to Vendor"

        doc = self._make_meter_installation()
        try:
            self._simulate_workflow_transition(doc, NEXT_STATE, GPS_LAT, GPS_LON)

            log_field = self._get_location_log_field("Meter Installation")
            log_entries = doc.get(log_field)

            # Assert location log is populated
            self.assertGreater(
                len(log_entries), 0,
                f"[BUG] Meter Installation: '{log_field}' table is empty after "
                f"workflow transition {INITIAL_STATE!r} → {NEXT_STATE!r} with GPS "
                f"({GPS_LAT}, {GPS_LON}). Root cause: '{log_field}' is missing from "
                f"field_order in meter_installation.json."
            )

            entry = log_entries[0]

            # Assert latitude matches input
            self.assertAlmostEqual(
                float(entry.latitude), GPS_LAT, places=4,
                msg=f"[BUG] Meter Installation: latitude mismatch. "
                    f"Expected {GPS_LAT}, got {entry.latitude}"
            )

            # Assert longitude matches input
            self.assertAlmostEqual(
                float(entry.longitude), GPS_LON, places=4,
                msg=f"[BUG] Meter Installation: longitude mismatch. "
                    f"Expected {GPS_LON}, got {entry.longitude}"
            )

            # Assert previous_status matches initial workflow state
            self.assertEqual(
                entry.previous_status, INITIAL_STATE,
                f"[BUG] Meter Installation: previous_status mismatch. "
                f"Expected {INITIAL_STATE!r}, got {entry.previous_status!r}"
            )

            # Assert new_status matches final workflow state
            self.assertEqual(
                entry.new_status, NEXT_STATE,
                f"[BUG] Meter Installation: new_status mismatch. "
                f"Expected {NEXT_STATE!r}, got {entry.new_status!r}"
            )

            # Assert changed_by is populated
            self.assertTrue(
                entry.changed_by,
                "[BUG] Meter Installation: changed_by is empty"
            )

        finally:
            doc.delete(ignore_permissions=True)
            frappe.db.commit()

    # -------------------------------------------------------------------------
    # Test 3: Meter Commissioning — location_log must be populated AND visible
    # -------------------------------------------------------------------------

    def test_meter_commissioning_location_log_populated_on_workflow_transition(self):
        """
        PROPERTY: When a workflow state transition occurs in Meter Commissioning
        with GPS coordinates, location_log SHALL be populated.

        BUG CONDITION: meter_commissioning.py does NOT call log_workflow_location()
        in its validate() method. The method is entirely absent from the class.

        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (AssertionError)
        EXPECTED OUTCOME AFTER FIX: PASS

        **Validates: Requirements 1.3, 2.3**
        """
        GPS_LAT = 12.9716
        GPS_LON = 77.5946
        INITIAL_STATE = "Draft"
        NEXT_STATE = "Assigned to Vendor"

        doc = self._make_meter_commissioning()
        try:
            self._simulate_workflow_transition(doc, NEXT_STATE, GPS_LAT, GPS_LON)

            log_field = self._get_location_log_field("Meter Commissioning")
            log_entries = doc.get(log_field)

            # Assert location log is populated
            self.assertGreater(
                len(log_entries), 0,
                f"[BUG] Meter Commissioning: '{log_field}' table is empty after "
                f"workflow transition {INITIAL_STATE!r} → {NEXT_STATE!r} with GPS "
                f"({GPS_LAT}, {GPS_LON}). Root cause: meter_commissioning.py does "
                f"not call log_workflow_location() in validate()."
            )

            entry = log_entries[0]

            # Assert latitude matches input
            self.assertAlmostEqual(
                float(entry.latitude), GPS_LAT, places=4,
                msg=f"[BUG] Meter Commissioning: latitude mismatch. "
                    f"Expected {GPS_LAT}, got {entry.latitude}"
            )

            # Assert longitude matches input
            self.assertAlmostEqual(
                float(entry.longitude), GPS_LON, places=4,
                msg=f"[BUG] Meter Commissioning: longitude mismatch. "
                    f"Expected {GPS_LON}, got {entry.longitude}"
            )

            # Assert previous_status matches initial workflow state
            self.assertEqual(
                entry.previous_status, INITIAL_STATE,
                f"[BUG] Meter Commissioning: previous_status mismatch. "
                f"Expected {INITIAL_STATE!r}, got {entry.previous_status!r}"
            )

            # Assert new_status matches final workflow state
            self.assertEqual(
                entry.new_status, NEXT_STATE,
                f"[BUG] Meter Commissioning: new_status mismatch. "
                f"Expected {NEXT_STATE!r}, got {entry.new_status!r}"
            )

            # Assert changed_by is populated
            self.assertTrue(
                entry.changed_by,
                "[BUG] Meter Commissioning: changed_by is empty"
            )

        finally:
            doc.delete(ignore_permissions=True)
            frappe.db.commit()

    def test_meter_commissioning_location_log_field_is_visible(self):
        """
        PROPERTY: The location_log field in Meter Commissioning SHALL be visible
        (hidden attribute must be 0 or absent).

        BUG CONDITION: The field definition in meter_commissioning.json does not
        have hidden=1, but the field may be hidden via property_setter or custom
        field configuration.

        EXPECTED OUTCOME ON UNFIXED CODE: PASS (field is not hidden in JSON)
        EXPECTED OUTCOME AFTER FIX: PASS

        **Validates: Requirements 1.5, 2.5**
        """
        meta = frappe.get_meta("Meter Commissioning")
        field = meta.get_field("location_log")

        self.assertIsNotNone(
            field,
            "[BUG] Meter Commissioning: 'location_log' field not found in meta. "
            "The field must be defined and accessible."
        )

        self.assertFalse(
            bool(field.hidden),
            f"[BUG] Meter Commissioning: 'location_log' field is hidden "
            f"(hidden={field.hidden}). The field must be visible to users."
        )

    # -------------------------------------------------------------------------
    # Test 4: Project Installation — location_log must be populated AND visible
    # -------------------------------------------------------------------------

    def test_project_installation_location_log_populated_on_workflow_transition(self):
        """
        PROPERTY: When a workflow state transition occurs in Project Installation
        with GPS coordinates, location_log SHALL be populated.

        BUG CONDITION: custom_location_activity_log is defined in fixtures with
        hidden=1 for Project Installation. gps.py finds custom_location_activity_log
        first in its candidates list. Even if it appends to that field, the data
        is in a hidden field rather than the expected location_log field.

        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (AssertionError)
        EXPECTED OUTCOME AFTER FIX: PASS

        **Validates: Requirements 1.4, 2.4**
        """
        GPS_LAT = 22.5726
        GPS_LON = 88.3639
        INITIAL_STATE = "Draft"
        NEXT_STATE = "Assigned to Vendor"

        doc = self._make_project_installation()
        try:
            self._simulate_workflow_transition(doc, NEXT_STATE, GPS_LAT, GPS_LON)

            log_field = self._get_location_log_field("Project Installation")
            log_entries = doc.get(log_field)

            # Assert location log is populated
            self.assertGreater(
                len(log_entries), 0,
                f"[BUG] Project Installation: '{log_field}' table is empty after "
                f"workflow transition {INITIAL_STATE!r} → {NEXT_STATE!r} with GPS "
                f"({GPS_LAT}, {GPS_LON}). Root cause: custom_location_activity_log "
                f"has hidden=1 in fixtures/custom_field.json for Project Installation, "
                f"and gps.py finds it first in its candidates list before location_log."
            )

            entry = log_entries[0]

            # Assert latitude matches input
            self.assertAlmostEqual(
                float(entry.latitude), GPS_LAT, places=4,
                msg=f"[BUG] Project Installation: latitude mismatch. "
                    f"Expected {GPS_LAT}, got {entry.latitude}"
            )

            # Assert longitude matches input
            self.assertAlmostEqual(
                float(entry.longitude), GPS_LON, places=4,
                msg=f"[BUG] Project Installation: longitude mismatch. "
                    f"Expected {GPS_LON}, got {entry.longitude}"
            )

            # Assert previous_status matches initial workflow state
            self.assertEqual(
                entry.previous_status, INITIAL_STATE,
                f"[BUG] Project Installation: previous_status mismatch. "
                f"Expected {INITIAL_STATE!r}, got {entry.previous_status!r}"
            )

            # Assert new_status matches final workflow state
            self.assertEqual(
                entry.new_status, NEXT_STATE,
                f"[BUG] Project Installation: new_status mismatch. "
                f"Expected {NEXT_STATE!r}, got {entry.new_status!r}"
            )

            # Assert changed_by is populated
            self.assertTrue(
                entry.changed_by,
                "[BUG] Project Installation: changed_by is empty"
            )

        finally:
            doc.delete(ignore_permissions=True)
            frappe.db.commit()

    def test_project_installation_location_log_field_is_visible(self):
        """
        PROPERTY: The location_log field in Project Installation SHALL be visible
        (hidden attribute must be 0 or absent).

        BUG CONDITION: custom_location_activity_log has hidden=1 in
        fixtures/custom_field.json for Project Installation. This means the
        location log data is stored in a hidden field, invisible to users.

        EXPECTED OUTCOME ON UNFIXED CODE: FAIL (AssertionError) if hidden=1
        EXPECTED OUTCOME AFTER FIX: PASS

        **Validates: Requirements 1.6, 2.6**
        """
        meta = frappe.get_meta("Project Installation")

        # Check the primary location log field (location_log) is visible
        location_log_field = meta.get_field("location_log")
        self.assertIsNotNone(
            location_log_field,
            "[BUG] Project Installation: 'location_log' field not found in meta."
        )
        self.assertFalse(
            bool(location_log_field.hidden),
            f"[BUG] Project Installation: 'location_log' field is hidden "
            f"(hidden={location_log_field.hidden}). The field must be visible."
        )

        # Also verify custom_location_activity_log is not hidden (if it exists)
        custom_log_field = meta.get_field("custom_location_activity_log")
        if custom_log_field:
            self.assertFalse(
                bool(custom_log_field.hidden),
                f"[BUG] Project Installation: 'custom_location_activity_log' field "
                f"is hidden (hidden={custom_log_field.hidden}). This field has "
                f"hidden=1 in fixtures/custom_field.json and must be fixed."
            )
