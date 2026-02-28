# GPS Tracking Implementation Guide - Kaiten Erp

## Overview

This guide documents the complete implementation of GPS tracking in ERPNext v16 with the Kaiten Erp module.

**IMPORTANT**: Replace `<TargetDocType>` with your actual DocType name (e.g., `Job File`, `Project Installation`, etc.) in all commands below.

---

## Architecture

```
<TargetDocType>
├── Fields
│   ├── workflow_state (Link) - Current workflow status
│   └── location_log (Table) - Child table for location history
├── Workflow: <TargetDocType> Workflow
│   ├── States: Pending, In Progress, Completed
│   └── Role: Administrator (configurable)
├── Client Script: <TargetDocType> Location Tracker
│   └── Captures GPS + logs to child table on status change
└── Child Table: <TargetDocType> Location Log
```

---

## Implementation Steps

### Prerequisites

- ERPNext v16 running (bench)
- Site name: `localhost`
- App: Kaiten Erp
- Module: Kaiten Erp

---

### Step 1: Create Child Table DocType

Replace `<TargetDocType>` with your DocType name before running.

```bash
bench --site localhost console <<EOF
child_doc = frappe.new_doc("DocType")
child_doc.name = "Location Log"
child_doc.module = "Kaiten Erp"
child_doc.custom = 1
child_doc.istable = 1
child_doc.editable_grid = 1
child_doc.append("fields", {"fieldname": "timestamp", "fieldtype": "Datetime", "label": "Date Time", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "previous_status", "fieldtype": "Data", "label": "Previous Status", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "new_status", "fieldtype": "Data", "label": "New Status", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "location", "fieldtype": "Data", "label": "Location", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "map_link", "fieldtype": "Data", "label": "Map Link", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "latitude", "fieldtype": "Float", "label": "Latitude", "precision": 8, "read_only": 1})
child_doc.append("fields", {"fieldname": "longitude", "fieldtype": "Float", "label": "Longitude", "precision": 8, "read_only": 1})
child_doc.append("fields", {"fieldname": "changed_by", "fieldtype": "Link", "label": "Changed By", "options": "User", "in_list_view": 1, "read_only": 1})
child_doc.append("permissions", {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1})
child_doc.insert()
frappe.db.commit()
print("Created: <TargetDocType> Location Log")
EOF
```

---

### Step 2: Add Custom Fields to Target DocType

Replace `<TargetDocType>` and `<InsertAfterField>` (the field to insert after).

```bash
bench --site localhost console <<EOF
# Workflow State field - REPLACE <InsertAfterField> with actual fieldname
wf = frappe.new_doc("Custom Field")
wf.dt = "<TargetDocType>"
wf.fieldname = "workflow_state"
wf.fieldtype = "Link"
wf.label = "Workflow Status"
wf.options = "Workflow State"
wf.read_only = 1
wf.insert_after = "<InsertAfterField>"
wf.insert()

# Section Break
sb = frappe.new_doc("Custom Field")
sb.dt = "<TargetDocType>"
sb.fieldname = "location_history_section"
sb.fieldtype = "Section Break"
sb.label = "Location History"
sb.insert_after = "workflow_state"
sb.insert()

# Location Log Table
lt = frappe.new_doc("Custom Field")
lt.dt = "<TargetDocType>"
lt.fieldname = "location_log"
lt.fieldtype = "Table"
lt.label = "Location Log"
lt.options = "<TargetDocType> Location Log"
lt.insert_after = "location_history_section"
lt.read_only = 1
lt.insert()

frappe.db.commit()
print("Fields added!")
EOF
```

---

### Step 3: Create Workflow States and Actions

```bash
bench --site localhost console <<EOF
# Create Workflow States
for state in ["Pending", "In Progress", "Completed"]:
    if not frappe.db.exists("Workflow State", state):
        ws = frappe.new_doc("Workflow State")
        ws.workflow_state_name = state
        ws.insert()
        print(f"Created State: {state}")

# Create Workflow Actions
for action in ["Start", "Complete", "Reset", "Reopen"]:
    if not frappe.db.exists("Workflow Action Master", action):
        wa = frappe.new_doc("Workflow Action Master")
        wa.workflow_action_name = action
        wa.insert()
        print(f"Created Action: {action}")

frappe.db.commit()
EOF
```

---

### Step 4: Create the Workflow

Replace `<TargetDocType>` and `<AllowedRole>` (e.g., Administrator, All Shares, etc.).

