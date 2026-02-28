# Material Request from Technical Survey - Implementation Summary

## Overview
This implementation enables Material Requests to be created from Technical Survey System Configuration items when a Sales Order is submitted, making the Technical Survey the single source of truth for material procurement.

---

## What Was Implemented

### 1. **Custom Fields Created**

#### Sales Order
- `custom_technical_survey` (Link to Technical Survey)
  - Auto-populated when Sales Order is created
  - Read-only field
  - Links SO to the approved Technical Survey

#### Material Request
- `custom_source_technical_survey` (Link to Technical Survey)
- `custom_source_sales_order` (Link to Sales Order)
- `custom_source_customer` (Link to Customer)
  - All read-only fields for traceability

---

### 2. **Files Created/Modified**

#### New Files Created:
1. **[sales_order_events.py](../doc_events/sales_order_events.py)**
   - Auto-links Technical Survey to Sales Order on save
   - Uses 3-tier matching:
     - Exact customer match
     - Fuzzy customer match (handles "Customer Name None")
     - Lead name match

2. **[add_custom_fields.py](../fixtures/add_custom_fields.py)**
   - Script to add custom fields to database
   - Executed via: `bench --site localhost execute kaiten_erp.kaiten_erp.fixtures.add_custom_fields.add_custom_fields`

#### Files Modified:
1. **[hooks.py](../hooks.py)**
   - Added Sales Order event registration:
     ```python
     "Sales Order": {
         "validate": "kaiten_erp.kaiten_erp.doc_events.sales_order_events.validate",
         "on_submit": "kaiten_erp.kaiten_erp.api.bom_stock_reservation.on_sales_order_submit",
         "on_cancel": "kaiten_erp.kaiten_erp.api.bom_stock_reservation.on_sales_order_cancel",
     },
     ```

2. **[bom_stock_reservation.py](../api/bom_stock_reservation.py)**
   - Updated field references to match Kaiten ERP's Technical Survey structure:
     - `panel` (instead of `selected_panel`)
     - `panel_qty_bom` (instead of `panel_qty_from_bom`)
     - `inverter` / `inverter_qty_bom`
     - `battery` / `battery_qty_bom`
     - `table_vctx` child table (BOM Items)

---

## How It Works

### Complete Workflow:

```
1. Lead Created
   ↓
2. Technical Survey Performed
   ↓
3. System Configuration Modified
   - Component Selection:
     * Panel (+ quantity)
     * Inverter (+ quantity)
     * Battery (+ quantity)
   - BOM Items Table:
     * Shaddle, ACDB, Cables, etc.
   ↓
4. Technical Survey Approved
   ↓
5. Quotation Created from Opportunity
   ↓
6. Sales Order Created from Quotation
   ↓ [validate event]
   Auto-link Technical Survey to SO
   ↓
7. Sales Order Submitted
   ↓ [on_submit event]
   Material Request Created with:
   - Items from TS System Configuration
   - Modified quantities (Source of Truth)
   - Links to TS, SO, Customer
```

---

## Technical Survey System Configuration Structure

Your Technical Survey has these fields:

### Component Selection Section:
- `panel` (Data field - item code)
- `panel_qty_bom` (Data field - quantity)
- `inverter` (Data field - item code)
- `inverter_qty_bom` (Data field - quantity)
- `battery` (Data field - item code)
- `battery_qty_bom` (Data field - quantity)

### BOM Items Section:
- `table_vctx` (Child Table → BOM Item)
  - Contains editable list of all other BOM items
  - Fields: `item_code`, `item_name`, `qty`

---

## Material Request Creation Logic

When Sales Order is submitted, the system:

1. **Checks if Technical Survey is linked**
   - If YES → Use TS System Configuration (✅ Source of Truth)
   - If NO → Fallback to Phantom BOM explosion

2. **Fetches items from TS System Configuration:**
   - Panel (if `panel` field has value and `panel_qty_bom` > 0)
   - Inverter (if `inverter` field has value and `inverter_qty_bom` > 0)
   - Battery (if `battery` field has value and `battery_qty_bom` > 0)
   - All items from `table_vctx` child table (where `qty` > 0)

3. **Checks stock availability for each item:**
   - Fully available → Reserve stock
   - Shortage → Add to Material Request

4. **Creates Material Request:**
   - Type: "Material Transfer"
   - Items: Only shortage items with modified quantities from TS
   - Links: Technical Survey, Sales Order, Customer

