# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

from kaiten_erp.kaiten_erp.doc_events.tax_bifurcation import fill_tax_bifurcation


def validate(doc, method=None):
    _set_place_of_supply(doc)
    fill_tax_bifurcation(doc)


def _set_place_of_supply(doc):
    """Ensure place_of_supply is set before india_compliance GST validations run.

    india_compliance crashes with a TypeError if place_of_supply is None.
    We use india_compliance's own utility to derive it from the customer address,
    so the value is always consistent with what ERPNext expects.
    """
    if doc.get("place_of_supply"):
        return

    try:
        from india_compliance.gst_india.utils import get_place_of_supply

        pos = get_place_of_supply(doc, "Sales Invoice")
        if pos:
            doc.place_of_supply = pos
    except Exception:
        pass