```bash
bench --site localhost console <<EOF
wf = frappe.new_doc("Workflow")
wf.workflow_name = "<TargetDocType> Workflow"
wf.document_type = "<TargetDocType>"
wf.is_active = 1
wf.send_email_alert = 0
wf.append("states", {"state": "Pending", "doc_status": 0, "allow_edit": "<AllowedRole>"})
wf.append("states", {"state": "In Progress", "doc_status": 0, "allow_edit": "<AllowedRole>"})
wf.append("states", {"state": "Completed", "doc_status": 0, "allow_edit": "<AllowedRole>"})
wf.append("transitions", {"state": "Pending", "action": "Start", "next_state": "In Progress", "allowed": "<AllowedRole>", "allow_self_approval": 1})
wf.append("transitions", {"state": "In Progress", "action": "Complete", "next_state": "Completed", "allowed": "<AllowedRole>", "allow_self_approval": 1})
wf.append("transitions", {"state": "In Progress", "action": "Reset", "next_state": "Pending", "allowed": "<AllowedRole>", "allow_self_approval": 1})
wf.append("transitions", {"state": "Completed", "action": "Reopen", "next_state": "In Progress", "allowed": "<AllowedRole>", "allow_self_approval": 1})
wf.insert()
frappe.db.commit()
print("Workflow created!")
EOF
```

---

### Step 5: Create Client Script for Location Tracking

Create a Python file `create_client_script.py`:

```python
import frappe

def create_location_tracker_client_script(doctype):
    script_code = f'''frappe.ui.form.on("{doctype}", {{
    refresh: function(frm) {{
        frm._previous_workflow_state = frm.doc.workflow_state;
        
        // Render map links as clickable in the grid
        if (frm.doc.location_log && frm.doc.location_log.length > 0) {{
            setTimeout(function() {{
                frm.fields_dict.location_log.grid.wrapper.find(".grid-row").each(function(idx) {{
                    var row = frm.doc.location_log[idx];
                    if (row && row.map_link) {{
                        var map_cell = $(this).find('[data-fieldname="map_link"]');
                        if (map_cell.length) {{
                            map_cell.html('<a href="' + row.map_link + '" target="_blank" style="color:#2490EF;">Open Map</a>');
                        }}
                    }}
                });
            }}, 300);
        }}
    }},
    before_workflow_action: async function(frm) {{
        frm._previous_workflow_state = frm.doc.workflow_state || "New";
        return new Promise((resolve, reject) => {{
            if (navigator.geolocation) {{
                frappe.show_alert({{message: "Capturing location...", indicator: "blue"}});
                navigator.geolocation.getCurrentPosition(
                    function(position) {{
                        var lat = position.coords.latitude;
                        var lng = position.coords.longitude;
                        frm._captured_location = {{
                            latitude: lat,
                            longitude: lng,
                            location: lat + ", " + lng,
                            map_link: "https://www.google.com/maps?q=" + lat + "," + lng
                        }};
                        frappe.show_alert({{message: "Location captured!", indicator: "green"}});
                        resolve();
                    }},
                    function(error) {{
                        frm._captured_location = {{
                            latitude: 0,
                            longitude: 0,
                            location: "Location unavailable",
                            map_link: ""
                        }};
                        resolve();
                    }},
                    {{enableHighAccuracy: true, timeout: 10000, maximumAge: 0}}
                );
            }} else {{
                frm._captured_location = {{latitude: 0, longitude: 0, location: "Geolocation not supported", map_link: ""}};
                resolve();
            }}
        }});
    }},
    after_workflow_action: function(frm) {{
        if (frm._captured_location && frm._previous_workflow_state !== frm.doc.workflow_state) {{
            frappe.call({{
                method: "frappe.client.insert",
                args: {{
                    doc: {{
                        doctype: "{doctype} Location Log",
                        parent: frm.doc.name,
                        parenttype: "{doctype}",
                        parentfield: "location_log",
                        timestamp: frappe.datetime.now_datetime(),
                        previous_status: frm._previous_workflow_state || "New",
                        new_status: frm.doc.workflow_state,
                        location: frm._captured_location.location,
                        latitude: frm._captured_location.latitude,
                        longitude: frm._captured_location.longitude,
                        map_link: frm._captured_location.map_link,
                        changed_by: frappe.session.user
                    }}
                }},
                callback: function(r) {{
                    frm.reload_doc();
                    frappe.show_alert({{message: "Location logged!", indicator: "green"}});
                }}
            }});
        }}
    }}
}});
'''
    
    script_name = f"{doctype} Location Tracker"
    
    # Delete old script if exists
    if frappe.db.exists("Client Script", script_name):
        frappe.delete_doc("Client Script", script_name)
    
    cs = frappe.new_doc("Client Script")
    cs.name = script_name
    cs.dt = doctype
    cs.view = "Form"
    cs.enabled = 1
    cs.script = script_code
    cs.insert()
    frappe.db.commit()
    print(f"Client Script created: {script_name}")

# Usage: Replace 'Job File' with your target DocType
create_location_tracker_client_script("Job File")
```