---

## Example Scenario

### Technical Survey 03909:
```
Component Selection:
  Panel: Panel DCR Bi-Facial 600-WT (Qty: 1)
  Inverter: Invertor-Luminious (Qty: 1)
  Battery: None (Qty: 0)

BOM Items Table:
  Shaddle-16 MM (Qty: 2) ← Modified from standard BOM
  ACDB-Havells-32 AMP (Qty: 2) ← Modified from standard BOM
  DC Wire-Polycab-4 SQMM (Qty: 1)
  Cable Tray-41X41 MM (Qty: 1)
  ...
```

### When Sales Order is submitted:
**Material Request will contain:**
- Panel (Qty: 1)
- Inverter (Qty: 1)
- Shaddle (Qty: **2** ← From TS, not standard BOM)
- ACDB (Qty: **2** ← From TS, not standard BOM)
- DC Wire (Qty: 1)
- Cable Tray (Qty: 1)
- ...

---

## Document Connections

The system creates proper document links visible in the **Connections** tab:

```
Technical Survey ←→ Sales Order ←→ Material Request
```

**To check connections:**
1. Open Technical Survey → Connections tab → See linked Sales Orders
2. Open Sales Order → Connections tab → See linked Technical Survey & Material Requests
3. Open Material Request → See Source Technical Survey, Source Sales Order, Source Customer fields

---

## Testing the Implementation

### Test Case 1: New Sales Order with Approved TS

1. **Setup:**
   - Lead with Customer
   - Approved Technical Survey with modified quantities

2. **Steps:**
   - Create Sales Order for that Customer
   - Save → Check `custom_technical_survey` field is populated
   - Submit → Material Request created

3. **Expected Result:**
   - Material Request items match TS System Configuration
   - Modified quantities from TS are used
   - Links are visible in Connections tab

### Test Case 2: Sales Order without Technical Survey

1. **Setup:**
   - Lead without Technical Survey
   - Or Customer without Lead

2. **Steps:**
   - Create Sales Order
   - Save → Warning message about no TS found
   - Submit → Fallback to Phantom BOM

3. **Expected Result:**
   - Material Request uses standard Phantom BOM
   - No TS link in Material Request

---

## Key Benefits

✅ **Single Source of Truth:** Technical Survey System Configuration
✅ **Modified Quantities:** Technician can adjust quantities during survey
✅ **Automatic Linking:** No manual linking required
✅ **Traceability:** Full document chain via Connections tab
✅ **Fallback Safety:** Uses Phantom BOM if no TS linked
✅ **Flexible Matching:** Handles customer name variations

---

## Troubleshooting

### Issue: Sales Order not linking to Technical Survey

**Possible Causes:**
1. No Lead found for Customer
2. Technical Survey not in "Approved" status
3. Customer name mismatch between SO and Lead

**Solution:**
- Check Lead exists for Customer
- Verify TS workflow_state = "Approved"
- Check customer name matches (exact or fuzzy)

### Issue: Material Request using Phantom BOM instead of TS

**Cause:** Sales Order has no `custom_technical_survey` link

**Solution:**
- Check if linking logic ran during SO save
- Manually verify TS is approved
- Cancel and recreate Sales Order to trigger linking

### Issue: Material Request missing items

**Cause:** Items in TS System Configuration have zero quantity

**Solution:**
- Check `panel_qty_bom`, `inverter_qty_bom`, `battery_qty_bom` > 0
- Check items in `table_vctx` have `qty` > 0

---

## Files Reference

### Core Implementation Files:
```
kaiten_erp/kaiten_erp/
├── doc_events/
│   └── sales_order_events.py          ← NEW: TS linking logic
├── api/
│   └── bom_stock_reservation.py       ← MODIFIED: Field name updates
├── fixtures/
│   ├── custom_fields.py               ← NEW: Field definitions
│   └── add_custom_fields.py           ← NEW: Installation script
└── hooks.py                           ← MODIFIED: Event registration
```

---

## Summary

This implementation successfully replicates the Material Request from Technical Survey functionality from Kaiten Erp into Kaiten ERP. The key difference is the field naming convention in your Technical Survey doctype, which has been properly mapped.

**Status: ✅ Implementation Complete**

The system is now ready to use! Create a new Sales Order for a customer with an approved Technical Survey to test the functionality.
