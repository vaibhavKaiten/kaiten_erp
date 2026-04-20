# Kaiten ERP — Deep Context Document

> **Purpose:** Full project knowledge base for AI-assisted development. Covers everything built, decisions made, challenges solved, and current state of the codebase as of April 2026.

---

## 1. What Is Kaiten ERP?

Kaiten ERP is a **custom Frappe v16 app** (`kaiten_erp`) built on top of **ERPNext** for managing the full lifecycle of **residential and commercial rooftop solar installation projects** in India. The app is developed by Kaiten Software for an internal operations team that manages vendor field crews, customer sites, procurement, billing, and regulatory approvals (DISCOM).

**Core problem being solved:** A solar company installs systems across hundreds of customer sites. Each job requires coordinating a sales team, two types of field vendors (technical installation + meter installation), internal reviewers, accounts, and DISCOM applications — all sequentially, with money gating field work. Standard ERPNext has no concept of this workflow. Kaiten ERP builds this entire machinery.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Framework | Frappe v16 |
| ERP Base | ERPNext (extended) |
| Backend | Python ≥ 3.14 |
| Frontend | Frappe Desk (JS) + Mobile API |
| DB | MariaDB via Frappe ORM |
| Linting | ruff (Python), eslint + prettier (JS) |
| Code Style | Tabs for indent, double quotes, line-length 110 |
| Hosting | Single-site bench (`dev-bench`) |
| App path | `/home/vaibhav/frappe/frappe-bench/apps/kaiten_erp` |

---

## 3. Architecture Overview

```
kaiten_erp/                         ← Frappe app root
├── hooks.py                        ← ALL wiring: fixtures, doc_events, permissions, doctype_js
├── patches.txt                     ← Migration patch registry (~32 patches)
├── fixtures/                       ← Exported JSON: Custom Fields, Workflows, Roles, Permissions
├── patches/                        ← One-off migration scripts
├── public/
│   ├── js/                         ← Per-DocType client scripts (17 files)
│   └── css/quick_hide.css          ← Desk CSS overrides
└── kaiten_erp/                     ← Inner module ("Kaiten Erp")
    ├── api/                        ← Whitelisted APIs & shared logic (25 files)
    ├── cron_job/                   ← Scheduler tasks
    ├── doc_events/                 ← DocType event handlers (16 files)
    ├── doctype/                    ← Custom DocType definitions (24 DocTypes)
    ├── patches/                    ← Patch implementations (linked from patches.txt)
    ├── permissions/                ← has_permission + permission_query (11 files)
    └── workspace/                  ← Frappe Desk workspace JSON
```

**Key architectural rule:** Double module nesting — all internal imports use `kaiten_erp.kaiten_erp.{subpackage}` (outer = app, inner = Frappe module).

---

## 4. The Core Domain Model — Solar Job Lifecycle

Every solar installation follows a fixed 7-step lifecycle, each managed by a separate DocType:

```
Lead
 └─► Job File  (created when Lead is "Qualified")
      └─► Opportunity  (created when Job File is "Job File Initiated")
           └─► Technical Survey        [Stage 1]
           └─► Structure Mounting      [Stage 2]
           └─► Project Installation    [Stage 3]
           └─► Meter Installation      [Stage 4]
           └─► Meter Commissioning     [Stage 5]
           └─► Verification Handover   [Stage 6]
      └─► Quotation  (after Technical Survey is approved)
      └─► Sales Order  (after Quotation is "Advance Approved")
      └─► Material Request  (auto-created on SO submit)
      └─► Delivery Note  (stock transfer to site)
      └─► Sales Invoice  (milestone-based, single saleable item)
      └─► Payment Entry  (per milestone)
```

All 6 execution DocTypes:
- Link to **Job File** via `job_file` or `custom_job_file`
- Have their own Frappe **Workflow** (managed via fixtures)
- Use **role-targeted ToDos** for every state transition
- Carry GPS coordinates and a **Location Log** child table
- Have their own **has_permission** + **permission_query_conditions**

---

## 5. Custom DocTypes (Full List)

### 5.1 Core Business DocTypes

#### Job File
The central anchor of every job. Created automatically when a Lead is qualified.

**Key Fields:**
- `lead` — Link to Lead
- `customer` — Link to Customer (auto-created from Lead)
- `sales_order` — Link to Sales Order
- `workflow_state` — States: Draft → In Progress → Approval Pending → Job File Initiated
- `mrp` — MRP price
- `negotiated_amount` — Final deal amount
- `token_amount_recieved` — Token amount (triggers Account Manager ToDo)
- `first_name`, `last_name`, `mobile_number`, `email` — Customer snapshot
- `address_line_1/2`, `city`, `state`, `territory` — Location snapshot
- `k_number` — DISCOM K-number (consumer number)
- `existing_load_kw`, `monthly_consumption`, `sanctioned_load_kw`, `required_load_kw` — Electrical
- `phase_type` — Single/Three phase
- `discom` — Link to DISCOM Master
- `proposed_system` — Link to Item (solar system size)
- `custom_assigned_technical_supplier` — Supplier for Technical Survey/Installation/VH
- `custom_assigned_meter_supplier` — Supplier for Meter Installation/Commissioning
- `custom_job_file_owner` — Assigned Sales Manager (User)
- `custom_technical_survey`, `custom_structure_mounting`, `custom_project_installation`, `custom_meter_installation`, `custom_meter_commissioning`, `custom_verification_handover` — Links to all execution documents
- `custom_opportunity` — Link to Opportunity
- `table_royw` — Job Execution child table (tracks all execution doc states)
- `custom_total_selling_price`, `custom_total_material_cost`, `custom_gross_profit`, `custom_profit_percentage`, `custom_cost_` — Profitability fields (auto-calculated)

**Workflow States:** Draft → In Progress → Approval Pending → Job File Initiated

**Key Automation:**
- `on_update` when state → "Job File Initiated": Creates ALL 6 execution documents + Opportunity simultaneously. Validates that both technical and meter suppliers are assigned.
- `on_update` when state → "Approval Pending": Creates ToDo for Execution Managers to approve
- Token amount received → Creates Accounts Manager ToDo
- DISCOM change → Syncs customer into DISCOM Master's linked customers table

#### Technical Survey
The first field visit. Vendor Executive goes to the site, records site data, and recommends a solar system configuration.

