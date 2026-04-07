# India Compliance — GST, TDS, e-Invoice, e-Waybill

## Installation

```bash
bench get-app https://github.com/resilient-tech/india-compliance
bench --site {site} install-app india_compliance
bench --site {site} migrate
```

Requires ERPNext v14+. Check compatibility: `bench version`

---

## Initial GST Setup

### 1. Company Master
- Abbr: Short code used in naming series
- Country: India (mandatory)
- GSTIN: 15-character GST number
- Default GST category: Registered Regular

### 2. GST Settings (in India Compliance > GST Settings)
```
Company GSTIN: 22AAAAA0000A1Z5
e-Invoice Applicable from: [date]
e-Invoice Credentials: [API user/password from NIC portal]
e-Waybill Auto Generate: Enabled (for invoices > ₹50,000 inter-state)
```

### 3. HSN/SAC Setup
```python
# Add HSN Code to Item
frappe.db.set_value("Item", item_code, {
    "gst_hsn_code": "84713010",    # For computers
    "is_nil_exempt": 0,
    "is_non_gst": 0
})
```

Common HSN Codes:
- Software services: SAC 998314
- IT consulting: SAC 998313
- Trading goods: varies by category
- Manufacturing: 6-digit HSN

---

## Tax Templates

### IGST (Inter-state)
```
Account Head: IGST - {Company Abbr}
Rate: 18% (or 5%, 12%, 28% depending on HSN)
```

### CGST + SGST (Intra-state)
```
CGST Account: CGST - {Company Abbr}  @ 9%
SGST Account: SGST - {Company Abbr}  @ 9%
```

### Creating Sales Tax Template
```python
doc = frappe.get_doc({
    "doctype": "Sales Taxes and Charges Template",
    "title": "GST 18% - Intra State",
    "company": company,
    "taxes": [
        {
            "charge_type": "On Net Total",
            "account_head": f"CGST - {abbr}",
            "description": "CGST @ 9%",
            "rate": 9
        },
        {
            "charge_type": "On Net Total",
            "account_head": f"SGST - {abbr}",
            "description": "SGST @ 9%",
            "rate": 9
        }
    ]
})
doc.insert()
```

---

## Customer / Supplier GST Fields

```python
{
    "gstin": "29ABCDE1234F1ZX",     # 15-char GSTIN
    "gst_category": "Registered Regular",
    "pan": "ABCDE1234F",
    "tax_withholding_category": ""   # For TDS
}
```

**gst_category options:**
- `Registered Regular`
- `Registered Composition`
- `Unregistered`
- `SEZ`
- `Overseas`
- `UIN Holders`
- `Tax Deductor`
- `Input Service Distributor`

---

## Address GST Fields

Every billing/shipping address needs:
```python
{
    "gstin": "...",            # Location-specific GSTIN
    "gst_state": "Karnataka", # Indian state name
    "gst_state_number": "29"  # State code
}
```

---

## e-Invoice

Applicable for businesses with turnover > ₹5 Cr.

### Auto-generation on Sales Invoice submit
1. Enabled in GST Settings → e-Invoice
2. Invoice submitted → IRN generated automatically
3. QR code embedded in print format
4. Cancellation: must cancel e-Invoice within 24 hours, then cancel ERPNext doc

### Manual trigger
```python
from india_compliance.gst_india.utils.e_invoice import EInvoiceData
e_invoice = EInvoiceData(invoice_doc)
e_invoice.validate()
response = e_invoice.generate_irn()
```

---

## e-Waybill

Auto-generated when:
- Invoice value > ₹50,000
- Movement of goods (not services)
- Inter-state OR intra-state (if state mandates)

### Settings
```
GST Settings → e-Waybill → Auto Generate e-Waybill
Transporter GSTIN on Delivery Note
Vehicle Number field
```

---

## TDS (Tax Deducted at Source)

```python
frappe.get_doc({
    "doctype": "Tax Withholding Category",
    "name": "194C - Contractors",
    "rates": [{
        "from_date": "2024-04-01",
        "to_date": "2025-03-31",
        "tax_withholding_rate": 1,    # 1% for individuals
        "single_threshold": 30000,
        "cumulative_threshold": 100000
    }]
}).insert()
```

Apply on Supplier master: `tax_withholding_category: "194C - Contractors"`

---

## Mandatory Custom Fields for India Compliance

These are auto-added by india_compliance app. Verify after install:

**Sales Invoice:**
- `is_reverse_charge`: 0/1
- `is_export_with_gst`: 0/1
- `gst_transporter_id`

**Purchase Invoice:**
- `bill_no`: Supplier's invoice number (mandatory for ITC)
- `bill_date`
- `eligibility_for_itc`: "Input Tax Credit"/"Ineligible for ITC"/etc.

---

## GST Reports

Available after install:
- GSTR-1 (Outward Supplies)
- GSTR-2B (Inward Supplies)
- GSTR-3B (Monthly Summary)
- GSTR-9 (Annual Return)

Navigate to: India Compliance > GST Reports

---

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| GSTIN validation fails | Check 15-char format: 2-digit state + 10-char PAN + 1Z + checksum |
| e-Invoice auth error | Regenerate API credentials in NIC portal, update in GST Settings |
| HSN not found | Add HSN Code master in India Compliance > HSN Code |
| State mismatch on e-Waybill | Ensure billing address state matches GSTIN state code |
| TDS not deducting | Check threshold not crossed; check supplier tax_withholding_category |
