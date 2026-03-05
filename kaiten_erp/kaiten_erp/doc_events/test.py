import frappe
from frappe import _


# ==============================
# Entry Point
# ==============================

def on_update(job_file, method):
    handle_advance_override(job_file)
    handle_workflow_transition(job_file)


# ==============================
# Advance Override Logic
# ==============================

def handle_advance_override(job_file):
    if not (
        job_file.has_value_changed("advance_override_approved")
        and job_file.advance_override_approved
    ):
        return

    validate_advance_override_permissions()
    validate_advance_invoice_status(job_file)

    update_advance_audit_fields(job_file)
    close_advance_todos(job_file)
    notify_accounts_managers(job_file)


def validate_advance_override_permissions():
    roles = frappe.get_roles(frappe.session.user)
    if "Execution Manager" not in roles and "System Manager" not in roles:
        frappe.throw(_("Only Execution Managers can approve Advance Override."))


def validate_advance_invoice_status(job_file):
    if job_file.advance_invoice_status != "Partly Paid":
        frappe.throw(
            _("Override allowed only for Partly Paid invoices. Current Status: {0}")
            .format(job_file.advance_invoice_status)
        )


def update_advance_audit_fields(job_file):
    job_file.db_set({
        "advance_override_approved_by": frappe.session.user,
        "advance_override_approved_on": frappe.utils.now(),
        "override_notification_sent": 1,
    }, update_modified=False)


def close_advance_todos(job_file):
    todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Job File",
            "reference_name": job_file.name,
            "status": "Open",
            "description": ["like", "%Advance Partially Paid%"],
        },
        pluck="name",
    )
    for todo in todos:
        frappe.db.set_value("ToDo", todo, "status", "Closed")


def notify_accounts_managers(job_file):
    msg = _("Dispatch approved with partial advance payment. Outstanding: {0}").format(
        frappe.utils.fmt_money(
            job_file.advance_outstanding_amount or 0,
            currency=job_file.currency or "INR",
        )
    )

    job_file.add_comment(
        "Info", f"Advance Override Approved by {frappe.session.user}. {msg}"
    )

    managers = frappe.get_all(
        "Has Role",
        filters={"role": "Accounts Manager", "parenttype": "User"},
        pluck="parent",
    )

    for user in managers:
        if user != frappe.session.user:
            frappe.publish_realtime(
                "msgprint",
                {
                    "message": msg,
                    "title": "Override Approved",
                    "indicator": "green",
                },
                user=user,
            )

    frappe.msgprint(
        _("Advance Override Approved. Notification sent to Accounts Team."),
        indicator="green",
        alert=True,
    )


# ==============================
# Workflow Router
# ==============================

def handle_workflow_transition(job_file):
    if not job_file.has_value_changed("workflow_state"):
        return

    if job_file.workflow_state == "Approval Pending":
        assign_to_execution_managers(job_file)

    elif job_file.workflow_state == "Job File Initiated":
        handle_job_file_initiated(job_file)


# ==============================
# Job File Initiated Flow
# ==============================

def handle_job_file_initiated(job_file):
    validate_suppliers(job_file)

    opportunity = create_opportunity(job_file)

    set_initiating_sales_manager(job_file)
    assign_sales_manager_owner_todo(job_file, opportunity)

    execution_docs = create_all_executions(job_file)

    link_documents_back_to_job_file(job_file, opportunity, execution_docs)

    frappe.msgprint(
        _("Opportunity {0} and Execution Documents created successfully.")
        .format(opportunity.name),
        indicator="green",
    )


def validate_suppliers(job_file):
    if not job_file.custom_assigned_technical_supplier:
        frappe.throw(_("Assigned Technical Supplier is required"))
    if not job_file.custom_assigned_meter_supplier:
        frappe.throw(_("Assigned Meter Supplier is required"))


# ==============================
# Execution Creation
# ==============================