**Key Fields:**
- `proposed_system_kw__tier` — Link to Item (the solar product)
- `bom_reference` — BOM name
- `panel`, `panel_qty_bom` — Panel item + quantity
- `inverter`, `inverter_qty_bom` — Inverter item + quantity
- `battery`, `battery_qty_bom` — Battery item + quantity (optional)
- `table_vctx` — BOM Items child table (full component list)
- `visit_type` — Select: Initial/Revisit
- `data_ycke` — Scheduled Date
- `data_tila` — Schedule Slot
- `data_zxjn` — Actual Start Date (auto-set when In Progress)
- `data_xwsx` — Completion Date (auto-set when Completed)
- `site_type` — Domestic/Commercial/Industrial (affects BOM component flexibility)
- `roof_type`, `roof_area_sqft`, `number_of_floors`, `roof_orientation`
- `azimuth_deg`, `tilt_deg` (tilt is auto-calculated client-side)
- `shading_level`, `feasibility_status`, `proposed_structure_type`
- `front`, `back`, `left`, `right`, `front_left`, `front_right`, `back_left`, `back_right`, `front_down`, `overall_site_view` — Photo attachments × 9 directions
- `marked_roof_layout`, `sld_draft`, `electrical_notes` — Technical documents
- `gps_latitude`, `gps_longitude` — GPS coordinates (cleared after logging)
- `location_log` — Location Log child table

**Critical Rules:**
- Once `workflow_state == "Approved"`, the system configuration fields (`proposed_system_kw__tier`, `panel`, `panel_qty_bom`, `inverter`, `inverter_qty_bom`, `battery`, `battery_qty_bom`, `table_vctx`) are **permanently locked** — server-side guard in `_guard_approved_system_config()` + client-side `lock_system_config_if_approved()`.
- Approval triggers: Link TS to Opportunity, create "Prepare Final Quotation" ToDo for Sales Manager, push panel/inverter counts to Project Installation, recalculate Job File profitability.

#### Structure Mounting
Field execution: vendor crew installs the mounting structure on the roof.

**Key Fields:** `job_file`, `lead`, `assigned_vendor`, `assigned_internal_user`, `structure_type`, `anchoring_type`, `strucutre_height`, planned/actual dates, GPS + Location Log, photo attachments.

**Workflow:** Draft → Assigned to Vendor → In Progress → Submitted → Completed → Approved / Rejected

#### Project Installation
Panel and inverter installation.

**Key Fields:** All Structure Mounting fields plus `panel_item`, `panel_count`, `custom_inverter_count` (auto-populated from approved TS), `planned_start_date`, `planned_end_date`, `actual_start_date`, `actual_end_date`, `installation_notes`, `safety__deviation_notes`, GPS + Location Log, 5 photo fields.

**Extra automation:** `validate` populates `structure_type`, `anchoring_type`, `structure_height_m` from the linked Structure Mounting doc (read-only snapshot).

**Payment gate:** `validate_installation_payment` runs on validate — can block progression if payments incomplete (currently implemented as a stub — the actual gate logic is there but not enforcing hard blocks).

#### Meter Installation
DISCOM meter-related field work by the meter vendor.

Fields similar to Project Installation. Also has `actual_installation_date` used as ToDo due date.

#### Meter Commissioning
DISCOM meter commissioning. Has `commissioning_date` for ToDo due dates.

**Special logic:** When Meter Commissioning is Approved:
- If Finance Type = "Self Finance": Intercepts normal chain to create "Collect Final Payment" Sales Manager ToDo instead of creating a VH ToDo immediately.
- If Finance Type = "Bank Loan": Defers VH ToDo creation to when Tranche 2 milestone is marked Paid on the Sales Order.

#### Verification Handover
Final customer handover. The only execution stage where **Sales Manager** (not Vendor Executive) executes; Vendor Head approves.

**Key Fields:** `assigned_internal_user`, `verification_date`, `dcr_certificate` (Attach), `warrenty_documents` (Attach), `s_and_d_final` (Attach), `customer_signature` (Attach Image), `handover_completed_on`, `customer_feedback`, `reviewer`, `reviewer_decision`, `closure_comments`.

**On Approval:** Updates Job File `custom_job_file_status` to "Completed".

---

### 5.2 Supporting DocTypes

#### Payment Milestone Template
Template for payment structures. Two built-in finance types.

**Fields:** `template_name`, `finance_type` (Select: Self Finance / Bank Loan), `payment_milestone` (child table → Payment Milestone)

Used to auto-populate the `custom_payment_plan` table on Sales Order when `custom_finance_type` is set.

#### DISCOM Master
India-specific: Electricity Distribution Company master. Used to track which DISCOM a customer's job belongs to for meter-related regulatory approvals.

**Key Features:**
- Full company details: address, nodal officer, contact info
- Technical specs: grid voltage, net metering, sanctioned load limits
- Tariff info: tariff order year, export/import rates, subsidy amounts
- `linked_customers` child table — automatically updated when Job File links to a DISCOM
- DISCOM Manager ToDo is triggered on Sales Order when DISCOM process needs to start
- When a customer row is marked "Completed" in `linked_customers` → auto-closes DISCOM Manager ToDos for that sales order

#### Procurement Consolidation
Aggregation DocType for bulk Purchase Order creation across multiple Material Requests.

**Fields:** `naming_series` (PROC-CONS-.YYYY.-), `posting_date`, `company`, `warehouse`, `status` (Draft/Partially Ordered/Ordered), `supplier_for_po`, `items` (child: Consolidated Procurement Item)

#### Procurement Shortage Log
Tracks BOM items that were reserved but couldn't be fulfilled from existing warehouse stock. Created automatically when Sales Order is submitted and stock is insufficient.

#### Stock Reservation Log
Tracks material reservations mapped to Sales Orders. States: Reserved → Consumed/Released.

#### Location Log
Standalone child table DocType for GPS location history. Used inside execution DocTypes.

#### Photo Log
Child table for photo attachments with categorization.

#### Discom Linked Customer
Child table for DISCOM Master's customer list. Fields: `customer`, `job_file`, `status`.

---

### 5.3 Child Table DocTypes

