# Test2 DocType Implementation Guide

## Overview

This guide documents the complete implementation of a **Test2** DocType in ERPNext v16 with the following features:

1. **Custom DocType** with tabbed layout (Details + Connections tabs)
2. **Workflow System** with Pending → In Progress → Completed states
3. **GPS Location Tracking** that captures device location on every status change
4. **Location History** child table with clickable Google Maps links

---

## Architecture

Test2 DocType
├── Fields
│   ├── test2_name (Data) - Primary identifier
│   ├── date_of_birth (Date)
│   ├── workflow_state (Link) - Current workflow status
│   └── location_log (Table) - Child table for location history
├── Workflow: Test2 Workflow
│   ├── States: Pending, In Progress, Completed
│   └── Role: Administrator
├── Client Script: Test2 Location Tracker
│   └── Captures GPS + logs to child table on status change
└── Connections: Lead, Customer, Quotation

---

## Child Table: Test2 Location Log

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | Datetime | When the status change occurred |
| `previous_status` | Data | Status before the change |
| `new_status` | Data | Status after the change |
| `location` | Data | Lat, Long coordinates |
| `map_link` | Data | Clickable Google Maps URL |
| `latitude` | Float | GPS Latitude (8 decimal precision) |
| `longitude` | Float | GPS Longitude (8 decimal precision) |
| `changed_by` | Link (User) | User who made the status change |

---

## Workflow Diagram

┌─────────┐   Start    ┌─────────────┐  Complete  ┌───────────┐
│ Pending │ ─────────► │ In Progress │ ─────────► │ Completed │
└─────────┘            └─────────────┘            └───────────┘
                              │                         │
                              │ Reset                   │ Reopen
                              ▼                         ▼
                        ┌─────────┐              ┌─────────────┐
                        │ Pending │ ◄────────────│ In Progress │
                        └─────────┘              └─────────────┘

---

## Implementation Steps

### Prerequisites
- ERPNext v16 running in Docker
- Site name: `frontend`
- Container name: `frappe_docker-backend-1`

---

### Step 1: Create Child Table DocType

bash
docker exec frappe_docker-backend-1 bash -c 'cd /home/frappe/frappe-bench && bench --site frontend console <<EOF
child_doc = frappe.new_doc("DocType")
child_doc.name = "Test2 Location Log"
child_doc.module = "Setup"
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
print("Created: Test2 Location Log")
EOF'

---

### Step 2: Add Custom Fields to Test2

bash
docker exec frappe_docker-backend-1 bash -c 'cd /home/frappe/frappe-bench && bench --site frontend console <<EOF
# Workflow State field
wf = frappe.new_doc("Custom Field")
wf.dt = "Test2"
wf.fieldname = "workflow_state"
wf.fieldtype = "Link"
wf.label = "Workflow Status"
wf.options = "Workflow State"
wf.read_only = 1
wf.insert_after = "date_of_birth"
wf.insert()

# Section Break
sb = frappe.new_doc("Custom Field")
sb.dt = "Test2"
sb.fieldname = "location_history_section"
sb.fieldtype = "Section Break"
sb.label = "Location History"
sb.insert_after = "workflow_state"
sb.insert()

# Location Log Table
lt = frappe.new_doc("Custom Field")
lt.dt = "Test2"
lt.fieldname = "location_log"
lt.fieldtype = "Table"
lt.label = "Location Log"
lt.options = "Test2 Location Log"
lt.insert_after = "location_history_section"
lt.read_only = 1
lt.insert()

frappe.db.commit()
print("Fields added!")
EOF'

---

### Step 3: Create Workflow States and Actions

bash
docker exec frappe_docker-backend-1 bash -c 'cd /home/frappe/frappe-bench && bench --site frontend console <<EOF
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
EOF'

---

### Step 4: Create the Workflow

bash
docker exec frappe_docker-backend-1 bash -c 'cd /home/frappe/frappe-bench && bench --site frontend console <<EOF
wf = frappe.new_doc("Workflow")
wf.workflow_name = "Test2 Workflow"
wf.document_type = "Test2"
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
EOF'

---

### Step 5: Create Client Script for Location Tracking

Create a Python file `update_client_script.py`:

python
import frappe

script_code = '''
frappe.ui.form.on("Test2", {
    refresh: function(frm) {
        frm._previous_workflow_state = frm.doc.workflow_state;
        
        // Render map links as clickable in the grid
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
                        doctype: "Test2 Location Log",
                        parent: frm.doc.name,
                        parenttype: "Test2",
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

# Delete old and create new client script
if frappe.db.exists("Client Script", "Test2 Location Tracker"):
    frappe.delete_doc("Client Script", "Test2 Location Tracker")

cs = frappe.new_doc("Client Script")
cs.name = "Test2 Location Tracker"
cs.dt = "Test2"
cs.view = "Form"
cs.enabled = 1
cs.script = script_code
cs.insert()
frappe.db.commit()
print("Client Script created!")

Execute it:
bash
docker cp update_client_script.py frappe_docker-backend-1:/tmp/
docker exec frappe_docker-backend-1 bash -c 'cd /home/frappe/frappe-bench && bench --site frontend execute "exec(open(\"/tmp/update_client_script.py\").read())"'[2:40 PM]
---

### Step 6: Clear Cache

bash
docker exec frappe_docker-backend-1 bash -c 'cd /home/frappe/frappe-bench && bench --site frontend clear-cache'

---

## Testing

1. Open ERPNext at `http://localhost:8080`
2. Go to **Test2** list
3. Create or open a Test2 document
4. Click a workflow action button (e.g., "Start")
5. Allow location access when browser prompts
6. Check the **Location History** section:
   - Should show timestamp, status change, coordinates
   - **Map Link** column shows clickable "Open Map" link
   - Clicking opens Google Maps at exact location

---

## Important Notes

### Browser Requirements
- **HTTPS required** for geolocation in production
- User must **Allow** location permission
- Works on desktop and mobile browsers

### Customization
- Change `Administrator` role in workflow to allow other roles
- Add more workflow states/transitions as needed
- Modify child table fields for additional tracking data

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Location not captured | Check browser permissions, ensure HTTPS |
| Workflow buttons not showing | Verify user has Administrator role |
| Map link not clickable | Hard refresh browser (Cmd+Shift+R) |
| Child table not updating | Check browser console for JS errors |

---

## Version Info

- **ERPNext**: v16.x
- **Frappe**: v16.x
- **Docker Container**: `frappe_docker-backend-1`
- **Site**: `frontend`
- **Date**: February 2026