def create_all_executions(job_file):
    return {
        "technical_survey": create_execution(
            "Technical Survey",
            job_file,
            job_file.custom_assigned_technical_supplier,
        ),
        "structure_mounting": create_execution(
            "Structure Mounting",
            job_file,
            job_file.custom_assigned_technical_supplier,
        ),
        "project_installation": create_execution(
            "Project Installation",
            job_file,
            job_file.custom_assigned_technical_supplier,
        ),
        "meter_installation": create_execution(
            "Meter Installation",
            job_file,
            job_file.custom_assigned_meter_supplier,
        ),
        "meter_commissioning": create_execution(
            "Meter Commissioning",
            job_file,
            job_file.custom_assigned_meter_supplier,
        ),
        "verification_handover": create_execution(
            "Verification Handover",
            job_file,
            job_file.custom_assigned_technical_supplier,
        ),
    }


def create_execution(doctype, job_file, vendor):
    validate_supplier(vendor)

    doc = frappe.get_doc({
        "doctype": doctype,
        "job_file": job_file.name,
        "lead": job_file.lead,
        "customer": job_file.customer,
        "assigned_vendor": vendor,
        "status": "Draft",
    })

    doc.insert()
    return doc


def validate_supplier(vendor):
    if not vendor:
        frappe.throw(_("Vendor is required"))

    if not frappe.db.exists("Supplier", vendor):
        frappe.throw(_("Supplier '{0}' does not exist").format(vendor))


# ==============================
# Opportunity
# ==============================

def create_opportunity(job_file):
    existing = frappe.db.get_value(
        "Opportunity",
        {"custom_job_file": job_file.name},
        "name"
    )
    if existing:
        return frappe.get_doc("Opportunity", existing)

    party = job_file.customer or job_file.lead
    if not party:
        frappe.throw(_("Customer or Lead required to create Opportunity"))

    doc = frappe.get_doc({
        "doctype": "Opportunity",
        "opportunity_from": "Customer" if job_file.customer else "Lead",
        "party_name": party,
        "custom_job_file": job_file.name,
        "opportunity_amount": job_file.negotiated_amount or 0,
        "status": "Open",
    })

    doc.insert()
    return doc


# ==============================
# Linking Back
# ==============================

def link_documents_back_to_job_file(job_file, opportunity, executions):
    job_file.db_set({
        "custom_opportunity": opportunity.name,
        "custom_technical_survey": executions["technical_survey"].name,
        "custom_structure_mounting": executions["structure_mounting"].name,
        "custom_project_installation": executions["project_installation"].name,
        "custom_meter_installation": executions["meter_installation"].name,
        "custom_meter_commissioning": executions["meter_commissioning"].name,
        "custom_verification_handover": executions["verification_handover"].name,
    }, update_modified=False)





# working old jobFile_events.py

# import frappe
# from frappe import _


# def _normalize_select_value(doctype, fieldname, value):
#     """Return a valid single Select option when stale multiline values are stored."""
#     if not value:
#         return value

#     value = str(value).strip()
#     options = frappe.get_meta(doctype).get_field(fieldname).options or ""
#     valid_options = [opt.strip() for opt in options.split("\n") if opt.strip()]

#     if value in valid_options:
#         return value

#     # Legacy bad data can store all options as one multiline value.
#     for line in [part.strip() for part in value.split("\n") if part.strip()]:
#         if line in valid_options:
#             return line

#     return value


# def on_update(job_file, method):
#     # Handle Advance Override Approval
#     if (
#         job_file.has_value_changed("advance_override_approved")
#         and job_file.advance_override_approved
#     ):
#         # 1. Permission Check
#         if "Execution Manager" not in frappe.get_roles(
#             frappe.session.user
#         ) and "System Manager" not in frappe.get_roles(frappe.session.user):
#             frappe.throw(_("Only Execution Managers can approve Advance Override."))

#         # 2. Validation Check (Must be Partly Paid)
#         # We rely on advance_invoice_status field which is updated by Payment Entry
#         if job_file.advance_invoice_status != "Partly Paid":
#             frappe.throw(
#                 _(
#                     "Overview Approval allowed only for Partly Paid invoices. Current Status: {0}"
#                 ).format(job_file.advance_invoice_status)
#             )