| DocType | Parent(s) | Purpose |
|---|---|---|
| `Supplier Territory Child Table` | Supplier | Territory assignments for vendor routing |
| `Payment Control Child Table` | Job File (removed) | Was payment control; removed via patch |
| `Job Execution Child Table` | Job File | Tracks execution doc states in a table |
| `Revisist Log Child Table` | Technical Survey | Log of revisit events |
| `Material Line Child Table` | Technical Survey | Additional material lines |
| `Consolidated Procurement Item` | Procurement Consolidation | Line items for bulk PO |
| `Sales Person Territory Child Table` | Sales Person | Territory assignments |
| `Tax Bifurcation Child Table` | Quotation, Sales Invoice | GST split: 70%@5% + 30%@18% |

---

## 6. Extended Standard ERPNext DocTypes (via Custom Fields)

### Lead
- `custom_assigned_technical_supplier` — Link to Supplier (technical vendor)
- `custom_assigned_meter_supplier` — Link to Supplier (meter vendor)  
- `custom_active_sales_manager` — Link to Sales Person (drives Job File ownership)
- `workflow_state` — Custom Lead workflow: Draft → Contacted → Qualified → Disqualified/Lost

**Automation on "Qualified":** Auto-creates Customer + Address from Lead fields, then creates Job File.

### Sales Order
- `custom_job_file` — Link to Job File
- `custom_technical_survey` — Link to Technical Survey (the BOM source)
- `custom_finance_type` — Link to Payment Milestone Template (Bank Loan / Self Finance)
- `custom_payment_plan` — Table of Payment Milestones (Advance/Tranche 1/Tranche 2/Final)
- `custom_bom_items` — Snapshot of BOM items from TS (for stock reservation)
- `custom_job_file_owner` — Resolved Sales Manager User
- `custom_quotation_source` — Source quotation name
- `custom_delivery_percent` — Delivery completion percentage (auto-updated from DNs)
- `custom_billing_percent` — Billing completion (from milestones)

**Automation on Submit:**
1. Auto-creates Material Request from Technical Survey BOM
2. Closes source Quotation ToDos
3. Creates Payment Milestone ToDos (one per milestone for Accounts Manager)
4. For Self Finance: creates "Collect Advance Payment" Sales Manager ToDo
5. Creates Stock Manager transfer ToDo (when Advance milestone is Paid for Bank Loan)

**Payment Milestone States:** Pending → Paid (manually updated by Sales Manager on SO)

### Quotation
- `custom_quotation_status` — Select: Draft / Advance Approved / Final Approved
- `custom_technical_survey` — Link to Technical Survey
- `custom_job_file` — Link to Job File
- `custom_next_followup_date` — Follow-up date
- `custom_followup_count` — Number of follow-ups done
- `custom_last_followup_date` — Last follow-up date
- `custom_customer_acceptance` — Yes/No acceptance
- `custom_tax_bifurcation` — Tax Bifurcation child table (auto-filled: 70%@5% + 30%@18%)
- `custom_quotation_stage` — Determines if item structure is locked on "Final Approved"

**Override:** `make_sales_order` is overridden to validate `custom_quotation_status == "Advance Approved"` before creating SO.

### Sales Invoice
- Items are replaced automatically on `before_insert` with a single saleable system item from the approved Technical Survey's `proposed_system_kw__tier`, at rate = Sales Order `grand_total`.
- Custom API `get_saleable_item_for_si()` is callable from client to preview this replacement.
- Tax bifurcation auto-filled on validate.

### Delivery Note
- `against_sales_order` — Standard field, used for phase-wise delivery tracking
- `populate_items_from_technical_survey` runs on `before_insert`: replaces items with **remaining** BOM items (survey qty minus already-submitted DNs for same SO). This enables partial/phased deliveries.
- `get_remaining_ts_items()` — Whitelisted API callable from client-side
- On submit: Closes Stock Manager ToDos, syncs SO delivery percent, triggers chain logic

### Material Request
- `custom_source_technical_survey` — Link/source TS
- `custom_source_sales_order` — Link to source SO
- `custom_source_customer` — Customer reference
- Title auto-set to `{customer_name} - {k_number} - Material Request` on insert

### Payment Entry
- `custom_quotation` — Optional link to source Quotation (for advance payment tracking)
- On submit: Closes "Create Payment Entry" Accounts Manager ToDos for the linked SO
- On cancel: Reopens those ToDos

### Supplier
- Vendor territory assignment via `Supplier Territory Child Table`
- Vendor portal user creation via `api/supplier_portal.py`

---

## 7. Workflow System

All 6 execution DocTypes have their own Frappe Workflow (defined in fixtures/workflow.json). The workflows are all active and follow this general pattern:

### Execution DocType Generic Workflow States
```
Draft
 → Assigned to Vendor        (Vendor Head triggers — creates Vendor Manager ToDos)
 → In Progress               (Vendor Manager starts — creates Vendor Executive ToDos)
 → Submitted                 (Vendor Executive completes — creates Vendor Manager ToDos for review)
 → Completed / Ready for Review  (Vendor Manager approves — creates Vendor Head ToDos for approval)
 → Approved                  (Vendor Head approves — creates chain ToDos for next stage)
 → Rejected                  (back to Vendor Executive)
 → On Hold
```

### Verification Handover Workflow Difference
VH uses **Sales Manager** for execution (not Vendor Executive). Internal user picks up the job, drives to site, collects customer signature, uploads documents. Vendor Head approves.

### Job File Workflow States
```
Draft → In Progress → Approval Pending → Job File Initiated
```

### Lead Workflow States
```
Draft → Contacted → Qualified → Disqualified / Lost
```

### Quotation Workflow
No formal Frappe Workflow — uses custom `custom_quotation_status` field managed by JS client + server logic.

---

## 8. ToDo Automation System (The Most Complex Part)

This is the backbone of task management in Kaiten ERP. Every workflow transition generates, routes, and closes ToDos with strict role targeting, deduplication, and due dates.

### Core Rules (enforced everywhere)
1. **Always check for duplicate** before inserting — uses `frappe.db.exists()` with `description LIKE` filter
2. **Always set `role` field** on every ToDo — used by `todo_permission_query` to isolate visibility
3. **Always resolve `allocated_to`** to an enabled User via `frappe.db.get_value("User", user, "enabled")`
4. **Close role's old ToDos** before creating new ones — uses `close_open_todos_by_role()` with JOIN on `Has Role`

### ToDo Flow for a Job (chronological order)

