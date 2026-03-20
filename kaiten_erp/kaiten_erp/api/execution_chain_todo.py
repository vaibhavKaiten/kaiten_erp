# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import nowdate

EXECUTION_CHAIN = {
    "Structure Mounting": "Project Installation",
    "Project Installation": "Meter Installation",
    "Meter Installation": "Meter Commissioning",
    "Meter Commissioning": "Verification Handover",
}

CHAIN_JOB_FILE_FIELD = {
    "Project Installation": "custom_project_installation",
    "Meter Installation": "custom_meter_installation",
    "Meter Commissioning": "custom_meter_commissioning",
    "Verification Handover": "custom_verification_handover",
}


def _get_workflow_state_field(doctype: str) -> str:
    try:
        fieldname = frappe.db.get_value(
            "Workflow",
            {"document_type": doctype, "is_active": 1},
            "workflow_state_field",
        )
        return fieldname or "workflow_state"
    except Exception:
        return "workflow_state"


def on_update(doc, method=None):
    # ---- CHECKPOINT 1: hook is firing ----
    print(
        f"on_update fired | doctype={doc.doctype} | name={doc.name}",
        "ExecChain DEBUG 1 – Hook Fired"
    )

    state_field = _get_workflow_state_field(doc.doctype)
    current_state = doc.get(state_field)

    # ---- CHECKPOINT 2: what is the state field and value? ----
    print(
        f"state_field={state_field} | current_state={current_state}",
        "ExecChain DEBUG 2 – State Field"
    )

    # Check if value changed
    try:
        changed = bool(doc.has_value_changed(state_field))
    except Exception as e:
        changed = True  # assume changed if we can't tell
        print(
            f"has_value_changed error: {e} – assuming changed=True",
            "ExecChain DEBUG 2b – has_value_changed"
        )

    # ---- CHECKPOINT 3: did the state change? ----
    print(
        f"state_field={state_field} | changed={changed} | value={current_state}",
        "ExecChain DEBUG 3 – Changed Check"
    )

    if not changed:
        print("STOPPING – state did not change", "ExecChain DEBUG 3 – STOP")
        return

    if current_state != "Approved":
        print(
            f"STOPPING – state is '{current_state}', not 'Approved'",
            "ExecChain DEBUG 3 – STOP"
        )
        return

    next_doctype = EXECUTION_CHAIN.get(doc.doctype)

    # ---- CHECKPOINT 4: is doctype in chain? ----
    print(
        f"next_doctype={next_doctype}",
        "ExecChain DEBUG 4 – Next Doctype"
    )

    if not next_doctype:
        return

    _create_vendor_head_todos(doc, next_doctype)


def _create_vendor_head_todos(doc, next_doctype):
    # ---- CHECKPOINT 5: entering todo creation ----
    print(
        f"Entered _create_vendor_head_todos | doc={doc.name} | next={next_doctype}",
        "ExecChain DEBUG 5 – Create Todos"
    )

    # Step 1: get job file name
    job_file_name = doc.get("job_file") or doc.get("custom_job_file")

    print(
        f"job_file_name={job_file_name} | doc.job_file={doc.get('job_file')} | doc.custom_job_file={doc.get('custom_job_file')}",
        "ExecChain DEBUG 6 – Job File Name"
    )

    if not job_file_name:
        # Last resort: dump all field values to find the job file field
        all_fields = {k: v for k, v in doc.as_dict().items() if v and "job" in str(k).lower()}
        print(
            f"STOPPING – no job_file found. Fields with 'job' in name: {all_fields}",
            "ExecChain DEBUG 6 – STOP No Job File"
        )
        return

    # Step 2: get next doc name from job file
    jf_field = CHAIN_JOB_FILE_FIELD[next_doctype]
    next_doc_name = frappe.db.get_value("Job File", job_file_name, jf_field)

    print(
        f"jf_field={jf_field} | next_doc_name={next_doc_name}",
        "ExecChain DEBUG 7 – Next Doc Name"
    )

    if not next_doc_name:
        print(
            f"STOPPING – Job File '{job_file_name}' has no value in '{jf_field}'",
            "ExecChain DEBUG 7 – STOP No Next Doc"
        )
        return

    # Step 3: customer from job file
    customer = frappe.db.get_value("Job File", job_file_name, "customer") or job_file_name

    # Step 4: get vendor heads
    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent as user"],
    )

    print(
        f"vendor_heads found: {vendor_heads}",
        "ExecChain DEBUG 8 – Vendor Heads"
    )

    if not vendor_heads:
        print(
            "STOPPING – no Vendor Head users found",
            "ExecChain DEBUG 8 – STOP"
        )
        return

    description = _("{0} is approved. Please start {1} for {2}.").format(
        doc.doctype, next_doctype, customer
    )

    created = 0
    for vh in vendor_heads:
        user = vh.user
        enabled = frappe.db.get_value("User", user, "enabled")

        print(
            f"Processing user={user} | enabled={enabled}",
            "ExecChain DEBUG 9 – User Loop"
        )

        if not enabled:
            continue

        existing = frappe.db.exists("ToDo", {
            "reference_type": next_doctype,
            "reference_name": next_doc_name,
            "allocated_to": user,
            "status": "Open",
        })

        print(
            f"user={user} | existing_todo={existing}",
            "ExecChain DEBUG 10 – Duplicate Check"
        )

        if existing:
            continue

        try:
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "allocated_to": user,
                "description": description,
                "reference_type": next_doctype,
                "reference_name": next_doc_name,
                "role": "Vendor Head",
                "priority": "High",
                "status": "Open",
                "date": nowdate(),
            })
            todo.flags.ignore_permissions = True
            todo.insert()
            frappe.db.commit()
            created += 1
            print(
                f"SUCCESS – ToDo created for user={user} | todo={todo.name}",
                "ExecChain DEBUG 11 – ToDo Created"
            )
        except Exception:
            print(
                frappe.get_traceback(),
                f"ExecChain DEBUG 11 – FAILED insert for user={user}"
            )

    print(
        f"Total ToDos created: {created}",
        "ExecChain DEBUG 12 – Done"
    )

    if created:
        frappe.msgprint(
            _("ToDo assigned to {0} Vendor Head(s): Start {1}").format(created, next_doctype),
            alert=True,
            indicator="blue",
        )