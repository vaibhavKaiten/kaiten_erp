import json

import frappe
import requests
from frappe import _


def after_insert(doc, method):
    frappe.enqueue(
            "kaiten_erp.kaiten_erp.doc_events.whatsapp_queue_events._send_workflow_webhook",
            whatsapp_broadcast_queue_name=doc.name,
            queue="short",
    )

def _send_workflow_webhook(whatsapp_broadcast_queue_name):
    whatsapp_broadcast_queue = frappe.get_doc("Whatsapp Broadcast Queue", whatsapp_broadcast_queue_name)
    party_name = whatsapp_broadcast_queue.dynamic_link_uzxz
    first_name = ""
    mobile_no = ""

    if whatsapp_broadcast_queue.party == "Customer":
        customer = frappe.get_doc("Customer", party_name)
        first_name = customer.customer_name or ""
        contact = frappe.db.get_value(
            "Dynamic Link",
            {"link_doctype": "Customer", "link_name": party_name, "parenttype": "Contact"},
            "parent",
        )
        mobile_no = frappe.db.get_value("Contact", contact, "mobile_no") or "" if contact else ""

    elif whatsapp_broadcast_queue.party == "User":
        user = frappe.get_doc("User", party_name)
        first_name = user.full_name or ""
        mobile_no = user.mobile_no or ""

    elif whatsapp_broadcast_queue.party == "Lead":
        lead = frappe.get_doc("Lead", party_name)
        first_name = lead.first_name or ""
        mobile_no = lead.whatsapp_no or ""

    settings = frappe.get_single("Kaiten Erp Settings")
    account_sid = settings.twilio_account_sid
    auth_token = settings.get_password("twilio_auth_token")
    from_number = settings.twilio_from_number or "+919521373117"

    content_variables = {
        "name": first_name,
        "case_number": whatsapp_broadcast_queue.case_number or "",
        "ac_mgr_name": whatsapp_broadcast_queue.ac_mgr_name or "",
        "ac_mgr_number": whatsapp_broadcast_queue.ac_mgr_number or "",
    }

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {
        "To": f"whatsapp:{mobile_no}",
        "From": f"whatsapp:{from_number}",
        "ContentSid": "HX7aa6295c61bf05d4667db8cfdb26fcfc",
        "ContentVariables": json.dumps(content_variables),
    }

    try:
        requests.post(
            url,
            data=data,
            auth=(account_sid, auth_token),
            timeout=10,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Whatsapp Broadcast Queue Workflow Webhook Error")

