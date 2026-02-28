# GPS Tracking Implementation Guide - Kaiten Erp
## Complete Production-Ready Setup for ERPNext v16

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Complete Step-by-Step Implementation](#complete-step-by-step-implementation)
4. [Troubleshooting](#troubleshooting)
5. [Browser Requirements](#browser-requirements)
6. [Production Deployment](#production-deployment)

---

## Architecture Overview

```
Technical Survey DocType
├── Fields (Core)
│   └── Existing fields...
├── Custom Fields
│   ├── workflow_state (Link to Workflow State)
│   ├── location_history_section (Section Break)
│   └── location_log (Table → Location Log)
├── Workflow: Technical Survey Workflow
│   ├── States: Pending → In Progress → Completed
│   └── Actions: Start, Complete, Reset, Reopen
├── Client Script: Technical Survey Location Tracker
│   └── navigator.geolocation integration
└── Child Table: Location Log (Custom DocType)
    ├── timestamp (Datetime)
    ├── previous_status (Data)
    ├── new_status (Data)
    ├── location (Data - "lat, lng")
    ├── latitude (Float)
    ├── longitude (Float)
    ├── map_link (Data - Google Maps URL)
    └── changed_by (Link to User)
```

---

## Prerequisites

- ERPNext v16.x installed
- Frappe v16.x installed
- Bench environment working (`bench --site localhost` accessible)
- Administrator privileges
- HTTPS enabled (required for geolocation in production)

### Verify Installation

```bash
bench --site localhost console <<EOF
import frappe
print(f"Frappe Version: {frappe.__version__}")
print(f"Database: {frappe.conf.db_name}")
print(f"Site: localhost")
EOF
```

---

## Complete Step-by-Step Implementation

### STEP 1: Create Location Log Child Table

The Location Log is a custom child table DocType that stores GPS coordinates and workflow state changes.

**Execute in bench console:**

```bash
bench --site localhost console <<'EOF'
import frappe

# Create Location Log child table
child_doc = frappe.new_doc("DocType")
child_doc.name = "Location Log"
child_doc.module = "Kaiten Erp"
child_doc.custom = 1
child_doc.istable = 1
child_doc.editable_grid = 1
child_doc.quick_entry = 0

# Field 1: Timestamp
child_doc.append("fields", {
    "fieldname": "timestamp",
    "fieldtype": "Datetime",
    "label": "Date Time",
    "in_list_view": 1,
    "read_only": 1,
    "reqd": 1
})

# Field 2: Previous Status
child_doc.append("fields", {
    "fieldname": "previous_status",
    "fieldtype": "Data",
    "label": "Previous Status",
    "in_list_view": 1,
    "read_only": 1,
    "reqd": 1
})

# Field 3: New Status
child_doc.append("fields", {
    "fieldname": "new_status",
    "fieldtype": "Data",
    "label": "New Status",
    "in_list_view": 1,
    "read_only": 1,
    "reqd": 1
})

# Field 4: Location (lat, lng string)
child_doc.append("fields", {
    "fieldname": "location",
    "fieldtype": "Data",
    "label": "Location",
    "in_list_view": 1,
    "read_only": 1,
    "reqd": 1
})

# Field 5: Map Link
child_doc.append("fields", {
    "fieldname": "map_link",
    "fieldtype": "Data",
    "label": "Map Link",
    "in_list_view": 1,
    "read_only": 1
})

# Field 6: Latitude
child_doc.append("fields", {
    "fieldname": "latitude",
    "fieldtype": "Float",
    "label": "Latitude",
    "precision": 8,
    "read_only": 1,
    "reqd": 1
})

# Field 7: Longitude
child_doc.append("fields", {
    "fieldname": "longitude",
    "fieldtype": "Float",
    "label": "Longitude",
    "precision": 8,
    "read_only": 1,
    "reqd": 1
})

# Field 8: Changed By
child_doc.append("fields", {
    "fieldname": "changed_by",
    "fieldtype": "Link",
    "label": "Changed By",
    "options": "User",
    "in_list_view": 1,
    "read_only": 1,
    "reqd": 1
})

# Permissions
child_doc.append("permissions", {
    "role": "System Manager",
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 1,
    "submit": 0,
    "amend": 0,
    "cancel": 0
})

child_doc.insert()
frappe.db.commit()
print("✓ Location Log child table created successfully!")
EOF
```

**Expected Output:**
```
✓ Location Log child table created successfully!
```

---

### STEP 2: Add Custom Fields to Technical Survey

Add workflow_state, location history section, and location_log fields to Technical Survey.

**Execute in bench console:**

```bash
bench --site localhost console <<'EOF'
import frappe

target_doctype = "Technical Survey"

# Verify target DocType exists
if not frappe.db.exists("DocType", target_doctype):
    print(f"✗ Error: DocType '{target_doctype}' not found")
else:
    print(f"Adding custom fields to {target_doctype}...")
    
    # Field 1: workflow_state
    if not frappe.db.exists("Custom Field", {"dt": target_doctype, "fieldname": "workflow_state"}):
        wf_field = frappe.new_doc("Custom Field")
        wf_field.dt = target_doctype
        wf_field.fieldname = "workflow_state"
        wf_field.fieldtype = "Link"
        wf_field.label = "Workflow Status"
        wf_field.options = "Workflow State"
        wf_field.read_only = 1
        wf_field.insert_after = "status"
        wf_field.insert()
        print("  ✓ Created: workflow_state")
    else:
        print("  - workflow_state already exists")
    
    # Field 2: location_history_section
    if not frappe.db.exists("Custom Field", {"dt": target_doctype, "fieldname": "location_history_section"}):
        section_field = frappe.new_doc("Custom Field")
        section_field.dt = target_doctype
        section_field.fieldname = "location_history_section"
        section_field.fieldtype = "Section Break"
        section_field.label = "Location History"
        section_field.insert_after = "workflow_state"
        section_field.collapsible = 1
        section_field.insert()
        print("  ✓ Created: location_history_section")
    else:
        print("  - location_history_section already exists")
    
    # Field 3: location_log
    if not frappe.db.exists("Custom Field", {"dt": target_doctype, "fieldname": "location_log"}):
        table_field = frappe.new_doc("Custom Field")
        table_field.dt = target_doctype
        table_field.fieldname = "location_log"
        table_field.fieldtype = "Table"
        table_field.label = "Location Log"
        table_field.options = "Location Log"
        table_field.insert_after = "location_history_section"
        table_field.read_only = 1
        table_field.insert()
        print("  ✓ Created: location_log")
    else:
        print("  - location_log already exists")
    
    frappe.db.commit()
    print("✓ Custom fields added successfully!")
EOF
```

**Expected Output:**
```
Adding custom fields to Technical Survey...
  ✓ Created: workflow_state
  ✓ Created: location_history_section
  ✓ Created: location_log
✓ Custom fields added successfully!
```

---

### STEP 3: Create Workflow States and Actions

Create the required workflow states and actions.

**Execute in bench console:**

```bash
bench --site localhost console <<'EOF'
import frappe

# Create Workflow States
print("Creating workflow states...")
workflow_states = ["Pending", "In Progress", "Completed"]

for state_name in workflow_states:
    if not frappe.db.exists("Workflow State", state_name):
        ws = frappe.new_doc("Workflow State")
        ws.workflow_state_name = state_name
        ws.insert()
        print(f"  ✓ Created: {state_name}")
    else:
        print(f"  - {state_name} already exists")

# Create Workflow Actions
print("\nCreating workflow actions...")
workflow_actions = ["Start", "Complete", "Reset", "Reopen"]

for action_name in workflow_actions:
    if not frappe.db.exists("Workflow Action Master", action_name):
        wa = frappe.new_doc("Workflow Action Master")
        wa.workflow_action_name = action_name
        wa.insert()
        print(f"  ✓ Created: {action_name}")
    else:
        print(f"  - {action_name} already exists")

frappe.db.commit()
print("\n✓ Workflow states and actions created successfully!")
EOF
```

**Expected Output:**
```
Creating workflow states...
  ✓ Created: Pending
  ✓ Created: In Progress
  ✓ Created: Completed

Creating workflow actions...
  ✓ Created: Start
  ✓ Created: Complete
  ✓ Created: Reset
  ✓ Created: Reopen

✓ Workflow states and actions created successfully!
```

---

### STEP 4: Create Technical Survey Workflow

Create the workflow with transitions and state configurations.

**Execute in bench console:**

```bash
bench --site localhost console <<'EOF'
import frappe

workflow_name = "Technical Survey Workflow"
doctype = "Technical Survey"
allowed_role = "Administrator"

# Delete existing workflow if present
if frappe.db.exists("Workflow", workflow_name):
    frappe.delete_doc("Workflow", workflow_name)
    frappe.db.commit()
    print(f"Deleted existing workflow: {workflow_name}")

print(f"Creating workflow: {workflow_name}")

wf = frappe.new_doc("Workflow")
wf.workflow_name = workflow_name
wf.document_type = doctype
wf.is_active = 1
wf.send_email_alert = 0
wf.create_new = 0
wf.cascade_on_submit = 0

# Add States
print("  Adding workflow states...")
for state in ["Pending", "In Progress", "Completed"]:
    wf.append("states", {
        "state": state,
        "doc_status": 0,
        "allow_edit": allowed_role
    })
    print(f"    ✓ {state}")

# Add Transitions
print("  Adding workflow transitions...")
transitions = [
    {"state": "Pending", "action": "Start", "next_state": "In Progress"},
    {"state": "In Progress", "action": "Complete", "next_state": "Completed"},
    {"state": "In Progress", "action": "Reset", "next_state": "Pending"},
    {"state": "Completed", "action": "Reopen", "next_state": "In Progress"}
]

for trans in transitions:
    wf.append("transitions", {
        "state": trans["state"],
        "action": trans["action"],
        "next_state": trans["next_state"],
        "allowed": allowed_role,
        "allow_self_approval": 1
    })
    print(f"    ✓ {trans['state']} --({trans['action']})→ {trans['next_state']}")

wf.insert()
frappe.db.commit()

print(f"\n✓ Workflow created successfully!")
print(f"  - Name: {workflow_name}")
print(f"  - Document Type: {doctype}")
print(f"  - Status: Active")
EOF
```

**Expected Output:**
```
Creating workflow: Technical Survey Workflow
  Adding workflow states...
    ✓ Pending
    ✓ In Progress
    ✓ Completed
  Adding workflow transitions...
    ✓ Pending --(Start)→ In Progress
    ✓ In Progress --(Complete)→ Completed
    ✓ In Progress --(Reset)→ Pending
    ✓ Completed --(Reopen)→ In Progress

✓ Workflow created successfully!
  - Name: Technical Survey Workflow
  - Document Type: Technical Survey
  - Status: Active
```

---

### STEP 5: Create Client Script with GPS Tracking

Create the client-side JavaScript script that captures GPS and logs location data.

**Execute in bench console:**

```bash
bench --site localhost console <<'EOF'
import frappe

doctype = "Technical Survey"
script_name = f"{doctype} Location Tracker"

# Delete existing script if present
if frappe.db.exists("Client Script", script_name):
    frappe.delete_doc("Client Script", script_name)
    frappe.db.commit()
    print(f"Deleted existing client script: {script_name}\n")

print(f"Creating client script: {script_name}")

javascript_code = '''frappe.ui.form.on("Technical Survey", {
    refresh: function(frm) {
        frm._previous_workflow_state = frm.doc.workflow_state;
        if (frm.doc.location_log && frm.doc.location_log.length > 0) {
            setTimeout(function() {
                frm.fields_dict.location_log.grid.wrapper.find(".grid-row").each(function(idx) {
                    var row = frm.doc.location_log[idx];
                    if (row && row.map_link) {
                        var map_cell = $(this).find('[data-fieldname="map_link"]');
                        if (map_cell.length) {
                            map_cell.html('<a href="' + row.map_link + '" target="_blank" style="color:#2490EF;text-decoration:underline;cursor:pointer;">Open Map</a>');
                        }
                    }
                });
            }, 300);
        }
    },
    before_workflow_action: async function(frm) {
        frm._previous_workflow_state = frm.doc.workflow_state || "New";
        return new Promise((resolve, reject) => {
            if (navigator.geolocation) {
                frappe.show_alert({message: "Capturing device location...", indicator: "blue"});
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        var lat = position.coords.latitude;
                        var lng = position.coords.longitude;
                        var accuracy = position.coords.accuracy;
                        frm._captured_location = {
                            latitude: lat,
                            longitude: lng,
                            location: lat + ", " + lng,
                            map_link: "https://www.google.com/maps?q=" + lat + "," + lng,
                            accuracy: accuracy
                        };
                        frappe.show_alert({message: "Location captured! (Accuracy: " + Math.round(accuracy) + "m)", indicator: "green"});
                        resolve();
                    },
                    function(error) {
                        console.warn("Geolocation error:", error);
                        frm._captured_location = {
                            latitude: 0,
                            longitude: 0,
                            location: "Location unavailable",
                            map_link: ""
                        };
                        frappe.show_alert({message: "Warning: Could not capture location. Check browser permissions.", indicator: "orange"});
                        resolve();
                    },
                    {enableHighAccuracy: true, timeout: 10000, maximumAge: 0}
                );
            } else {
                console.warn("Geolocation not supported");
                frm._captured_location = {latitude: 0, longitude: 0, location: "Geolocation not supported", map_link: ""};
                frappe.show_alert({message: "Warning: Geolocation not supported in this browser.", indicator: "orange"});
                resolve();
            }
        });
    },
    after_workflow_action: function(frm) {
        if (frm._captured_location && frm._previous_workflow_state !== frm.doc.workflow_state) {
            var child_row = {
                doctype: "Location Log",
                parent: frm.doc.name,
                parenttype: "Technical Survey",
                parentfield: "location_log",
                timestamp: frappe.datetime.now_datetime(),
                previous_status: frm._previous_workflow_state || "New",
                new_status: frm.doc.workflow_state,
                location: frm._captured_location.location,
                latitude: frm._captured_location.latitude,
                longitude: frm._captured_location.longitude,
                map_link: frm._captured_location.map_link,
                changed_by: frappe.session.user
            };
            frappe.call({
                method: "frappe.client.insert",
                args: {doc: child_row},
                callback: function(r) {
                    if (r.message) {
                        frm.reload_doc();
                        frappe.show_alert({message: "Location logged successfully!", indicator: "green"});
                        console.log("Location log entry created:", r.message);
                    }
                },
                error: function(r) {
                    frappe.show_alert({message: "Error logging location. Try again.", indicator: "red"});
                    console.error("Failed to insert location log:", r);
                }
            });
        }
    }
});
'''

cs = frappe.new_doc("Client Script")
cs.name = script_name
cs.dt = doctype
cs.view = "Form"
cs.enabled = 1
cs.script = javascript_code
cs.insert()

frappe.db.commit()

print(f"✓ Client script created successfully!")
print(f"  - DocType: {doctype}")
print(f"  - Name: {script_name}")
print(f"  - View: Form")
print(f"  - Enabled: Yes")
print(f"\nEvent Hooks Configured:")
print(f"  ✓ refresh: Renders map links as clickable")
print(f"  ✓ before_workflow_action: Captures GPS before transition")
print(f"  ✓ after_workflow_action: Logs location after transition")
EOF
```

**Expected Output:**
```
Creating client script: Technical Survey Location Tracker
✓ Client script created successfully!
  - DocType: Technical Survey
  - Name: Technical Survey Location Tracker
  - View: Form
  - Enabled: Yes

Event Hooks Configured:
  ✓ refresh: Renders map links as clickable
  ✓ before_workflow_action: Captures GPS before transition
  ✓ after_workflow_action: Logs location after transition
```

---

### STEP 6: Clear Cache

Clear the Frappe cache to ensure all changes are reflected.

**Execute in terminal:**

```bash
bench --site localhost clear-cache
```

**Expected Output:**
```
Cache cleared.
Cache purged.
```

---

### STEP 7: Verify Installation

Verify that all components were created successfully.

**Execute in bench console:**

```bash
bench --site localhost console <<'EOF'
import frappe

print("=" * 80)
print("GPS TRACKING IMPLEMENTATION VERIFICATION")
print("=" * 80)

# Check 1: Location Log DocType
location_log_exists = frappe.db.exists("DocType", "Location Log")
print(f"\n✓ Location Log child table: {'EXISTS' if location_log_exists else 'MISSING'}")

# Check 2: Custom Fields
custom_fields_check = {
    "workflow_state": frappe.db.exists("Custom Field", {"dt": "Technical Survey", "fieldname": "workflow_state"}),
    "location_history_section": frappe.db.exists("Custom Field", {"dt": "Technical Survey", "fieldname": "location_history_section"}),
    "location_log": frappe.db.exists("Custom Field", {"dt": "Technical Survey", "fieldname": "location_log"})
}
print(f"\n✓ Custom Fields:")
for field_name, exists in custom_fields_check.items():
    status = "EXISTS" if exists else "MISSING"
    print(f"  - {field_name}: {status}")

# Check 3: Workflow States
workflow_states_check = {
    "Pending": frappe.db.exists("Workflow State", "Pending"),
    "In Progress": frappe.db.exists("Workflow State", "In Progress"),
    "Completed": frappe.db.exists("Workflow State", "Completed")
}
print(f"\n✓ Workflow States:")
for state, exists in workflow_states_check.items():
    status = "EXISTS" if exists else "MISSING"
    print(f"  - {state}: {status}")

# Check 4: Workflow Actions
workflow_actions_check = {
    "Start": frappe.db.exists("Workflow Action Master", "Start"),
    "Complete": frappe.db.exists("Workflow Action Master", "Complete"),
    "Reset": frappe.db.exists("Workflow Action Master", "Reset"),
    "Reopen": frappe.db.exists("Workflow Action Master", "Reopen")
}
print(f"\n✓ Workflow Actions:")
for action, exists in workflow_actions_check.items():
    status = "EXISTS" if exists else "MISSING"
    print(f"  - {action}: {status}")

# Check 5: Workflow
workflow_exists = frappe.db.exists("Workflow", "Technical Survey Workflow")
print(f"\n✓ Technical Survey Workflow: {'EXISTS' if workflow_exists else 'MISSING'}")

# Check 6: Client Script
client_script_exists = frappe.db.exists("Client Script", "Technical Survey Location Tracker")
print(f"\n✓ Client Script (GPS Tracking): {'EXISTS' if client_script_exists else 'MISSING'}")

# Final Status
all_checks = [location_log_exists] + list(custom_fields_check.values()) + list(workflow_states_check.values()) + list(workflow_actions_check.values()) + [workflow_exists, client_script_exists]

print(f"\n{'=' * 80}")
if all(all_checks):
    print("✓ ALL COMPONENTS INSTALLED SUCCESSFULLY!")
    print("✓ GPS TRACKING READY FOR USE")
else:
    print("✗ SOME COMPONENTS ARE MISSING")
    print("✗ Please review and rerun failed steps")
print(f"{'=' * 80}")
EOF
```

**Expected Output:**
```
================================================================================
GPS TRACKING IMPLEMENTATION VERIFICATION
================================================================================

✓ Location Log child table: EXISTS

✓ Custom Fields:
  - workflow_state: EXISTS
  - location_history_section: EXISTS
  - location_log: EXISTS

✓ Workflow States:
  - Pending: EXISTS
  - In Progress: EXISTS
  - Completed: EXISTS

✓ Workflow Actions:
  - Start: EXISTS
  - Complete: EXISTS
  - Reset: EXISTS
  - Reopen: EXISTS

✓ Technical Survey Workflow: EXISTS

✓ Client Script (GPS Tracking): EXISTS

================================================================================
✓ ALL COMPONENTS INSTALLED SUCCESSFULLY!
✓ GPS TRACKING READY FOR USE
================================================================================
```

---

## Browser Requirements

### Desktop Browsers
- **Chrome**: Version 50+ (Released Apr 2016)
- **Firefox**: Version 55+ (Released Aug 2017)
- **Safari**: Version 13+ (Released Sep 2019)
- **Edge**: Version 15+ (Released Apr 2017)

### Mobile Browsers
- **iOS Safari**: Version 13.3+ (Released Mar 2020)
- **Chrome Android**: Version 50+ (Released Apr 2016)
- **Samsung Internet**: Version 5.0+

### Critical Requirements
1. **HTTPS Only**: Geolocation API requires secure context (HTTPS) in production
2. **User Permission**: Browser must request and user must grant permission
3. **Supported Protocol**: Standard W3C Geolocation API (`navigator.geolocation`)

### Testing with HTTP (Development Only)
- HTTP is allowed on `localhost` for development
- Production deployment MUST use HTTPS
- Self-signed certificates work (browser will warn but allow)

---

## Production Deployment

### HTTPS Configuration

#### Docker Environment (Recommended)
```bash
# Using Let's Encrypt with reverse proxy
# Configure in docker-compose.yml

services:
  frappe:
    environment:
      - HTTPS_ENABLED=1
      - SSL_CERT_PATH=/etc/ssl/certs/
      - SSL_KEY_PATH=/etc/ssl/private/
    volumes:
      - /etc/ssl/certs/:/etc/ssl/certs/
      - /etc/ssl/private/:/etc/ssl/private/
```

#### Browser Permission Prompts

User will see a prompt:
```
"localhost wants to know your location"
[Block] [Allow] [Ask every time]
```

User must click **[Allow]** for GPS capture to work.

### Troubleshooting HTTPS Issues

**Issue**: "Geolocation not supported" in production
**Solution**:
```bash
# Ensure HTTPS is enforced
bench --site localhost set-url-base https://yourdomain.com
bench --site localhost console <<EOF
frappe.conf.server_script_enabled = 1
frappe.conf.allow_cross_domain_requests = 1
EOF
```

---

## Troubleshooting

### Issue: Location Not Captured

| Cause | Solution |
|-------|----------|
| Browser permission denied | Check browser console, click "Allow" on permission prompt |
| HTTP in production | Switch to HTTPS (required by geolocation API) |
| Timeout (10 seconds) | Move to location with GPS signal, try again |
| Browser not supported | Update to modern browser version |
| Location disabled on device | Enable GPS/Location in device settings |

**Check Browser Console:**
```javascript
// In browser dev tools console (F12)
if (navigator.geolocation) {
    console.log("✓ Geolocation supported");
    navigator.geolocation.getCurrentPosition(pos => {
        console.log("Position:", pos.coords);
    }, err => {
        console.error("Error:", err);
    });
} else {
    console.error("✗ Geolocation not supported");
}
```

### Issue: Workflow Buttons Not Visible

1. Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Check user role has "Administrator" permission
3. Verify workflow is set to active:
   ```bash
   bench --site localhost console <<EOF
   import frappe
   wf = frappe.get_doc("Workflow", "Technical Survey Workflow")
   print(f"Workflow Active: {wf.is_active}")
   EOF
   ```

### Issue: Map Link Not Clickable

1. Hard refresh browser cache
2. Check client script is enabled:
   ```bash
   bench --site localhost console <<EOF
   import frappe
   cs = frappe.get_doc("Client Script", "Technical Survey Location Tracker")
   print(f"Client Script Enabled: {cs.enabled}")
   EOF
   ```

### Issue: Location Log Not Updating

1. Check browser console for JavaScript errors (F12)
2. Verify child table permissions:
   ```bash
   bench --site localhost console <<EOF
   import frappe
   meta = frappe.get_meta("Location Log")
   for perm in meta.permissions:
       print(f"{perm.role}: read={perm.read}, write={perm.write}")
   EOF
   ```

---

## Data Structure

### Location Log Entry Example

| Field | Value | Type |
|-------|-------|------|
| timestamp | 2026-02-21 14:30:45.123456 | Datetime |
| previous_status | Pending | String |
| new_status | In Progress | String |
| latitude | 40.7128° | Float (8 decimals) |
| longitude | -74.0060° | Float (8 decimals) |
| location | 40.7128, -74.0060 | String |
| map_link | https://www.google.com/maps?q=40.7128,-74.0060 | URL |
| changed_by | administrator@example.com | User |

### Map Link Format
```
https://www.google.com/maps?q={latitude},{longitude}

Example: https://www.google.com/maps?q=40.7128,-74.0060
```

---

## Customization

### Change Allowed Role (Default: Administrator)

Replace `Administrator` with your role in all workflow transitions:

```bash
bench --site localhost console <<EOF
import frappe

wf = frappe.get_doc("Workflow", "Technical Survey Workflow")
for trans in wf.transitions:
    trans.allowed = "Manager"  # Or your desired role
wf.save()
frappe.db.commit()
print("Workflow updated with new role")
EOF
```

### Add GPS Tracking to Another DocType

Replace `"Technical Survey"` with your target DocType in Step 2.

### Extend Location Log Fields

Add custom fields to Location Log child table:

```bash
bench --site localhost console <<EOF
import frappe

cf = frappe.new_doc("Custom Field")
cf.dt = "Location Log"
cf.fieldname = "altitude"
cf.fieldtype = "Float"
cf.label = "Altitude (meters)"
cf.read_only = 1
cf.insert_after = "longitude"
cf.insert()
frappe.db.commit()
EOF
```

Then update the client script's `fax._captured_location` object to include the new field.

---

## Version Information

- **ERPNext**: v16.x
- **Frappe**: v16.x
- **Kaiten Erp App**: Latest
- **Geolocation API**: W3C Standard
- **Browser Support**: Modern browsers (2016+)
- **Date**: February 2026

---

## Support & Documentation

### Official Resources
- [Frappe Framework Docs](https://frappeframework.com)
- [ERPNext Documentation](https://docs.erpnext.com)
- [W3C Geolocation API](https://www.w3.org/TR/geolocation-API/)
- [Google Maps Platform](https://developers.google.com/maps)

### Common Issues
- **"Insecure context"**: Use HTTPS or localhost
- **"Permission denied"**: User must grant geolocation permission
- **"Timeout"**: Check GPS signal availability
- **"Not supported"**: Update browser to version 50+

---

## License

This implementation is part of the Kaiten Erp application and follows the same license terms.

Implementation Date: February 21, 2026
Last Updated: February 21, 2026
