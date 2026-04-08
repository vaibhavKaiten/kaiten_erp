# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

from kaiten_erp.kaiten_erp.doc_events.tax_bifurcation import fill_tax_bifurcation


def validate(doc, method=None):
    _set_place_of_supply(doc)
    fill_tax_bifurcation(doc)


def _set_place_of_supply(doc):
    """Ensure place_of_supply is set before india_compliance GST validations run.

    india_compliance crashes with a TypeError if place_of_supply is None.
    Priority:
      1. india_compliance's own get_place_of_supply (uses customer address/GSTIN)
      2. Fallback: derive state from company_gstin (in-state supply assumption)
    """
    if doc.get("place_of_supply"):
        return

    # 1. Try india_compliance's own logic (uses customer address / GSTIN)
    try:
        from india_compliance.gst_india.utils import get_place_of_supply

        pos = get_place_of_supply(doc, "Sales Invoice")
        if pos:
            doc.place_of_supply = pos
            return
    except Exception:
        pass

    # 2. Fallback: derive from company GSTIN state code (first 2 digits)
    try:
        from india_compliance.gst_india.constants import STATE_NUMBERS

        company_gstin = doc.get("company_gstin") or ""
        if len(company_gstin) >= 2:
            state_code = company_gstin[:2]
            # STATE_NUMBERS is {state_name: code}, so invert it
            code_to_state = {v: k for k, v in STATE_NUMBERS.items()}
            state_name = code_to_state.get(state_code)
            if state_name:
                doc.place_of_supply = f"{state_code}-{state_name}"
    except Exception:
        pass