#         # 3. Update Audit Fields
#         frappe.db.set_value(
#             "Job File",
#             job_file.name,
#             {
#                 "advance_override_approved_by": frappe.session.user,
#                 "advance_override_approved_on": frappe.utils.now(),
#                 "override_notification_sent": 1,
#             },
#             update_modified=False,
#         )

#         # 4. Close 'Advance Partially Paid' ToDos
#         todos = frappe.get_all(
#             "ToDo",
#             filters={
#                 "reference_type": "Job File",
#                 "reference_name": job_file.name,
#                 "status": "Open",
#                 "description": ["like", "%Advance Partially Paid%"],
#             },
#         )
#         for todo in todos:
#             frappe.db.set_value("ToDo", todo.name, "status", "Closed")

#         # 5. Notify Accounts Managers
#         msg = _(
#             "Dispatch approved with partial advance payment. Outstanding: {0}"
#         ).format(
#             frappe.utils.fmt_money(
#                 job_file.advance_outstanding_amount or 0,
#                 currency=job_file.currency or "INR",
#             )
#         )

#         # Add a timeline comment
#         job_file.add_comment(
#             "Info", f"Advance Override Approved by {frappe.session.user}. {msg}"
#         )

#         # Send system notification to Accounts Managers
#         accounts_managers = frappe.get_all(
#             "Has Role",
#             filters={"role": "Accounts Manager", "parenttype": "User"},
#             fields=["parent"],
#         )
#         for mgr in accounts_managers:
#             if mgr.parent != frappe.session.user:
#                 frappe.publish_realtime(
#                     "msgprint",
#                     {
#                         "message": msg,
#                         "title": "Override Approved",
#                         "indicator": "green",
#                     },
#                     user=mgr.parent,
#                 )

#         frappe.msgprint(
#             _("Advance Override Approved. Notification sent to Accounts Team."),
#             indicator="green",
#             alert=True,
#         )

#     if job_file.has_value_changed("workflow_state"):
#         print(f"Workflow state changed to: {job_file.workflow_state}")

#         # Handle Approval Pending state - Create ToDo for Execution Managers
#         if job_file.workflow_state == "Approval Pending":
#             print("Triggering assign_to_execution_managers...")
#             assign_to_execution_managers(job_file)

#         if job_file.workflow_state == "Job File Initiated":

#             #  check for assigned supplier company before creating execution documents
#             if not job_file.custom_assigned_technical_supplier:
#                 frappe.throw(_("Assigned Technical Supplier is required"))

#             if not job_file.custom_assigned_meter_supplier:
#                 frappe.throw(_("Assigned Meter Supplier is required"))

#             # Create Opportunity from Job File
#             opportunity = create_opportunity(job_file)

#             # Record which Sales Manager initiated the Job File, if field exists
#             set_initiating_sales_manager(job_file)

#             # Create ToDo for the Job File owner (Sales Manager) to prepare Quotation
#             assign_sales_manager_owner_todo(job_file, opportunity)

#             # 3. Technical vendor executions

