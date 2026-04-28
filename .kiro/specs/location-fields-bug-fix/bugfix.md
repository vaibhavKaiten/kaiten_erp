# Bugfix Requirements Document

## Introduction

This bugfix addresses inconsistent location field population across Frappe doctypes in the Kaiten ERP system. The location logging mechanism, which tracks GPS coordinates during workflow state transitions, is not functioning correctly in four doctypes (Structure Mounting, Meter Installation, Meter Commissioning, and Project Installation), while it works correctly in reference doctypes (Technical Survey and Verification Handover).

The impact of this bug is that location history is not being captured for critical workflow transitions in these doctypes, preventing proper audit trails and location tracking for field operations.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a workflow state transition occurs in Structure Mounting doctype THEN the system does not populate the `custom_location_activity_log` table field with location data

1.2 WHEN a workflow state transition occurs in Meter Installation doctype THEN the system does not populate the `custom_location_activity_log` table field with location data

1.3 WHEN a workflow state transition occurs in Meter Commissioning doctype THEN the system does not populate the `location_log` table field with location data

1.4 WHEN a workflow state transition occurs in Project Installation doctype THEN the system does not populate the `location_log` table field with location data

1.5 WHEN viewing the Meter Commissioning doctype form THEN the `location_log` field in the location tab is hidden despite having no hidden attribute set in the JSON definition

1.6 WHEN viewing the Project Installation doctype form THEN the `location_log` field in the location tab is hidden despite having no hidden attribute set in the JSON definition

### Expected Behavior (Correct)

2.1 WHEN a workflow state transition occurs in Structure Mounting doctype THEN the system SHALL populate the `custom_location_activity_log` table field with timestamp, previous status, new status, latitude, longitude, location string, and changed_by user

2.2 WHEN a workflow state transition occurs in Meter Installation doctype THEN the system SHALL populate the `custom_location_activity_log` table field with timestamp, previous status, new status, latitude, longitude, location string, and changed_by user

2.3 WHEN a workflow state transition occurs in Meter Commissioning doctype THEN the system SHALL populate the `location_log` table field with timestamp, previous status, new status, latitude, longitude, location string, and changed_by user

2.4 WHEN a workflow state transition occurs in Project Installation doctype THEN the system SHALL populate the `location_log` table field with timestamp, previous status, new status, latitude, longitude, location string, and changed_by user

2.5 WHEN viewing the Meter Commissioning doctype form THEN the `location_log` field in the location tab SHALL be visible to users

2.6 WHEN viewing the Project Installation doctype form THEN the `location_log` field in the location tab SHALL be visible to users

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a workflow state transition occurs in Technical Survey doctype THEN the system SHALL CONTINUE TO populate the `location_log` table field correctly as it currently does

3.2 WHEN a workflow state transition occurs in Verification Handover doctype THEN the system SHALL CONTINUE TO populate the `location_log` and `custom_location__history` table fields correctly as they currently do

3.3 WHEN GPS coordinates are not available during a workflow state transition THEN the system SHALL CONTINUE TO allow the transition without blocking (fail silently)

3.4 WHEN a doctype does not have a workflow_state field THEN the system SHALL CONTINUE TO skip location logging without errors

3.5 WHEN a workflow state transition occurs but the state has not actually changed from the database value THEN the system SHALL CONTINUE TO skip logging to prevent duplicate entries

3.6 WHEN location data is logged successfully THEN the system SHALL CONTINUE TO clear the temporary GPS fields (gps_latitude, gps_longitude) to prevent stale values

3.7 WHEN the `log_workflow_location()` function is called from within the validate() method THEN the system SHALL CONTINUE TO never call doc.save() or doc.db_update() to avoid recursion issues
