# Implementation Plan

## Overview

This task list implements the location fields bug fix using the exploratory bugfix workflow. The fix addresses missing `field_order` entries and incorrect hidden attributes in four Frappe doctypes (Structure Mounting, Meter Installation, Meter Commissioning, and Project Installation).

**Workflow Phases:**
1. **Explore** - Write tests BEFORE fix to understand the bug (Bug Condition)
2. **Preserve** - Write tests for non-buggy behavior (Preservation Requirements)
3. **Implement** - Apply the fix with understanding (Expected Behavior)
4. **Validate** - Verify fix works and doesn't break anything

---

## Tasks

- [ ] 1. Write bug condition exploration property test
  - **Property 1: Bug Condition** - Location Log Fields Missing from Field Order
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bug exists
  - **Scoped PBT Approach**: For each affected doctype, scope the property to concrete workflow transitions with GPS coordinates
  - Test implementation details:
    - For Structure Mounting: Create document, set GPS coordinates (28.6139, 77.2090), trigger workflow transition "Draft" → "Pending Review", assert `custom_location_activity_log` table is populated
    - For Meter Installation: Create document, set GPS coordinates (19.0760, 72.8777), trigger workflow transition "Scheduled" → "In Progress", assert `custom_location_activity_log` table is populated
    - For Meter Commissioning: Create document, set GPS coordinates (12.9716, 77.5946), trigger workflow transition "Pending" → "Completed", assert `location_log` table is populated AND field is visible in UI
    - For Project Installation: Create document, set GPS coordinates (22.5726, 88.3639), trigger workflow transition "In Progress" → "Completed", assert `location_log` table is populated AND field is visible in UI
  - The test assertions should match the Expected Behavior Properties from design:
    - Assert location log table length > 0
    - Assert latitude matches input GPS latitude
    - Assert longitude matches input GPS longitude
    - Assert previous_status matches initial workflow state
    - Assert new_status matches final workflow state
    - Assert changed_by is populated with current user
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bug exists)
  - Document counterexamples found:
    - Which doctypes fail to populate location log tables
    - Whether field_order is missing the location log field name
    - Whether hidden attribute is incorrectly set
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Location Logging Behavior
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy inputs:
    - Technical Survey: Create document, set GPS coordinates, trigger workflow transition, observe that `location_log` table is populated correctly
    - Verification Handover: Create document, set GPS coordinates, trigger workflow transition, observe that `location_log` and `custom_location__history` tables are populated correctly
    - Observe that GPS temporary fields (gps_latitude, gps_longitude) are cleared after logging
    - Observe that workflow transitions without GPS coordinates succeed without errors
  - Write property-based tests capturing observed behavior patterns:
    - For Technical Survey: Generate random GPS coordinates and workflow states, assert location_log is populated correctly
    - For Verification Handover: Generate random GPS coordinates and workflow states, assert location_log and custom_location__history are populated correctly
    - For all working doctypes: Assert GPS temporary fields are cleared after logging
    - For all doctypes: Assert workflow transitions without GPS coordinates succeed silently
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 3. Fix location field configuration for all affected doctypes

  - [ ] 3.1 Fix Structure Mounting doctype JSON configuration
    - Open `kaiten_erp/kaiten_erp/doctype/structure_mounting/structure_mounting.json`
    - Add `"custom_location_activity_log"` to the end of the `field_order` array (after `"gps_map_link"`)
    - Verify field definition exists in `fields` array with correct properties:
      - `"fieldname": "custom_location_activity_log"`
      - `"fieldtype": "Table"`
      - `"options": "Location Log"`
      - `"read_only": 1`
      - `"allow_on_submit": 1`
    - If field definition is missing, add it to the `fields` array
    - _Bug_Condition: isBugCondition(input) where input.doctype = "Structure Mounting" AND locationLogFieldMissingFromFieldOrder(input.doctype)_
    - _Expected_Behavior: custom_location_activity_log table is populated with location data on workflow transitions_
    - _Preservation: Technical Survey and Verification Handover location logging unchanged_
    - _Requirements: 1.1, 2.1_

  - [ ] 3.2 Fix Meter Installation doctype JSON configuration
    - Open `kaiten_erp/kaiten_erp/doctype/meter_installation/meter_installation.json`
    - Add `"custom_location_activity_log"` to the end of the `field_order` array (after `"gps_map_link"`)
    - Add complete field definition to `fields` array:
      ```json
      {
        "fieldname": "custom_location_activity_log",
        "fieldtype": "Table",
        "label": "Location Activity Log",
        "options": "Location Log",
        "read_only": 1,
        "allow_on_submit": 1
      }
      ```
    - _Bug_Condition: isBugCondition(input) where input.doctype = "Meter Installation" AND locationLogFieldMissingFromFieldOrder(input.doctype)_
    - _Expected_Behavior: custom_location_activity_log table is populated with location data on workflow transitions_
    - _Preservation: Technical Survey and Verification Handover location logging unchanged_
    - _Requirements: 1.2, 2.2_

  - [ ] 3.3 Fix Meter Commissioning doctype JSON configuration
    - Open `kaiten_erp/kaiten_erp/doctype/meter_commissioning/meter_commissioning.json`
    - Add `"location_log"` to the end of the `field_order` array (after `"gps_map_link"`)
    - Verify field definition in `fields` array has `"hidden": 0` or no hidden attribute
    - If hidden attribute is set to 1, change it to 0
    - _Bug_Condition: isBugCondition(input) where input.doctype = "Meter Commissioning" AND (locationLogFieldMissingFromFieldOrder(input.doctype) OR locationLogFieldHidden(input.doctype))_
    - _Expected_Behavior: location_log table is populated with location data on workflow transitions AND field is visible in UI_
    - _Preservation: Technical Survey and Verification Handover location logging unchanged_
    - _Requirements: 1.3, 1.5, 2.3, 2.5_

  - [ ] 3.4 Fix Project Installation doctype JSON configuration
    - Open `kaiten_erp/kaiten_erp/doctype/project_installation/project_installation.json`
    - Add `"location_log"` to the end of the `field_order` array (after `"gps_map_link"`)
    - Verify field definition in `fields` array has `"hidden": 0` or no hidden attribute
    - If hidden attribute is set to 1, change it to 0
    - _Bug_Condition: isBugCondition(input) where input.doctype = "Project Installation" AND (locationLogFieldMissingFromFieldOrder(input.doctype) OR locationLogFieldHidden(input.doctype))_
    - _Expected_Behavior: location_log table is populated with location data on workflow transitions AND field is visible in UI_
    - _Preservation: Technical Survey and Verification Handover location logging unchanged_
    - _Requirements: 1.4, 1.6, 2.4, 2.6_

  - [ ] 3.5 Fix custom field visibility in fixtures
    - Open `kaiten_erp/fixtures/custom_field.json`
    - Find entry with `"name": "Project Installation-custom_location_activity_log"`
    - Change `"hidden": 1` to `"hidden": 0`
    - Verify Structure Mounting and Meter Installation custom_location_activity_log entries have `"hidden": 0`
    - _Bug_Condition: locationLogFieldHidden("Project Installation")_
    - _Expected_Behavior: custom_location_activity_log field is visible in Project Installation UI_
    - _Preservation: Existing custom field visibility unchanged for other doctypes_
    - _Requirements: 1.6, 2.6_

  - [ ] 3.6 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Location Log Fields Populated on Workflow Transitions
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior
    - When this test passes, it confirms the expected behavior is satisfied
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed)
    - Verify all four affected doctypes now populate location log tables correctly:
      - Structure Mounting: `custom_location_activity_log` table has entries
      - Meter Installation: `custom_location_activity_log` table has entries
      - Meter Commissioning: `location_log` table has entries AND field is visible
      - Project Installation: `location_log` table has entries AND field is visible
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 3.7 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Location Logging Behavior
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix:
      - Technical Survey location logging works correctly
      - Verification Handover location logging works correctly
      - GPS temporary fields are cleared after logging
      - Workflow transitions without GPS coordinates succeed silently
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Run all bug condition exploration tests - should PASS
  - Run all preservation property tests - should PASS
  - Run any existing unit tests for location logging functionality
  - Verify no regressions in other doctypes
  - If any tests fail, investigate and fix before proceeding
  - Ask the user if questions arise about test failures or unexpected behavior

---

## Notes

- **Test-Driven Approach**: Tests are written BEFORE the fix to understand the bug
- **Property-Based Testing**: Used for stronger guarantees across input domains
- **Observation-First**: Preservation tests observe unfixed behavior first
- **No Python Code Changes**: This is a configuration-only fix (JSON files)
- **Database Patch**: Optional - not included in this task list because historical data may not have GPS coordinates available
- **Frappe Bench Commands**: After JSON changes, run `bench migrate` to apply schema changes

## Testing Commands

```bash
# Run property-based tests
bench --site [site-name] run-tests kaiten_erp.tests.test_location_logging

# Run specific test
bench --site [site-name] run-tests kaiten_erp.tests.test_location_logging.TestLocationLogging.test_bug_condition_exploration

# Apply schema changes after JSON modifications
bench migrate
```
