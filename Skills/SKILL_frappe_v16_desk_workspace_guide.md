# Skill: Adding DocTypes, Pages & Workspaces to Frappe v16 /desk

> **Context:** Frappe v16 (Koristu fork) uses a **three-layer system** for the desk:
> 1. **Desktop Icon** → the icon tile on `/desk` home grid
> 2. **Workspace Sidebar** → the left sidebar when you click into a module
> 3. **Workspace** → the main content area (shortcuts, links, charts)
>
> All three must exist and have matching permissions for a module to be fully accessible.

> **CRITICAL WARNING — Route Conflicts:**
> If you want to add a `/desk` button that links to an **existing built-in DocType** (like `ToDo`, `Note`, `Event`, etc.), **DO NOT create a Workspace for it**.
> 
> **Why:** Workspaces claim routes. A Workspace named "ToDo" takes over `/desk/todo`. But the DocType "ToDo" list view also lives at `/desk/todo`. The Workspace wins — so clicking any link to "ToDo" just shows the workspace page, NOT the actual list. Ctrl+K search also breaks.
>
> **Rule:** If a DocType already exists with the same name you'd give the Workspace, **only create Desktop Icon + Workspace Sidebar** (no Workspace JSON, no Workspace doc). The sidebar item links directly to the DocType. See the "Adding a Button for an Existing DocType" section below.
>
> **Safe to create Workspace:** Only when the Workspace name does NOT collide with any existing DocType name (e.g., a Workspace named "WhatsApp" is fine because there's no DocType called "WhatsApp").

---

## Architecture Overview

```
/desk (home grid)
  └── Desktop Icon (doctype: "Desktop Icon")
        ├── links to → Workspace Sidebar (doctype: "Workspace Sidebar")
        └── clicking opens sidebar + workspace content

Sidebar (left panel)
  └── Workspace Sidebar (doctype: "Workspace Sidebar")
        ├── has items[] → pages, doctypes, reports
        └── header_icon, module, app

Main Content Area
  └── Workspace (doctype: "Workspace")
        ├── content (JSON blocks: headers, shortcuts, spacers)
        ├── shortcuts[] → pages, doctypes
        ├── links[] → pages, doctypes, reports
        └── roles[] → who can see it
```

---

## File Structure (in your app)

```
your_app/
  your_app/
    your_module/
      __init__.py
      doctype/
        __init__.py
        your_doctype/
          __init__.py
          your_doctype.json      ← DocType definition
          your_doctype.py        ← Server-side logic
      page/
        __init__.py
        your_page/
          __init__.py
          your_page.json         ← Page definition
          your_page.js           ← Client-side logic
          your_page.css          ← Styles
          your_page.py           ← Server API for the page
      workspace/
        your_workspace/
          your_workspace.json    ← Workspace definition (NO __init__.py needed)
```

**Key rule:** The `workspace/` folder does NOT need `__init__.py`. Frappe discovers workspace JSONs by convention.

---

## Step 1: Create a DocType

### File: `doctype/whatsapp_settings/whatsapp_settings.json`

```json
{
  "doctype": "DocType",
  "name": "WhatsApp Settings",
  "module": "WhatsApp Chat",
  "engine": "InnoDB",
  "issingle": 1,
  "field_order": ["twilio_account_sid", "twilio_auth_token"],
  "fields": [
    {
      "fieldname": "twilio_account_sid",
      "fieldtype": "Data",
      "label": "Account SID",
      "reqd": 1
    },
    {
      "fieldname": "twilio_auth_token",
      "fieldtype": "Password",
      "label": "Auth Token",
      "reqd": 1
    }
  ],
  "permissions": [
    {
      "role": "System Manager",
      "read": 1, "write": 1, "create": 1, "delete": 1
    },
    {
      "role": "Your Custom Role",
      "read": 1
    }
  ]
}
```

### Critical permission rules:
- **Standard permissions** are in the DocType JSON `permissions[]`
- **Custom DocPerm** (set via UI) **overrides** standard permissions entirely
- If Custom DocPerm exists for a DocType, the JSON `permissions[]` are IGNORED
- Check with: `frappe.get_all("Custom DocPerm", filters={"parent": "Your DocType"})`

---

## Step 2: Create a Page

### File: `page/whatsapp_chat/whatsapp_chat.json`

```json
{
  "doctype": "Page",
  "name": "whatsapp-chat",
  "page_name": "whatsapp-chat",
  "title": "WhatsApp Chat",
  "module": "WhatsApp Chat",
  "standard": "Yes",
  "roles": [
    {"role": "System Manager"},
    {"role": "Your Custom Role"}
  ]
}
```

**Naming convention:**
- Folder name: `whatsapp_chat` (underscores)
- Page `name` field: `whatsapp-chat` (hyphens)
- URL becomes: `/app/whatsapp-chat`

### Files needed in the page folder:

| File | Purpose |
|------|---------|
| `__init__.py` | Empty, makes it a Python package |
| `whatsapp_chat.json` | Page definition |
| `whatsapp_chat.js` | Client-side `frappe.pages['whatsapp-chat'] = ...` |
| `whatsapp_chat.css` | Page styles |
| `whatsapp_chat.py` | Server-side API |

---

## Step 3: Create a Workspace (JSON file)

### File: `workspace/whatsapp/whatsapp.json`

```json
{
  "doctype": "Workspace",
  "name": "WhatsApp",
  "label": "WhatsApp",
  "title": "WhatsApp",
  "module": "WhatsApp Chat",
  "icon": "chat",
  "app": "whatsapp_chat",
  "public": 1,
  "is_hidden": 0,
  "for_user": "",
  "parent_page": "",
  "restrict_to_domain": "",
  "sequence_id": 23.0,
  "type": "Workspace",
  "content": "[{\"id\": \"header_1\", \"type\": \"header\", \"data\": {\"text\": \"<span class=\\\"h4\\\"><b>WhatsApp</b></span>\", \"col\": 12}}, {\"id\": \"shortcut_1\", \"type\": \"shortcut\", \"data\": {\"shortcut_name\": \"WhatsApp Chat\", \"col\": 4}}]",
  "shortcuts": [
    {"label": "WhatsApp Chat", "type": "Page", "link_to": "whatsapp-chat", "color": "#4bce97"},
    {"label": "WhatsApp Settings", "type": "DocType", "link_to": "WhatsApp Settings", "color": "#f5cd47"}
  ],
  "links": [
    {"type": "Link", "label": "WhatsApp Chat", "link_type": "Page", "link_to": "whatsapp-chat", "onboard": 1},
    {"type": "Link", "label": "WhatsApp Settings", "link_type": "DocType", "link_to": "WhatsApp Settings"}
  ],
  "roles": [
    {"role": "System Manager"},
    {"role": "Your Custom Role"}
  ]
}
```

### Critical Workspace fields:

| Field | Required Value | What happens if wrong |
|-------|---------------|----------------------|
| `public` | `1` | Won't show in sidebar |
| `is_hidden` | `0` | Hidden from sidebar |
| `for_user` | `""` (empty string) | If `null`, causes filtering issues |
| `parent_page` | `""` (empty string) | If `null`, causes filtering issues |
| `restrict_to_domain` | `""` (empty string) | If `null`, breaks domain filter query |
| `sequence_id` | Any positive number | `0` may cause sorting issues |
| `type` | `"Workspace"` | Required for proper type identification |
| `link_type` | `null` or omit | If set to `"DocType"`, breaks rendering |

### Content block types (stringified JSON array):

```json
[
  {"id": "unique_id", "type": "header",      "data": {"text": "<b>Title</b>", "col": 12}},
  {"id": "unique_id", "type": "shortcut",    "data": {"shortcut_name": "Label", "col": 4}},
  {"id": "unique_id", "type": "spacer",      "data": {"col": 12}},
  {"id": "unique_id", "type": "chart",       "data": {"chart_name": "Name", "col": 12}},
  {"id": "unique_id", "type": "number_card", "data": {"number_card_name": "Name", "col": 4}},
  {"id": "unique_id", "type": "onboarding",  "data": {"onboarding_name": "Name", "col": 12}}
]
```

---

## Step 4: Create a Workspace Sidebar (runtime only — NOT a file)

> **This is NOT a JSON file.** It must be created via bench console or a migration/patch.

```python
import frappe

sidebar = frappe.get_doc({
    "doctype": "Workspace Sidebar",
    "title": "WhatsApp",
    "header_icon": "chat",
    "standard": 0,
    "app": "whatsapp_chat",
    "module": "WhatsApp Chat",
    "items": [
        {
            "doctype": "Workspace Sidebar Item",
            "label": "WhatsApp Chat",
            "type": "Link",
            "link_type": "Page",
            "link_to": "whatsapp-chat",
            "icon": "chat"
        },
        {
            "doctype": "Workspace Sidebar Item",
            "label": "Settings",
            "type": "Section Break",
            "link_type": "DocType",
            "icon": "settings"
        },
        {
            "doctype": "Workspace Sidebar Item",
            "label": "WhatsApp Settings",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "WhatsApp Settings",
            "icon": "settings"
        },
        {
            "doctype": "Workspace Sidebar Item",
            "label": "WhatsApp Template",
            "type": "Link",
            "link_type": "DocType",
            "link_to": "WhatsApp Template",
            "icon": "file"
        }
    ]
})
sidebar.insert(ignore_permissions=True)
frappe.db.commit()
```

### Workspace Sidebar Item fields:

| Field | Options | Description |
|-------|---------|-------------|
| `type` | `Link`, `Section Break`, `Spacer`, `Sidebar Item Group` | Item type |
| `link_type` | `DocType`, `Page`, `Report`, `Workspace`, `Dashboard`, `URL` | What it links to |
| `link_to` | Dynamic based on `link_type` | Target name |
| `icon` | Any Frappe icon name | Sidebar icon |
| `child` | `0` or `1` | Indented under parent |
| `collapsible` | `0` or `1` | Section can collapse |

---

## Step 5: Create a Desktop Icon (runtime only — NOT a file)

> **This is NOT a JSON file.** It must be created via bench console or a migration/patch.
> This is what actually shows the icon tile on the `/desk` home page.

```python
import frappe

icon = frappe.get_doc({
    "doctype": "Desktop Icon",
    "label": "WhatsApp",
    "icon_type": "Link",
    "link_type": "Workspace Sidebar",
    "link_to": "WhatsApp",              # Must EXACTLY match Workspace Sidebar name
    "parent_icon": "",                   # Empty = top-level on desk
    "standard": 0,
    "app": "whatsapp_chat",
    "icon": "chat",
    "idx": 7,
    "hidden": 0,
    "bg_color": "blue",
    "roles": [
        {"doctype": "Has Role", "role": "System Manager"},
        {"doctype": "Has Role", "role": "Your Custom Role"}
    ]
})
icon.insert(ignore_permissions=True)
frappe.db.commit()
```

### Desktop Icon fields:

| Field | Options | Description |
|-------|---------|-------------|
| `icon_type` | `Link`, `Folder`, `App` | `Link` = single workspace, `Folder` = groups icons, `App` = app grouping |
| `link_type` | `Workspace Sidebar`, `External` | What it links to |
| `link_to` | Name of Workspace Sidebar | Must exactly match sidebar `name` |
| `parent_icon` | Empty or name of another Desktop Icon | Empty = top-level on desk grid |
| `bg_color` | `blue`, `gray` | Icon background color |
| `hidden` | `0` or `1` | `1` = user hid it from their layout |
| `idx` | Integer | Sort order on the grid |

### After creating Desktop Icon, reset saved layouts:

```python
# Delete all saved user layouts so they pick up the new icon
layouts = frappe.get_all("Desktop Layout", fields=["name"])
for l in layouts:
    frappe.delete_doc("Desktop Layout", l.name, ignore_permissions=True)
frappe.db.commit()
```

Users must also clear localStorage:
```js
localStorage.removeItem(frappe.session.user + ':desktop')
```

---

## Step 6: Create Custom Roles (if needed)

```python
import frappe

for role_name in ["AI Chatbot", "WhatsApp Chatbot"]:
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name,
            "desk_access": 1,       # MUST be 1 for desk access
            "is_custom": 1
        }).insert(ignore_permissions=True)

frappe.db.commit()
```

---

## Complete Setup Script (all-in-one)

Run this via `bench --site your-site console` after installing the app:

```python
import frappe

# --- 1. Create Roles ---
for role_name in ["AI Chatbot", "WhatsApp Chatbot"]:
    if not frappe.db.exists("Role", role_name):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": role_name,
            "desk_access": 1,
            "is_custom": 1
        }).insert(ignore_permissions=True)

# --- 2. Create Workspace Sidebar ---
if not frappe.db.exists("Workspace Sidebar", "WhatsApp"):
    frappe.get_doc({
        "doctype": "Workspace Sidebar",
        "title": "WhatsApp",
        "header_icon": "chat",
        "standard": 0,
        "app": "whatsapp_chat",
        "module": "WhatsApp Chat",
        "items": [
            {"doctype": "Workspace Sidebar Item", "label": "WhatsApp Chat",
             "type": "Link", "link_type": "Page", "link_to": "whatsapp-chat", "icon": "chat"},
            {"doctype": "Workspace Sidebar Item", "label": "Settings",
             "type": "Section Break", "link_type": "DocType", "icon": "settings"},
            {"doctype": "Workspace Sidebar Item", "label": "WhatsApp Settings",
             "type": "Link", "link_type": "DocType", "link_to": "WhatsApp Settings"},
            {"doctype": "Workspace Sidebar Item", "label": "WhatsApp Template",
             "type": "Link", "link_type": "DocType", "link_to": "WhatsApp Template"}
        ]
    }).insert(ignore_permissions=True)

# --- 3. Create Desktop Icon ---
if not frappe.db.exists("Desktop Icon", {"label": "WhatsApp"}):
    frappe.get_doc({
        "doctype": "Desktop Icon",
        "label": "WhatsApp",
        "icon_type": "Link",
        "link_type": "Workspace Sidebar",
        "link_to": "WhatsApp",
        "parent_icon": "",
        "standard": 0,
        "app": "whatsapp_chat",
        "icon": "chat",
        "idx": 7,
        "hidden": 0,
        "bg_color": "blue",
        "roles": [
            {"doctype": "Has Role", "role": "System Manager"},
            {"doctype": "Has Role", "role": "AI Chatbot"},
            {"doctype": "Has Role", "role": "WhatsApp Chatbot"}
        ]
    }).insert(ignore_permissions=True)

# --- 4. Reset saved layouts ---
for l in frappe.get_all("Desktop Layout"):
    frappe.delete_doc("Desktop Layout", l.name, ignore_permissions=True)

frappe.db.commit()
print("Setup complete! Clear browser cache and reload /desk")
```

---

## Permission Checklist

For a user to fully access a module, **ALL** of these must align:

| Layer | Where | What to check |
|-------|-------|---------------|
| **Role exists** | Role doctype | `desk_access = 1` |
| **User has role** | User doctype → roles[] | Role assigned to user |
| **Module not blocked** | User → Module Profile → block_modules | Module not in blocked list |
| **DocType permission** | DocType JSON → permissions[] | Role has `read: 1` |
| **Custom DocPerm** | Custom DocPerm doctype | If exists, OVERRIDES DocType JSON permissions |
| **Page permission** | Page JSON → roles[] | Role is listed |
| **Workspace permission** | Workspace JSON → roles[] | Role is listed |
| **Desktop Icon permission** | Desktop Icon → roles[] | Role is listed (empty = all) |

### Debug permission issues:

```python
import frappe

user_email = "user@example.com"
frappe.set_user(user_email)

# Check roles
print(f"Roles: {frappe.get_roles()}")

# Check doctype access
print(f"Can read: {frappe.has_permission('Your DocType', ptype='read')}")

# Check page access
page = frappe.get_doc("Page", "your-page")
user_roles = set(frappe.get_roles())
page_roles = set(r.role for r in page.roles)
print(f"Page accessible: {bool(user_roles & page_roles)}")

# Check if Custom DocPerm overrides exist
custom = frappe.get_all("Custom DocPerm", filters={"parent": "Your DocType"}, fields=["role", "read"])
print(f"Custom DocPerms (override standard): {custom}")

# Check module blocking
user = frappe.get_doc("User", user_email)
blocked = [m.module for m in user.block_modules]
print(f"Module blocked: {'Your Module' in blocked}")
```

---

## Common Gotchas

1. **Workspace shows in sidebar but NOT on `/desk` grid** → Missing Desktop Icon + Workspace Sidebar entries
2. **`for_user: null` instead of `""`** → Can cause workspace to be filtered out
3. **`restrict_to_domain: null` instead of `""`** → Breaks domain filter in `get_workspace_sidebar_items()`
4. **Custom DocPerm exists** → Completely overrides JSON permissions; your new role won't have access until added to Custom DocPerm
5. **Desktop Layout cached** → Users see stale layout; delete from `Desktop Layout` doctype + clear `localStorage`
6. **Role missing `desk_access: 1`** → User can't access desk at all
7. **Module Profile blocks module** → User's Module Profile has the module in `block_modules`
8. **`link_to` in Desktop Icon must match Workspace Sidebar `name` exactly** → Link validation will fail otherwise
9. **After creating Desktop Icons, must run:**
   - `bench --site your-site clear-cache`
   - `sudo bench restart`
   - Users clear localStorage: `localStorage.removeItem(user + ':desktop')`
10. **ROUTE CONFLICT: Workspace name = existing DocType name** → The Workspace hijacks the route. If you create a Workspace named "ToDo", it takes `/desk/todo`. The DocType "ToDo" list also lives at `/desk/todo`. Result: clicking any link/shortcut to "ToDo" shows the workspace page instead of the list. Ctrl+K search for "ToDo" also shows the workspace, not the list. **Fix:** Do NOT create a Workspace when linking to an existing DocType. Only create Desktop Icon + Workspace Sidebar.
11. **Shortcut card shows but clicking does nothing** → Usually caused by #10 (route conflict). The shortcut generates a route that matches the current workspace URL, so the browser thinks nothing changed. Also check that `doc_view` is set (e.g., `"List"`) — without it, the default route may collide.

---

## Quick Reference: Creating Everything from Scratch

```
1. App files (committed to git):
   ├── doctype/your_dt/your_dt.json          ← with permissions[]
   ├── page/your_page/your_page.json         ← with roles[]
   └── workspace/your_ws/your_ws.json        ← with roles[], links[], shortcuts[]

2. Runtime setup (bench console or after_install hook):
   ├── Create Role(s)                         ← desk_access=1
   ├── Create Workspace Sidebar              ← with items[]
   ├── Create Desktop Icon                   ← link_to = Sidebar name
   └── Delete Desktop Layout(s)              ← force refresh for users

3. Deploy:
   ├── bench --site site clear-cache
   ├── sudo bench restart
   └── Users: Cmd+Shift+R + clear localStorage
```

---

## Adding a Button for an Existing DocType (e.g., ToDo, Note, Event)

> **This is the correct approach when you want to add a `/desk` icon that opens an existing built-in DocType's list view.** DO NOT create a Workspace JSON for this — it will cause a route conflict.

### Why No Workspace?

Frappe routes work like this:
- Workspace named "ToDo" → claims route `/desk/todo` → shows workspace content page
- DocType named "ToDo" → its list lives at `/desk/todo` → shows the ToDo list

If both exist, the **Workspace wins**. The list becomes unreachable via normal navigation. Even Ctrl+K search will show the workspace instead of the list.

### What You Need (only 2 things)

You only need **Desktop Icon** + **Workspace Sidebar**. No workspace JSON file. No Workspace doc in the database.

```
/desk (home grid)
  └── Desktop Icon "ToDo"  →  links to Workspace Sidebar "ToDo"
                                  └── Sidebar Item: link_type=DocType, link_to=ToDo
                                        └── User clicks → goes to /desk/todo (the LIST, not a workspace)
```

### Step-by-Step: Complete Patch File

Create a patch file at `your_app/your_module/patches/add_todo_desk_icon.py`:

```python
# Copyright (c) 2026, Your Company
# For license information, please see license.txt

import frappe


def execute():
    # --- IMPORTANT: Delete any conflicting Workspace with same name ---
    # If a Workspace named "ToDo" exists, it hijacks /desk/todo route
    # and the DocType list becomes unreachable
    if frappe.db.exists("Workspace", "ToDo"):
        frappe.delete_doc("Workspace", "ToDo", ignore_permissions=True, force=True)

    # --- Create Workspace Sidebar ---
    # This creates the left sidebar panel when user clicks the desk icon
    if not frappe.db.exists("Workspace Sidebar", "ToDo"):
        frappe.get_doc(
            {
                "doctype": "Workspace Sidebar",
                "title": "ToDo",
                "header_icon": "check",
                "standard": 0,
                "app": "your_app",                # your app name
                "module": "Your Module",           # your module name from modules.txt
                "items": [
                    {
                        "doctype": "Workspace Sidebar Item",
                        "label": "ToDo",
                        "type": "Link",
                        "link_type": "DocType",    # links directly to the DocType list
                        "link_to": "ToDo",         # the DocType name
                        "icon": "check",
                    }
                ],
            }
        ).insert(ignore_permissions=True)

    # --- Create Desktop Icon ---
    # This is the tile/button that appears on the /desk home grid
    if not frappe.db.exists("Desktop Icon", {"label": "ToDo", "standard": 0}):
        frappe.get_doc(
            {
                "doctype": "Desktop Icon",
                "label": "ToDo",
                "icon_type": "Link",
                "link_type": "Workspace Sidebar",
                "link_to": "ToDo",          # must EXACTLY match Workspace Sidebar name
                "parent_icon": "",           # empty = top-level on desk
                "standard": 0,
                "app": "your_app",
                "icon": "check",
                "idx": 50,
                "hidden": 0,
                "bg_color": "blue",
                "roles": [],                 # empty = visible to all roles
            }
        ).insert(ignore_permissions=True)

    # --- Reset saved Desktop Layouts ---
    # Users have cached layouts; delete them so the new icon appears
    for layout in frappe.get_all("Desktop Layout"):
        frappe.delete_doc("Desktop Layout", layout.name, ignore_permissions=True)

    frappe.db.commit()
```

### Register the Patch

Add to your `patches.txt` under `[post_model_sync]`:

```
your_app.your_module.patches.add_todo_desk_icon
```

### Apply It

```bash
bench --site your-site migrate
# If migrate fails on unrelated issues, run directly:
bench --site your-site console
# Then paste the execute() body from the patch

# Always clear cache after:
bench --site your-site clear-cache
```

### What the User Sees After

1. `/desk` home grid → "ToDo" icon tile appears
2. Click the icon → left sidebar shows with "ToDo" item
3. Click "ToDo" in sidebar → navigates to `/desk/todo` → shows the **ToDo list view** (not a workspace page)
4. Ctrl+K → search "ToDo" → opens the ToDo list correctly

### Decision Flowchart

```
Do you want to add a /desk button for something?
  │
  ├── Is it a NEW custom module with custom DocTypes/Pages?
  │     └── YES → Create all 3: Workspace JSON + Workspace Sidebar + Desktop Icon
  │             (Workspace name must NOT match any existing DocType name)
  │
  └── Is it for an EXISTING built-in DocType (ToDo, Note, Event, etc.)?
        └── YES → Create only 2: Workspace Sidebar + Desktop Icon
                  DO NOT create a Workspace (it will steal the route)
                  Also DELETE any Workspace with the same name if one exists
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Click desk icon → shows blank page with shortcut card, card click does nothing | Workspace with same name as DocType exists, route conflict | Delete the Workspace doc from DB and remove workspace JSON file |
| Ctrl+K search shows workspace page instead of DocType list | Same route conflict as above | Delete the Workspace |
| Desk icon doesn't appear after migrate | Desktop Layout cached for users | Delete all Desktop Layout docs + user clears localStorage |
| Sidebar appears but no items | Workspace Sidebar created without items[] | Re-create with proper items array |
| Icon appears but clicking shows wrong sidebar | `link_to` in Desktop Icon doesn't match Workspace Sidebar name | Ensure exact name match (case-sensitive) |