| Event | ToDo Created For | Role | Reference |
|---|---|---|---|
| Job File → Approval Pending | Execution Manager users | - | Job File |
| Job File → Job File Initiated | Job File Owner (Sales Manager) | Sales Manager | Opportunity (prepare quotation) |
| Lead Qualified (auto) | Sales Manager | - | Job File |  
| Technical Survey → Assigned to Vendor | Vendor Manager users (territory-filtered) | Vendor Manager | Technical Survey |
| Technical Survey → In Progress | Vendor Executive users (vendor-filtered) | Vendor Executive | Technical Survey |
| Technical Survey → Submitted | Vendor Manager users | Vendor Manager | Technical Survey |
| Technical Survey → Completed | Vendor Head users | Vendor Head | Technical Survey |
| Technical Survey → Approved | Sales Manager (Job File owner) | Sales Manager | Quotation (prepare final quotation) |
| Quotation (draft saves) | Sales Manager | Sales Manager | Quotation (follow-up) — rescheduled on date change |
| Sales Order submit | Accounts Manager (per milestone) | Accounts Manager | Sales Order (Create Payment Entry for X) |
| Sales Order submit (Self Finance) | Job File Owner (Sales Manager) | Sales Manager | Sales Order (Collect Advance Payment) |
| Sales Order submit (Bank Loan Advance Paid) | Stock Manager | Stock Manager | Material Request (Transfer Materials to Site) |
| Structure Mounting → Approved | Sales Manager (Job File Owner + SO submitter) | Sales Manager | Sales Order (Collect Structure Payment) |
| Structure Mounting → Approved | (conditional, see below) | Vendor Head | Project Installation (Initiate PI) |
| Project Installation → Approved | Vendor Head users | Vendor Head | Meter Installation (Initiate MI) |
| Meter Installation → Approved | Vendor Head users | Vendor Head | Meter Commissioning (Initiate MC) |
| Meter Commissioning → Approved (Bank Loan) | Sales Manager (Job File Owner) | Sales Manager | Sales Order (Followup for Tranche 2) |
| Tranche 2 Paid (Bank Loan) | Vendor Head users | Vendor Head | Verification Handover (Initiate VH) |
| Meter Commissioning → Approved (Self Finance) | Sales Manager | Sales Manager | VH (Collect Final Payment — skip VH ToDo until paid) |
| Payment Entry submit | (closes PE ToDo) | Accounts Manager | Sales Order |
| Delivery Note submit | (closes Stock Manager ToDo) | Stock Manager | Material Request |
| DISCOM Process (on SO) | DISCOM Manager | DISCOM Manager | DISCOM Master |
| DISCOM linked customer → Completed | (closes DISCOM Manager ToDo) | DISCOM Manager | DISCOM Master |

### Structure Mounting → Project Installation Gate
This is the most complex gating rule:
- After SM is Approved, PI ToDo for Vendor Head is **only created** if the "Structure" payment milestone on the Sales Order is already "Paid"
- If not yet paid: the PI ToDo creation is deferred
- When Structure payment is later marked Paid on SO → `_sf_check_delivery_after_structure_paid()` triggers and creates the PI ToDo at that point (triggered by `on_update_after_submit` on Sales Order)

### Self Finance vs Bank Loan Payment Gates

**Bank Loan flow:**
- Advance Payment → Material Transfer → Delivery → Structure Payment → PI → MI → MC → Tranche 2 → VH → Final Payment

**Self Finance flow:**
- Advance → Material Transfer → Delivery → (no structure gate) → PI → MI → MC → Collect Final Payment → VH → Close

---

## 9. Permissions Layer

Two-layer permission system implemented for all custom DocTypes:

### Layer 1: `permission_query_conditions` (List View filtering)
Registered in `hooks.py` for: Technical Survey, Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover, Job File, ToDo, DISCOM Master.

Vendor users (Vendor Manager, Vendor Executive, Vendor Head) see only documents belonging to their supplier company. Implemented via `Contact → Dynamic Link → Supplier` lookup, then filtering docs by `assigned_vendor = supplier_name`.

### Layer 2: `has_permission` (Per-Document Check)
Same DocType list. Returns `True`/`False`/`None` (None = fall through to Frappe default).

- **System Manager / Administrator / Execution Manager:** Full access always
- **Sales Manager:** Only Job Files where they are the assigned sales manager for the linked Lead
- **Vendor users:** Only docs belonging to their linked Supplier
- **ToDo:** Users see only their own ToDos (`allocated_to = user`) unless privileged

### Vendor-Supplier Linking
Users are linked to Suppliers via: `Contact.user = user` + `Dynamic Link(parenttype=Contact, link_doctype=Supplier, link_name=supplier)`. The `get_user_supplier()` and `get_supplier_users()` utilities in `vendor_permissions.py` handle this lookup.

---

## 10. BOM & Materials System

### Technical Survey as the BOM Source
The Technical Survey is the "single source of truth" for materials. Once approved:
- `proposed_system_kw__tier` = the saleable product (e.g., "5kW Tier-2 System")
- `bom_reference` = the ERPNext BOM for that product
- `panel`, `panel_qty_bom` = specific panel item chosen + qty
- `inverter`, `inverter_qty_bom` = specific inverter item + qty
- `battery` (optional)
- `table_vctx` = complete flattened BOM items list

### BOM Payload API (`technical_survey_bom.py`)
- `get_bom_payload(proposed_system_item_code)` — Explodes BOM, categorizes items into Panel/Inverter/Battery/Other, returns candidates with default selections
- Handles Phantom BOM expansion via `BOM Explosion Item` table (with manual recursion fallback)
- `get_items_with_bom(item_group)` — Filters items to only those with active BOMs (used in dropdowns on TS and SO)
- `get_bom_component_items(proposed_system, component_group)` — Returns valid panel/inverter items from the BOM of the selected system (BOM-restricted items for Domestic; all items by group for Commercial/Industrial)

### Material Request Auto-Creation
On Sales Order submit, a Material Request is created automatically from the TS BOM items. The MR carries:
- `custom_source_technical_survey` — TS reference
- `custom_source_sales_order` — SO reference  
- `custom_source_customer` — Customer reference
- Title = `{customer_name} - {k_number} - Material Request`

### Stock Reservation
On SO submit, `bom_stock_reservation.py` processes stock:
1. Checks available qty in warehouse for each BOM item
2. Creates `Stock Reservation Log` for available items
3. For shortage items, creates `Procurement Shortage Log` (MR creation is handled separately by `sales_order_events.on_submit`)

