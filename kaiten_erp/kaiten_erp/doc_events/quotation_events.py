# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def validate(doc, method=None):
    _sync_links_from_opportunity(doc)

    if doc.get("custom_quotation_stage") == "Final Approved":
        _validate_final_approved_requirements(doc)
        _ensure_single_commercial_item(doc)
        _lock_final_approved_item_structure(doc)


def _sync_links_from_opportunity(doc):
    if not doc.opportunity:
        return

    opportunity = frappe.db.get_value(
        "Opportunity",
        doc.opportunity,
        ["custom_job_file"],
        as_dict=True,
    )

    if opportunity and opportunity.get("custom_job_file") and not doc.get("custom_job_file"):
        doc.custom_job_file = opportunity.custom_job_file

    if hasattr(doc, "custom_opportunity_link"):
        doc.custom_opportunity_link = doc.opportunity


def _validate_final_approved_requirements(doc):
    if not doc.opportunity:
        frappe.throw(_("Final Approved Quotation must be linked to an Opportunity."))

    if not doc.get("custom_technical_survey"):
        frappe.throw(
            _("Approved Technical Survey is mandatory for Final Approved Quotation.")
        )

    technical_survey = frappe.get_doc("Technical Survey", doc.custom_technical_survey)

    if technical_survey.get("workflow_state") != "Approved":
        frappe.throw(
            _("Technical Survey {0} must be in Approved state.").format(
                technical_survey.name
            )
        )

    if not technical_survey.get("custom_opportunity"):
        frappe.throw(
            _("Technical Survey {0} must be linked to an Opportunity.").format(
                technical_survey.name
            )
        )

    if technical_survey.custom_opportunity != doc.opportunity:
        frappe.throw(
            _(
                "Technical Survey {0} is linked to Opportunity {1}, not {2}."
            ).format(technical_survey.name, technical_survey.custom_opportunity, doc.opportunity)
        )

    if technical_survey.get("custom_job_file") and not doc.get("custom_job_file"):
        doc.custom_job_file = technical_survey.custom_job_file

    if technical_survey.get("customer") and doc.get("party_name"):
        if (
            doc.get("quotation_to") == "Customer"
            and technical_survey.customer != doc.party_name
        ):
            frappe.throw(
                _(
                    "Technical Survey customer {0} does not match Quotation customer {1}."
                ).format(technical_survey.customer, doc.party_name)
            )


def _ensure_single_commercial_item(doc):
    opportunity = frappe.db.get_value(
        "Opportunity",
        doc.opportunity,
        ["custom_proposed_system", "opportunity_amount"],
        as_dict=True,
    )

    proposed_system = (opportunity or {}).get("custom_proposed_system")
    if not proposed_system:
        frappe.throw(
            _("Opportunity {0} is missing Proposed System.").format(doc.opportunity)
        )

    if not doc.items:
        doc.append(
            "items",
            {
                "item_code": proposed_system,
                "qty": 1,
                "rate": (opportunity or {}).get("opportunity_amount") or 0,
            },
        )
        return

    if len(doc.items) != 1:
        frappe.throw(
            _(
                "Final Approved Quotation can contain only one commercial item (Proposed System)."
            )
        )

    item = doc.items[0]
    if item.item_code != proposed_system:
        frappe.throw(
            _(
                "Final Approved Quotation item must be the Opportunity Proposed System: {0}."
            ).format(proposed_system)
        )

    if not item.qty:
        item.qty = 1


def _lock_final_approved_item_structure(doc):
    if doc.is_new() or doc.amended_from:
        return

    previous_doc = doc.get_doc_before_save()
    if not previous_doc:
        return

    if previous_doc.get("custom_quotation_stage") != "Final Approved":
        return

    previous_items = previous_doc.get("items") or []
    current_items = doc.get("items") or []

    if len(previous_items) != len(current_items):
        frappe.throw(
            _(
                "Item add/remove is not allowed for Final Approved Quotation unless amended."
            )
        )

    for index, old_item in enumerate(previous_items):
        new_item = current_items[index]
        if (
            old_item.get("item_code") != new_item.get("item_code")
            or float(old_item.get("qty") or 0) != float(new_item.get("qty") or 0)
            or old_item.get("uom") != new_item.get("uom")
        ):
            frappe.throw(
                _(
                    "Item code, quantity, and UOM are locked for Final Approved Quotation unless amended."
                )
            )