#             # Prepare data for Technical Survey
#             technical_survey_data = {
#                 "first_name": job_file.get("first_name"),
#                 "last_name": job_file.get("last_name"),
#                 "mobile_number": job_file.get("mobile_number"),
#                 "email": job_file.get("email"),
#                 "address_line_1": job_file.get("address_line_1"),
#                 "address_line_2": job_file.get("address_line_2"),
#                 "city": job_file.get("city"),
#                 "state": job_file.get("state"),
#                 "territory": job_file.get("territory"),
#                 "existing_load_kw": job_file.get("existing_load_kw"),
#                 "monthly_consumption": job_file.get("monthly_consumption"),
#                 "sanctioned_load_kw": job_file.get("sanctioned_load_kw"),
#                 "required_load_kw": job_file.get("required_load_kw"),
#                 "discom": job_file.get("discom"),
#                 # Remapped fields
#                 "proposed_system_kw__tier": job_file.get("proposed_system"),
#                 "phase_type_copy": job_file.get("phase_type"),
#                 # Potential extra fields (using .get() safely)
#                 "k_number": job_file.get("k_number"),
#                 "roof_area_sqft": job_file.get("roof_area_sqft"),
#                 "roof_type": job_file.get("roof_type"),
#                 "site_type": job_file.get("site_type"),
#                 "area_suitability": job_file.get("area_suitability"),
#                 "data_ycke": job_file.get("preferred_visit_date"),  # Scheduled Date
#                 "data_tila": _normalize_select_value(
#                     "Technical Survey",
#                     "data_tila",
#                     job_file.get("preferred_time_slot"),
#                 ),  # Schedule Slot
#                 "custom_opportunity": opportunity.name,
#             }
#             global technical_survey # set as global to be used in opportunity creation
#             technical_survey = create_execution(
#                 "Technical Survey",
#                 "custom_job_file",
#                 "custom_lead",
#                 job_file,
#                 job_file.custom_assigned_technical_supplier,
#                 extra_data=technical_survey_data,
#             )
#             structure_mounting = create_execution(
#                 "Structure Mounting",
#                 "job_file",
#                 "lead",
#                 job_file,
#                 job_file.custom_assigned_technical_supplier,
#             )
#             project_installation = create_execution(
#                 "Project Installation",
#                 "job_file",
#                 "lead",
#                 job_file,
#                 job_file.custom_assigned_technical_supplier,
#             )
#             meter_installation = create_execution(
#                 "Meter Installation",
#                 "job_file",
#                 "lead",
#                 job_file,
#                 job_file.custom_assigned_meter_supplier,
#             )
#             meter_commissioning = create_execution(
#                 "Meter Commissioning",
#                 "job_file",
#                 "lead",
#                 job_file,
#                 job_file.custom_assigned_meter_supplier,
#             )
#             verification_handover = create_execution(
#                 "Verification Handover",
#                 "job_file",
#                 "lead",
#                 job_file,
#                 job_file.custom_assigned_technical_supplier,
#             )
#             # Update Job File fields with created document names
#             job_file.custom_technical_survey = technical_survey.name
#             job_file.custom_structure_mounting = structure_mounting.name
#             job_file.custom_project_installation = project_installation.name
#             job_file.custom_meter_installation = meter_installation.name
#             job_file.custom_meter_commissioning = meter_commissioning.name
#             job_file.custom_verification_handover = verification_handover.name
#             if frappe.db.has_column("Job File", "custom_opportunity"):
#                 job_file.custom_opportunity = opportunity.name
#             job_file.save()

#             # 6. Show success message
#             opportunity_url = f"/app/opportunity/{opportunity.name}"
#             message = f"""Opportunity <b><a href=\"{opportunity_url}\">{opportunity.name}</a></b> and Execution Documents have been created successfully.<br><br>"""
#             frappe.msgprint(message, title="Documents Created", indicator="green")


# def create_execution(
#     doctype,
#     jobFileName,
#     leadName,
#     job_file,
#     vendor,
#     field_label="Assigned Vendor",
#     extra_data=None,
# ):
#     valid_vendor = get_valid_supplier(vendor, field_label)

#     data = {
#         "doctype": doctype,
#         jobFileName: job_file.name,
#         leadName: job_file.lead,
#         "status": "Draft",
#         "custom_k_number": job_file.get("k_number"),
#     }

#     # CRITICAL: Add customer field from Job File to ensure all execution documents have customer
#     # This prevents "Could not find Party" error during quotation creation
#     if hasattr(job_file, "customer") and job_file.customer:
#         data["customer"] = job_file.customer

#     if valid_vendor:
#         data["assigned_vendor"] = valid_vendor

#     # Add extra data if provided
#     if extra_data:
#         data.update(extra_data)

#     doc = frappe.get_doc(data)