On SO cancel: all reservations released via `release_reservations_for_sales_order()`.

### Delivery Note Phase-wise Delivery
`populate_items_from_technical_survey` (before_insert hook):
- Computes survey qty for each item
- Subtracts already-submitted DN qty for same SO
- Only adds items with remaining qty > 0
- Enables partial deliveries across multiple DN documents

---

## 11. Financial System

### Payment Milestones
Two templates exist (Payment Milestone Template DocType):
- **Bank Loan:** Advance → Tranche 1 → Tranche 2 → Final
- **Self Finance:** Advance → Structure → Final

When `custom_finance_type` is set on Sales Order (client-side, `sales_order.js`), the `custom_payment_plan` child table is auto-populated from the template.

Milestone rows have: `milestone` (label), `payment_source`, `amount`, `stage`, `status` (Pending/Paid).

### Payment Milestone → ToDo linkage
Each milestone row triggers an Accounts Manager ToDo: "Create Payment Entry for {milestone} | {SO name}".

When Payment Entry is submitted referencing the SO → the PE ToDo is auto-closed.
When PE is cancelled → the PE ToDo is auto-reopened.

### GST Tax Bifurcation
India-specific. `fill_tax_bifurcation()` in `doc_events/tax_bifurcation.py`:
- 70% of net total @5% GST → CGST 2.5% + SGST 2.5%
- 30% of net total @18% GST → CGST 9% + SGST 9%
- Auto-fills `custom_tax_bifurcation` child table on Quotation and Sales Invoice on validate

### Sales Invoice — Single Saleable Item Pattern
**Problem:** Sales Order has BOM component items for delivery tracking. But the Sales Invoice should show the customer a single line item (e.g., "5kW Solar System") at the full deal price.

**Solution:** On `before_insert` of Sales Invoice (when created from SO or DN), all items are replaced with the single `proposed_system_kw__tier` item from the approved TS, at rate = SO `grand_total`.

### Profitability Calculation
`api/profitability.py` contains `update_profitability(job_file_name)`:
- Fetches `net_total` from latest submitted Sales Order
- Fetches material cost = Σ (qty × valuation_rate from tabBin, fallback to `last_purchase_rate`)
- Calculates gross profit, profit %, cost %
- Written to Job File via `frappe.db.set_value`

Triggered on: Technical Survey Approved, Sales Order submit/cancel.

### Advance Payment Flow
`api/advance_payment.py` provides `create_advance_payment_entry()`:
- Creates Payment Entry linked to Sales Invoice
- Validates amount ≥ 0, ≤ outstanding, ≥ structured advance amount
- Logs audit trail

---

## 12. Supplier Portal & Vendor User Management

### Vendor User Creation (`api/supplier_portal.py`)
`create_vendor_portal_user()` — creates portal users for vendors:
1. Validates Supplier exists
2. Creates User (Website User type) with random password
3. Adds role (Vendor Manager or Vendor Executive)
4. Creates Contact linked to User
5. Creates Dynamic Link: Contact → Supplier
6. Sends welcome email (optional)

This Contact→DynamicLink chain is what makes the `get_user_supplier()` permission check work.

### Vendor Filtering
Technical and meter vendors are filtered by territory on the Job File form:
- `lead_vendor.py`: `get_technical_vendors(territory)` and `get_meter_vendors(territory)` query Supplier Territory Child Table for territory-matched vendors
- On Job File refresh, dropdown queries are set to filter by the job's territory
- Changing territory clears supplier selections

---

## 13. Mobile App Integration

### Mobile Workflow API (`api/mobile_workflow.py`)
Two whitelisted endpoints that expose the full Frappe workflow engine to mobile:

**`get_actions(doc_type, doc_name)`** → Returns available workflow transitions for the current user. Frappe's `get_transitions()` handles role filtering, condition scripts, and docstatus constraints natively.

**`apply_action(doc_type, doc_name, action, gps_latitude, gps_longitude)`** → Applies a workflow action. GPS coordinates are stamped on the document before `apply_workflow()` runs. The `log_workflow_location()` function in `gps.py` reads these and appends a Location Log row.

**GPS Location Logging (`api/gps.py`):**
- Runs inside `validate()` during workflow transitions
- Compares DB state vs in-memory to detect actual transitions
- Appends Location Log row: timestamp, previous_status, new_status, lat, lon, changed_by
- Clears `gps_latitude`/`gps_longitude` temp fields after logging
- Never blocks a workflow even if GPS is absent

### Pincode Lookup API (`api/pincode.py`)
`get_pincode_details(pincode)` — Calls India Post API (`api.postalpincode.in`) to auto-fill city + state from a 6-digit PIN code. Used on Lead and Job File forms.

---

## 14. Client-Side JavaScript (per DocType)

| File | Key Functionality |
|---|---|
| `JobFile.js` | Territory-based vendor field filtering, query overrides for supplier dropdowns |
| `technical_survey.js` | BOM auto-load, system config lock when Approved, tilt auto-calc, custom assignment dialog filtered to vendor's users |
| `sales_order.js` | Finance type → auto-populate payment milestone rows from template |
| `quotation.js` | Follow-up date, customer acceptance sync, profitability display |
| `project_installation.js` | Phase-wise delivery button |
| `meter_installation.js` / `meter_commissioning.js` / `structure_mounting.js` | Workflow action buttons, GPS capture |
| `verification_handover.js` | Document upload prompts, customer signature capture |
| `delivery_note.js` | Load remaining TS items button |
| `sales_invoice.js` | Saleable item preview, milestone billing |
| `lead.js` | Vendor assignment, Active Sales Manager picker |
| `material_request.js` | Source SO/TS display |
| `opportunity.js` | Link to Job File/TS |
| `supplier.js` | Territory assignment UI |
| `desk_override.js` | Replaces Frappe loading screen logo with Kaiten logo |
| `location_tracker.js` | GPS utilities shared across execution forms |

---

## 15. DISCOM Integration

DISCOM (Distribution Company) Master is an India-specific DocType for electricity utility companies. Key features:

