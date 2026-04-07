# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

from kaiten_erp.kaiten_erp.doc_events.tax_bifurcation import fill_tax_bifurcation


def validate(doc, method=None):
    fill_tax_bifurcation(doc)