Execute it:

```bash
bench --site localhost console <<EOF
exec(open("create_client_script.py").read())
EOF
```

Or alternatively:

```bash
bench --site localhost execute "exec(open('create_client_script.py').read())"
```

---

### Step 6: Clear Cache

```bash
bench --site localhost clear-cache
```

---

## Usage with Specific DocTypes

### For Job File

```bash
# Step 1: Create Child Table
bench --site localhost console <<EOF
child_doc = frappe.new_doc("DocType")
child_doc.name = "Job File Location Log"
child_doc.module = "Kaiten Erp"
child_doc.custom = 1
child_doc.istable = 1
child_doc.editable_grid = 1
child_doc.append("fields", {"fieldname": "timestamp", "fieldtype": "Datetime", "label": "Date Time", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "previous_status", "fieldtype": "Data", "label": "Previous Status", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "new_status", "fieldtype": "Data", "label": "New Status", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "location", "fieldtype": "Data", "label": "Location", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "map_link", "fieldtype": "Data", "label": "Map Link", "in_list_view": 1, "read_only": 1})
child_doc.append("fields", {"fieldname": "latitude", "fieldtype": "Float", "label": "Latitude", "precision": 8, "read_only": 1})
child_doc.append("fields", {"fieldname": "longitude", "fieldtype": "Float", "label": "Longitude", "precision": 8, "read_only": 1})
child_doc.append("fields", {"fieldname": "changed_by", "fieldtype": "Link", "label": "Changed By", "options": "User", "in_list_view": 1, "read_only": 1})
child_doc.append("permissions", {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1})
child_doc.insert()
frappe.db.commit()
print("Created: Job File Location Log")
EOF

# Step 2: Add Custom Fields (insert after 'workflow_state' or your preferred field)
bench --site localhost console <<EOF
# Workflow State field (if not already exists)
if not frappe.db.exists("Custom Field", {"dt": "Job File", "fieldname": "workflow_state"}):
    wf = frappe.new_doc("Custom Field")
    wf.dt = "Job File"
    wf.fieldname = "workflow_state"
    wf.fieldtype = "Link"
    wf.label = "Workflow Status"
    wf.options = "Workflow State"
    wf.read_only = 1
    wf.insert_after = "status"
    wf.insert()

# Section Break
sb = frappe.new_doc("Custom Field")
sb.dt = "Job File"
sb.fieldname = "location_history_section"
sb.fieldtype = "Section Break"
sb.label = "Location History"
sb.insert_after = "workflow_state"
sb.insert()

# Location Log Table
lt = frappe.new_doc("Custom Field")
lt.dt = "Job File"
lt.fieldname = "location_log"
lt.fieldtype = "Table"
lt.label = "Location Log"
lt.options = "Job File Location Log"
lt.insert_after = "location_history_section"
lt.read_only = 1
lt.insert()

frappe.db.commit()
print("Fields added!")
EOF

# Step 3: Workflow States and Actions (skip if already created)
# (Use the commands from Step 3 above)

# Step 4: Create Workflow
bench --site localhost console <<EOF
wf = frappe.new_doc("Workflow")
wf.workflow_name = "Job File Workflow"
wf.document_type = "Job File"
wf.is_active = 1
wf.send_email_alert = 0
wf.append("states", {"state": "Pending", "doc_status": 0, "allow_edit": "Administrator"})
wf.append("states", {"state": "In Progress", "doc_status": 0, "allow_edit": "Administrator"})
wf.append("states", {"state": "Completed", "doc_status": 0, "allow_edit": "Administrator"})
wf.append("transitions", {"state": "Pending", "action": "Start", "next_state": "In Progress", "allowed": "Administrator", "allow_self_approval": 1})
wf.append("transitions", {"state": "In Progress", "action": "Complete", "next_state": "Completed", "allowed": "Administrator", "allow_self_approval": 1})
wf.append("transitions", {"state": "In Progress", "action": "Reset", "next_state": "Pending", "allowed": "Administrator", "allow_self_approval": 1})
wf.append("transitions", {"state": "Completed", "action": "Reopen", "next_state": "In Progress", "allowed": "Administrator", "allow_self_approval": 1})
wf.insert()
frappe.db.commit()
print("Workflow created!")
EOF

# Step 5: Create Client Script
bench --site localhost console <<EOF
script_code = '''
frappe.ui.form.on("Job File", {
    refresh: function(frm) {
        frm._previous_workflow_state = frm.doc.workflow_state;
        
        if (frm.doc.location_log && frm.doc.location_log.length > 0) {
            setTimeout(function() {
                frm.fields_dict.location_log.grid.wrapper.find(".grid-row").each(function(idx) {
                    var row = frm.doc.location_log[idx];
                    if (row && row.map_link) {
                        var map_cell = $(this).find('[data-fieldname="map_link"]');
                        if (map_cell.length) {
                            map_cell.html('<a href="' + row.map_link + '" target="_blank" style="color:#2490EF;">Open Map</a>');
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
                frappe.show_alert({message: "Capturing location...", indicator: "blue"});
                navigator.geolocation.getCurrentPosition(
                    function(position) {
                        var lat = position.coords.latitude;
                        var lng = position.coords.longitude;
                        frm._captured_location = {
                            latitude: lat,
                            longitude: lng,
                            location: lat + ", " + lng,
                            map_link: "https://www.google.com/maps?q=" + lat + "," + lng
                        };
                        frappe.show_alert({message: "Location captured!", indicator: "green"});
                        resolve();
                    },
                    function(error) {
                        frm._captured_location = {
                            latitude: 0,
                            longitude: 0,
                            location: "Location unavailable",
                            map_link: ""
                        };
                        resolve();
                    },
                    {enableHighAccuracy: true, timeout: 10000, maximumAge: 0}
                );
            } else {
                frm._captured_location = {latitude: 0, longitude: 0, location: "Geolocation not supported", map_link: ""};
                resolve();
            }
        });
    },
    after_workflow_action: function(frm) {
        if (frm._captured_location && frm._previous_workflow_state !== frm.doc.workflow_state) {
            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype: "Job File Location Log",
                        parent: frm.doc.name,
                        parenttype: "Job File",
                        parentfield: "location_log",
                        timestamp: frappe.datetime.now_datetime(),
                        previous_status: frm._previous_workflow_state || "New",
                        new_status: frm.doc.workflow_state,
                        location: frm._captured_location.location,
                        latitude: frm._captured_location.latitude,
                        longitude: frm._captured_location.longitude,
                        map_link: frm._captured_location.map_link,
                        changed_by: frappe.session.user
                    }
                },
                callback: function(r) {
                    frm.reload_doc();
                    frappe.show_alert({message: "Location logged!", indicator: "green"});
                }
            });
        }
    }
});
'''

if frappe.db.exists("Client Script", "Job File Location Tracker"):
    frappe.delete_doc("Client Script", "Job File Location Tracker")

cs = frappe.new_doc("Client Script")
cs.name = "Job File Location Tracker"
cs.dt = "Job File"
cs.view = "Form"
cs.enabled = 1
cs.script = script_code
cs.insert()
frappe.db.commit()
print("Client Script created!")
EOF

# Step 6: Clear Cache
bench --site localhost clear-cache
```

---

## Important Notes

### Browser Requirements

- **HTTPS required** for geolocation in production
- User must **Allow** location permission
- Works on desktop and mobile browsers

### Role Configuration

- Change `Administrator` to any role in the workflow transitions
- Common roles: `All Shares`, `Owner`, `System Manager`, or custom roles

### Module Assignment

- All components are assigned to **Kaiten Erp** module
- This satisfies the requirement that DocTypes belong to Kaiten Erp, not Setup

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Location not captured | Check browser permissions, ensure HTTPS |
| Workflow buttons not showing | Verify user has the allowed role |
| Map link not clickable | Hard refresh browser (Ctrl+Shift+R) |
| Child table not updating | Check browser console for JS errors |

---

## Version Info

- **ERPNext**: v16.x
- **Frappe**: v16.x
- **App**: Kaiten Erp
- **Site**: localhost
- **Date**: February 2026