#     # Set flags to allow setting read-only fields
#     doc.flags.ignore_permissions = True
#     doc.flags.ignore_validate = False

#     doc.insert()

#     # Ensure assigned_vendor is saved even if field is read-only
#     # if valid_vendor and doc.assigned_vendor != valid_vendor:
#     #     frappe.db.set_value(doctype, doc.name, "assigned_vendor", valid_vendor, update_modified=False)

#     frappe.db.commit()

#     return doc


# def get_valid_supplier(vendor, field_label):
#     if not vendor:
#         return None

#     # Block emails
#     if "@" in vendor:
#         frappe.throw(_(f"{field_label} must be a Supplier, not an email: {vendor}"))

#     # Must exist as Supplier
#     if not frappe.db.exists("Supplier", vendor):
#         frappe.throw(
#             _(f"Supplier '{vendor}' does not exist. Please select a valid Supplier.")
#         )

#     return vendor


# def create_opportunity(job_file):
#     """
#     Create an Opportunity from Job File data.
#     Maps Job File fields to custom Opportunity fields:
#     - k_number -> custom_k_number
#     - proposed_system -> custom_proposed_system
#     - required_load_kw -> custom_required_load_kw
#     - existing_load_kw -> custom_existing_load_kw
#     - negotiated_amount -> opportunity_amount
#     """
#     existing_opportunity = frappe.db.get_value(
#         "Opportunity", {"custom_job_file": job_file.name}, "name"
#     )
#     if existing_opportunity:
#         return frappe.get_doc("Opportunity", existing_opportunity)

#     opportunity_from = "Customer" if job_file.customer else "Lead"
#     party_name = job_file.customer if job_file.customer else job_file.lead
#     if not party_name:
#         frappe.throw(_("Customer or Lead is required to create Opportunity."))

#     opportunity_data = {
#         "doctype": "Opportunity",
#         "opportunity_from": opportunity_from,
#         "party_name": party_name,
#         "custom_job_file": job_file.name,
#         "custom_technical_survey" : technical_survey.name if 'technical_survey' in globals() else None, # Link 
#         "custom_k_number": job_file.get("k_number"),
#         "custom_proposed_system": job_file.get("proposed_system"),
#         "custom_required_load_kw": job_file.get("required_load_kw"),
#         "custom_existing_load_kw": job_file.get("existing_load_kw"),
#         "opportunity_amount": job_file.get("negotiated_amount") or 0,
#         "status": "Open",
#     }

#     # Create the opportunity document
#     opportunity = frappe.get_doc(opportunity_data)
#     opportunity.flags.ignore_permissions = True
#     opportunity.insert()
#     frappe.db.commit()

#     return opportunity


# def assign_sales_manager_owner_todo(job_file, opportunity):
#     """
#     Create a ToDo for the Job File owner when the Job File is initiated.
#     The ToDo is only assigned if the owner has the Sales Manager role and is enabled.
#     """
#     owner = job_file.owner

#     if not owner:
#         return

#     # Ensure owner is active
#     if not frappe.db.get_value("User", owner, "enabled"):
#         return

#     # Owner must be a Sales Manager
#     has_sales_manager_role = frappe.db.exists(
#         "Has Role", {"parent": owner, "role": "Sales Manager"}
#     )
#     if not has_sales_manager_role:
#         return

#     description = _(
#         "Job File {0} has been initiated. Please create the Quotation for Opportunity {1} before Technical Survey Quotation."
#     ).format(job_file.name, opportunity.name)

#     # Avoid duplicate open ToDos for the same user and opportunity
#     existing_todo = frappe.db.exists(
#         "ToDo",
#         {
#             "allocated_to": owner,
#             "reference_type": "Opportunity",
#             "reference_name": opportunity.name,
#             "status": "Open",
#             "description": description,
#         },
#     )

#     if existing_todo:
#         return