- Full DISCOM profile: company type, regulatory body, nodal officer, technical specs, tariff data
- `linked_customers` child table auto-managed: when Job File is saved with a discom, customer is added; when DISCOM changes, old DISCOM entry is removed and new one added; on trash, entry removed
- On Sales Order `on_update_after_submit`: when a DISCOM-related milestone triggers, a DISCOM Manager ToDo is created referencing the DISCOM Master document
- When DISCOM Manager marks a customer row as "Completed" in DISCOM Master → auto-closes that job's DISCOM Manager ToDo via `discom_master_events.on_update`

---

## 16. Scheduler

One scheduled task:
```python
# cron: 0 9,12,15,18,21 * * *  (5x daily: 9am, 12pm, 3pm, 6pm, 9pm)
kaiten_erp.kaiten_erp.cron_job.hourly_backup.take_full_backup
```
Takes a full database backup at each interval.

---

## 17. Custom Roles

| Role | Purpose |
|---|---|
| `Vendor Manager` | Mid-tier field supervisor for a vendor company. Assigns work to Vendor Executives, reviews their submissions |
| `Vendor Executive` | Field technician. Executes site work (surveys, installation) |
| `Vendor Head` | Senior vendor company representative. Approves completed work |
| `Sales Executive` | Internal sales staff (limited use in current build) |
| `DISCOM Manager` | Internal staff handling DISCOM applications and regulatory approvals |
| `Sales Manager` | Internal sales manager who owns jobs and follows up on payments |
| `Execution Manager` | Internal project manager who approves Job Files |
| `Accounts Manager` | Accounting staff who create Payment Entries |
| `Stock Manager` | Warehouse staff who process material transfers |

---

## 18. Patch History (What Changed Over Time)

The 32 patches reveal the project's evolution:

### Schema Cleanup Patches
- `remove_sales_order_invoice_fields` — Removed direct invoice tracking from SO
- `remove_sales_order_custom_fields` — Cleaned up early SO customizations
- `remove_job_file_payment_control_tab` — Payment Control tab was removed (became Payment Milestones)
- `remove_job_file_commercial_qualification_fields` — Commercial fields removed from Job File
- `remove_hybrid_from_job_file_finance_type` — "Hybrid" finance type removed; only Self Finance + Bank Loan remain
- `remove_meter_commissioning_prv_test_report_field` — Previous test report field removed from MC
- `remove_verification_handover_verification_section` — Verification section restructured
- `remove_meter_installation_location_log_field` — Location log moved to child table format
- `remove_tax_biffurication_fields` — Old tax bifurcation fields removed (replaced by a proper child table)

### Business Logic Evolution Patches
- `migrate_dn_linked_sales_order` — Fixed legacy DN→SO linkage (migrated data to new field)
- `cleanup_job_file_payment_tab_and_fix_meter_type` — Consolidated payment UI + fixed meter data
- `change_sales_order_finance_type_to_link` — Finance type changed from Select to Link (to Payment Milestone Template) — major evolution from hardcoded to configurable milestones
- `replace_customer_handover_with_dcr_certificate` — VH field renamed to DCR Certificate (regulatory doc)
- `rename_self_funding_to_self_finance` — Terminology standardized

### Feature Addition Patches
- `add_execution_workspaces` — Added custom Frappe Desk workspaces for execution team
- `add_job_file_desk_icon` — Added Job File to desk shortcuts
- `add_job_file_to_crm_sidebar` — Job File surfaced in CRM sidebar
- `create_payment_milestone_todos` — Backfilled ToDos for existing Sales Orders
- `backfill_material_request_titles` — Applied new title format to existing MRs
- `update_discom_master_select_options` — Added states to DISCOM dropdown

### UI/Field Fixes
- `fix_property_setter_field_orders` — Corrected field ordering in DocType forms
- `fix_technical_survey_roof_type_and_add_distance` — TS roof type options + distance field
- `set_roof_type_select_options` — Expanded roof type choices
- `rename_job_file_monthly_consumption_label` — Label clarification
- `change_job_file_monthly_bill_to_currency` — Field type corrected to Currency
- `rename_handover_label_and_unhide_meter_tab` — VH form improvements
- `add_meter_commissioning_sync_options` — MC sync field options added
- `set_technical_survey_visit_type_select` / `set_visit_type_select_with_default` — TS visit type formalized
- `quotation_allow_on_submit_and_move_profitability_tab` — Quotation form restructured
- `rename_property_photo_label` — Photo field label fix
- `update_workflow_roles` — Workflow transition roles updated

---

## 19. Key Challenges Solved

### 1. Deferred ToDo Creation (Payment-Gated Chain)
**Problem:** Structure Mounting Approved should trigger Project Installation ToDo, but only after the Structure payment is received. Meter Commissioning Approved should trigger Verification Handover ToDo, but differently for Bank Loan vs Self Finance.

**Solution:** In `execution_chain_todo.py`, `on_update()` checks payment status before creating the next ToDo. `_sf_intercept_mc_approved()` handles Self Finance. The deferred piece is picked up by `sales_order_events.on_update_after_submit` checking milestone status changes.

### 2. ToDo Deduplication
**Problem:** Multiple doc saves can trigger the same ToDo creation multiple times.

**Solution:** Every `frappe.db.exists("ToDo", {...})` call includes `"description": ["like", "%keyword%"]`, `role`, `reference_type`, `reference_name`, and `status: "Open"` to ensure exact dedup.

### 3. System Configuration Lock After TS Approval
**Problem:** After Technical Survey is Approved and BOM submitted, field staff shouldn't be able to change panel/inverter quantities (they're already ordered).

**Solution:** Server-side `_guard_approved_system_config()` in `technical_survey_events.py` throws a ValidationError if any locked field changes. Client-side `lock_system_config_if_approved()` sets `read_only=1` on all config fields.

### 4. Sales Invoice Item Replacement
**Problem:** SO has component items (panels, inverter, cable, etc.) but SI must show a single line: "5kW Solar System — ₹3,20,000".

**Solution:** `sales_invoice_events.py` intercepts `before_insert`, finds the approved TS's `proposed_system_kw__tier`, builds a single row at `grand_total` rate, replaces `doc.items` entirely. Client API `get_saleable_item_for_si()` allows the form to preview this before save.

### 5. Vendor Permission Isolation
**Problem:** Vendor users from company A must not see documents belonging to vendor company B.

**Solution:** Two-layer approach:
- List view: SQL filter `assigned_vendor = (contact → dynamic_link → supplier for current user)`
- Form view: `has_permission()` re-runs supplier lookup and compares

