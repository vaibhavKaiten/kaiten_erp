# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
Auto-fill the Tax Bifurcation child table on Quotation / Sales Invoice.

Business rule (for CA audit):
  - 70 % of net total is taxed at 5 % GST  → CGST 2.5 % + SGST 2.5 %
  - 30 % of net total is taxed at 18 % GST → CGST 9 %   + SGST 9 %

Effective blended rate = 0.70 × 5 % + 0.30 × 18 % = 8.9 %
"""

from frappe.utils import flt

# (slab_pct, component_rate)  — component_rate = half the GST slab rate
_SLABS = [
    (70, 2.5),   # 5 % GST ÷ 2
    (30, 9.0),   # 18 % GST ÷ 2
]


def fill_tax_bifurcation(doc):
    """Rebuild `custom_tax_bifurcation` rows from the document's net total."""
    net_total = flt(doc.get("net_total"))
    if not net_total:
        doc.set("custom_tax_bifurcation", [])
        return

    doc.set("custom_tax_bifurcation", [])

    for category in ("CGST", "SGST"):
        for slab_pct, rate in _SLABS:
            base = flt(net_total * slab_pct / 100, 2)
            tax_amount = flt(base * rate / 100, 2)
            doc.append("custom_tax_bifurcation", {
                "total": base,
                "tax_category": category,
                "on_amount": str(slab_pct),
                "tax_": rate,
                "amount": tax_amount,
            })