#     todo = frappe.get_doc(
#         {
#             "doctype": "ToDo",
#             "allocated_to": owner,
#             "reference_type": "Opportunity",
#             "reference_name": opportunity.name,
#             "description": description,
#             "priority": "High",
#             "status": "Open",
#         }
#     )
#     todo.flags.ignore_permissions = True
#     todo.insert()
#     frappe.db.commit()


# def set_initiating_sales_manager(job_file):
#     """
#     When a Sales Manager clicks "Start Job File", stamp their user id into
#     the custom Job File owner field (supports both single and double 'r').
#     """

#     current_user = frappe.session.user

#     # Detect which field exists
#     owner_fields = ["custom_job_file_owner", "custom_job_file_ownerr"]
#     target_field = next(
#         (f for f in owner_fields if frappe.db.has_column("Job File", f)), None
#     )

#     if not target_field:
#         return

#     # If already set, keep existing owner
#     if job_file.get(target_field):
#         return

#     frappe.db.set_value(
#         "Job File",
#         job_file.name,
#         target_field,
#         current_user,
#         update_modified=False,
#     )


# def assign_to_execution_managers(job_file):
#     """
#     Assign Job File to all users with Execution Manager role
#     Creates ToDo for each Execution Manager when approval is pending
#     """
#     print(f"\n=== assign_to_execution_managers called ===")
#     print(f"Job File: {job_file.name}")

#     # Get all users with Execution Manager role
#     execution_managers = frappe.get_all(
#         "Has Role",
#         filters={"role": "Execution Manager", "parenttype": "User"},
#         fields=["parent"],
#     )

#     print(f"Found {len(execution_managers)} Execution Managers")

#     if not execution_managers:
#         frappe.msgprint(
#             _("No Execution Managers found to assign this Job File for approval"),
#             indicator="orange",
#             alert=True,
#         )
#         return

#     # Create ToDo for each Execution Manager
#     assigned_count = 0
#     errors = []

#     for manager in execution_managers:
#         user = manager.parent

#         # Check if user is enabled
#         user_enabled = frappe.db.get_value("User", user, "enabled")
#         print(f"    User enabled: {user_enabled}")
#         if not user_enabled:
#             print(f"    Skipping disabled user: {user}")
#             continue

#         # Check if ToDo already exists for this user and document
#         existing_todo = frappe.db.exists(
#             "ToDo",
#             {
#                 "reference_type": "Job File",
#                 "reference_name": job_file.name,
#                 "allocated_to": user,
#                 "status": "Open",
#             },
#         )

#         print(f"    Existing ToDo: {existing_todo}")

#         if existing_todo:
#             print(f"    Skipping - ToDo already exists for user: {user}")
#             continue

#         try:
#             print(f"    Creating ToDo for {user}...")
#             # Create ToDo
#             todo = frappe.get_doc(
#                 {
#                     "doctype": "ToDo",
#                     "allocated_to": user,
#                     "reference_type": "Job File",
#                     "reference_name": job_file.name,
#                     "description": f"Job File {job_file.name} requires approval. Negotiated Amount (₹{job_file.negotiated_amount or 0:,.2f}) is less than MRP (₹{job_file.mrp or 0:,.2f}).",
#                     "priority": "High",
#                     "status": "Open",
#                 }
#             )
#             todo.flags.ignore_permissions = True
#             todo.insert()
#             frappe.db.commit()
#             assigned_count += 1
#             print(f"    ✓ Successfully created ToDo: {todo.name}")
#         except Exception as e:
#             print(f"    ✗ Error creating ToDo: {str(e)}")
#             error_msg = f"Failed to create ToDo for {user}: {str(e)}"
#             errors.append(error_msg)
#             frappe.log_error(error_msg, "Job File ToDo Assignment Error")

#     if assigned_count > 0:
#         frappe.msgprint(
#             _("Job File assigned to {0} Execution Manager(s) for approval").format(
#                 assigned_count
#             ),
#             indicator="green",
#             alert=True,
#         )

#     if errors:
#         frappe.msgprint(
#             _("Some assignments failed. Check Error Log for details."),
#             indicator="orange",
#             alert=True,
#         )