### 6. Phase-wise Delivery
**Problem:** All BOM materials may not be available in one shipment. Need multiple partial DNs to same SO.

**Solution:** `populate_items_from_technical_survey()` calculates remaining qty (survey qty − sum of submitted DNs) and only adds items with remaining > 0.

### 7. Stale `multiline` Select Field Values
**Problem:** After a Select field's options list was changed, some records had stored all-options-as-one-string as the field value.

**Solution:** `_normalize_select_value()` in `JobFile_events.py` parses the stored value, tries to find a valid single option from the options list, and returns it.

### 8. BOM Access for Vendor Users
**Problem:** Vendor Manager/Executive roles lack BOM read access in ERPNext, but they need BOM data to populate panel/inverter dropdowns on Technical Survey.

**Solution:** `technical_survey_bom.py` uses `ignore_permissions=True` on BOM-related queries since this data is non-sensitive component information.

### 9. Self Finance vs Bank Loan Flow Divergence
**Problem:** Two completely different payment sequences depending on how the customer finances their system.

**Solution:** Helper functions `_is_bank_loan(doc)`, `_is_self_finance(doc)` throughout `sales_order_events.py`. Each milestone trigger function checks finance type before acting.

### 10. ToDo Visibility Isolation
**Problem:** All users were seeing all ToDos in the ToDo list, including those allocated to others.

**Solution:** Custom `todo_permission_query` returns SQL condition `allocated_to = '{user}'` for non-privileged users. Custom `todo_has_permission` checks `doc.allocated_to == user`. Both registered in `hooks.py`.

---

## 20. Known Incomplete / Stub Areas

### `execution_payment_validation.py`
`validate_installation_payment()` and `validate_verification_payment()` have the structure (resolving linked SO, fetching milestone data) but the actual blocking logic is commented out / empty. These functions currently just return without enforcing any gate. This is a **known incomplete feature** — payment gating is done primarily via ToDo orchestration rather than hard validation blocks.

### `milestone_invoice_manager.py`
This file is completely empty. The intent was to manage milestone-based SI creation automatically, but it was never implemented. SI creation is currently manual (Accounts team creates from SO after ToDonotification).

### `execution_actions.py`
Contains the `STATUS_TRANSITIONS` map and role permission check functions, but these aren't actively used by the live workflow (the Frappe native workflow handles transitions). This file appears to be from an earlier architectural approach before the Frappe workflow was adopted.

### `advance_payment.py`
Creates advance Payment Entries linked to Sales Invoice. The flow of creating a Sales Invoice first and then advance PE is implemented, but the end-to-end client-side dialog that calls this isn't present in the current JS files (may be in a removed/unreferenced script).

### `create_milestone_items.py`
One-time setup script with `frappe.init(site="dev2.localhost")` hardcoded. Run manually to create Payment Item masters. Not a runtime feature.

---

## 21. Fixtures System

All UI customizations are exported to `kaiten_erp/fixtures/` as JSON:

| File | Contains |
|---|---|
| `custom_field.json` | All custom fields on standard ERPNext DocTypes (module = "Kaiten Erp") |
| `doctype.json` | All custom DocType definitions |
| `property_setter.json` | Field order, read-only, hidden, required overrides on all DocTypes |
| `workflow.json` | All active Frappe Workflows |
| `workflow_state.json` | All workflow states |
| `workflow_action.json` | All workflow action names |
| `custom_docperm.json` | Custom permission rules |
| `role.json` | Custom roles (Vendor Manager, Vendor Executive, Vendor Head, Sales Executive, DISCOM Manager) |
| `server_script.json` | Server scripts created from UI (if any) |
| `client_script.json` | Client scripts created from UI (if any) |

Export command: `bench export-fixtures` (run from app directory after any UI changes)

---

## 22. Current Development State

### What is fully built and operational:
- Complete Lead → Job File → Execution chain creation automation
- All 6 execution DocType workflows with role-targeted ToDos
- Vendor permission isolation (list + form level)
- Technical Survey BOM system with lock after approval
- Sales Order + Material Request automation from TS BOM
- Phase-wise Delivery Note from TS BOM
- Sales Invoice single-item replacement
- Tax bifurcation (GST 70%@5% + 30%@18%)
- Payment Milestone ToDo system
- Payment Entry → ToDo auto-close/reopen
- DISCOM Master + customer sync
- Self Finance vs Bank Loan payment flow differentiation
- Profitability calculation on Job File
- Supplier portal user creation
- Mobile workflow API (get_actions + apply_action)
- GPS location logging in execution DocTypes
- Pincode auto-lookup
- Desk branding (Kaiten logo)
- 32 migration patches for clean data evolution

### What is stubbed / incomplete:
- `execution_payment_validation.py` — hard payment gates not enforced
- `milestone_invoice_manager.py` — empty, SI creation is manual
- Some JS action buttons in execution forms may reference APIs that weren't fully wired

### Architecture decisions still in flux (based on patch history):
- Finance type field: went from Select → Link (to support configurable templates)
- Payment control: went from a job file tab → dedicated milestone rows on SO
- Tax bifurcation: went from individual fields → a proper child table
- Delivery Note: evolved to phase-wise (remaining qty logic)

---

## 23. Data Flow Summary

