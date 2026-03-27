# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import json

import frappe


def execute():
    """
    Fix Property Setter records in the DB that were overriding DocField
    changes made by previous patches.  All three field_order setters were
    re-applied on every bench migrate, effectively undoing the field removals.

    Changes:
      1. Verification Handover field_order — remove verification section
         fields and replace customer_handover_form with dcr_certificate.
      2. Meter Commissioning field_order — remove prv__test_report and
         its orphaned column_break_qbog.
      3. Job File field_order — remove payment_control_tab and all its
         child fields.
      4. Delete two stale Verification Handover property setters that are
         no longer valid (customer_handover_form-label, installation_notes_section-hidden).

    Idempotent — safe to run multiple times.
    """

    # ── 1. Verification Handover field_order ──────────────────────────────
    vh_remove = {
        "installation_notes_section",
        "verification_reference_no",
        "column_break_axcy",
        "verification_notes",
        "column_break_oifu",
        "execution_remarks",
    }
    _update_field_order(
        ps_name="Verification Handover-main-field_order",
        remove=vh_remove,
        replace={"customer_handover_form": "dcr_certificate"},
    )

    # ── 2. Meter Commissioning field_order ────────────────────────────────
    _update_field_order(
        ps_name="Meter Commissioning-main-field_order",
        remove={"column_break_qbog", "prv__test_report"},
    )

    # ── 3. Job File field_order ────────────────────────────────────────────
    jf_remove = {
        "payment_control_tab",
        "payment_control_section",
        "advance_invoice_number",
        "advance_invoice_amount",
        "advance_paid_amount",
        "advance_outstanding_amount",
        "advance_invoice_status",
        "column_break_pc1",
        "advance_override_approved",
        "advance_override_remark",
        "column_break_pc2",
        "advance_override_approved_by",
        "advance_override_approved_on",
        "override_notification_sent",
    }
    _update_field_order(ps_name="Job File-main-field_order", remove=jf_remove)

    # ── 4. Delete stale Verification Handover property setters ────────────
    for stale_name in (
        "Verification Handover-customer_handover_form-label",
        "Verification Handover-installation_notes_section-hidden",
    ):
        if frappe.db.exists("Property Setter", stale_name):
            frappe.db.delete("Property Setter", {"name": stale_name})

    frappe.db.commit()

    for doctype in ("Verification Handover", "Meter Commissioning", "Job File"):
        frappe.clear_cache(doctype=doctype)


# ── helper ────────────────────────────────────────────────────────────────────


def _update_field_order(ps_name, remove, replace=None):
    """
    Load a field_order Property Setter, drop fields in `remove`, apply
    `replace` renames, and save it back — only if the record exists and
    actually needs changing.
    """
    if not frappe.db.exists("Property Setter", ps_name):
        return

    current_value = frappe.db.get_value("Property Setter", ps_name, "value")
    try:
        fields = json.loads(current_value)
    except (TypeError, ValueError):
        return

    new_fields = []
    changed = False
    for f in fields:
        if f in remove:
            changed = True
            continue
        if replace and f in replace:
            new_fields.append(replace[f])
            changed = True
        else:
            new_fields.append(f)

    if changed:
        frappe.db.set_value(
            "Property Setter", ps_name, "value", json.dumps(new_fields)
        )