```
1. INCOMING LEAD
   Sales Manager gets Lead → contacts customer → moves to "Contacted" 
   → qualifies → Lead → "Qualified"
   
2. JOB CREATION (automated)
   Lead "Qualified" → Customer auto-created
                    → Job File created (with electrical/location snapshot from Lead)

3. JOB ASSIGNMENT
   Job File: set territory, select technical vendor + meter vendor
   → Submit to "Approval Pending"
   → Execution Manager reviews → approves → "Job File Initiated"
   → ALL 6 execution docs + Opportunity created in one transaction

4. PRESALES
   Opportunity → SM prepares Quotation
   Quotation → follow-up ToDos → customer accepts
   → Quotation "Advance Approved"
   
5. FIELD SURVEY (Technical Survey)
   Technical Survey "Assigned to Vendor" → Vendor Manager assigns Vendor Executive
   → Vendor Executive arrives on site (mobile GPS logged)
   → Fills site data, selects system, fills BOM
   → "Submitted" → Vendor Manager reviews → "Completed" → Vendor Head approves
   → "Approved" → BOM LOCKED → Quotation finalized → SO creation enabled

6. SALES ORDER CREATION
   Quotation "Advance Approved" + customer pays advance
   → Sales Order created from Quotation (override validates advance approval)
   → Payment milestones populated from template
   → Material Request auto-created from TS BOM
   → Stock reservation processed

7. MATERIALS & DELIVERY
   Procurement team raises PO / processes MR
   Stock Manager: Material Transfer to site → closes MR transfer ToDo
   Delivery Note: remaining BOM items (phase-wise) → closes stock ToDo
   
8. STRUCTURE MOUNTING (execution stage)
   Vendor Head assigns → Vendor Manager dispatches team → Vendor Executive installs
   → Approved → "Collect Structure Payment" Sales Manager ToDo
   → Structure payment received → PI ToDo for Vendor Head

9-10. PROJECT + METER INSTALLATION
   Same vendor workflow pattern
   Progress ToDos created at each approval

11. METER COMMISSIONING
   Same pattern
   → Approved → triggers Tranche 2 followup ToDo (Bank Loan) OR Final Payment ToDo (Self Finance)
   → After Tranche 2 paid → VH ToDo for Vendor Head

12. VERIFICATION HANDOVER
   Sales Manager (Assigned Internal User) goes to site
   Collects customer signature, DCR certificate, warranty docs
   → Vendor Head approves
   → Job File set to "Completed"
   
13. BILLING
   Accounts Manager creates Sales Invoice for each payment milestone
   (SI auto-replaces items with single saleable system item)
   Payment Entry created → closes PE ToDo
```

---

## 24. File Reference Index

### API Files (`kaiten_erp/kaiten_erp/api/`)
| File | Status | Purpose |
|---|---|---|
| `execution_actions.py` | Legacy/minimal | Status transition map, role permission checks (not actively used by live workflow) |
| `execution_chain_todo.py` | Active | ToDo creation when execution stage is Approved (chain progression) |
| `execution_payment_validation.py` | Stub | Payment gate validators (currently no-ops) |
| `execution_workflow.py` | Active | Stage ordering, admin bypass, advance payment checking helpers |
| `job_file_workflow.py` | Active | Manual trigger for Execution Manager ToDo assignment (utility/debug) |
| `bom_stock_reservation.py` | Active | SO submit/cancel stock reservation logic |
| `profitability.py` | Active | Job File profitability recalculation |
| `sales_order_bom.py` | Active | Full SO creation from Quotation with TS BOM integration |
| `milestone_invoice_manager.py` | Empty | Planned milestone SI manager |
| `gps.py` | Active | GPS location logging on workflow transitions |
| `supplier_portal.py` | Active | Vendor portal user creation |
| `technical_survey_bom.py` | Active | BOM explosion, item filtering for TS dropdowns |
| `lead_vendor.py` | Active | Territory-filtered vendor queries |
| `mobile_workflow.py` | Active | REST API for mobile workflow actions |
| `advance_payment.py` | Active | Advance Payment Entry creation |
| `pincode.py` | Active | India Post pincode lookup |
| `quotation_workflow.py` | Utility | Quotation workflow helpers |
| `material_request_validation.py` | Active | MR validation utils |
| `assignment_filter.py` | Active | User assignment filters |
| `get_vendorExcutive.py` | Active | Vendor Executive lookup |
| `technical_survey.py` | Active | TS-specific utilities |
| `supplier_query.py` | Active | Supplier search queries |
| `purchase_gst_hook.py` | Active | GST hooks on purchase documents |
| `setup_milestone_fields.py` | Utility | One-time milestone field setup |
| `milestone_custom_fields.py` | Utility | Custom field definitions for milestones |
| `create_milestone_items.py` | Setup | One-time Item master creation script |

### Doc Events Files
| File | DocType(s) |
|---|---|
| `JobFile_events.py` | Job File |
| `lead_events.py` | Lead |
| `lead_validation.py` | Lead (sub-validation) |
| `technical_survey_events.py` | Technical Survey + shared helpers for all execution DocTypes |
| `execution_events.py` | Structure Mounting, Project Installation, Meter Installation, Meter Commissioning, Verification Handover |
| `project_installation_events.py` | Project Installation (structure data populate) |
| `quotation_events.py` | Quotation |
| `sales_order_events.py` | Sales Order (most complex file — all payment milestone logic) |
| `sales_invoice_events.py` | Sales Invoice |
| `delivery_note_events.py` | Delivery Note |
| `material_request_events.py` | Material Request |
| `stock_entry_events.py` | Stock Entry |
| `payment_entry_events.py` | Payment Entry |
| `discom_master_events.py` | DISCOM Master |
| `tax_bifurcation.py` | Shared (Quotation + SI) |
| `test.py` | Debug/test utilities |

---

## 25. Naming Conventions & Known Field Name Quirks

Several field names in the codebase use Frappe's auto-generated cryptic names from form builder (random suffixes). This is a legacy of fields created in the UI before being moved to JSON:

- `data_ycke` = Technical Survey "Scheduled Date"
- `data_tila` = Technical Survey "Schedule Slot"  
- `data_zxjn` = Technical Survey "Actual Start Date"
- `data_xwsx` = Technical Survey "Completion Date"
- `data_mrku` = Technical Survey (some revisit date field)
- `table_vctx` = Technical Survey "BOM Items" child table
- `proposed_system_kw__tier` = Technical Survey "Proposed System (kW / Tier)"
- `phase_type_copy` = Technical Survey copy of phase type from Job File
- `city__district` = Project Installation, Meter Installation, VH "City / District"
- `strucutre_height` = Structure Mounting (note: typo in field name — "structure" not "strucutre")

Custom fields on standard DocTypes always carry `custom_` prefix:
- `custom_job_file`, `custom_technical_survey`, `custom_finance_type`, etc.

---

## 26. Bench & Deployment Context

- **Bench root:** `/home/vaibhav/frappe/frappe-bench`
- **App dir:** `/home/vaibhav/frappe/frappe-bench/apps/kaiten_erp`
- **Site name:** `dev-bench`
- **App includes globally:** `desk_override.js` (logo), `quick_hide.css`

### Standard workflow after any change:
```bash
cd /home/vaibhav/frappe/frappe-bench
bench migrate
bench --site dev-bench clear-cache
# If DocType/Custom Field/Workflow changed in UI:
cd apps/kaiten_erp && bench export-fixtures
```

---

*This document was auto-generated from codebase exploration on 2026-04-18.*
