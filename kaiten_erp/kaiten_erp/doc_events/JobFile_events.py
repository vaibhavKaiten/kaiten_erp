import frappe
from frappe import _


def _normalize_select_value(doctype, fieldname, value):
    """Return a valid single Select option when stale multiline values are stored."""
    if not value:
        return value

    value = str(value).strip()
    options = frappe.get_meta(doctype).get_field(fieldname).options or ""
    valid_options = [opt.strip() for opt in options.split("\n") if opt.strip()]

    if value in valid_options:
        return value

    # Legacy bad data can store all options as one multiline value.
    for line in [part.strip() for part in value.split("\n") if part.strip()]:
        if line in valid_options:
            return line

    return value


def on_update(job_file, method):

    if job_file.has_value_changed("workflow_state"):
       

        # Set Job File Owner when "Start Job File" is clicked (Draft -> In Progress)
        # This can be overridden by subsequent users until final initiation
        if job_file.workflow_state == "In Progress":
            _close_execution_manager_todos(job_file)  # Issue C: close if returning from Approval Pending
            _close_start_job_file_todos(job_file)     # Issue F: close stale Sales Manager todos
            set_initiating_sales_manager(job_file, allow_override=True, final=False)

        # Handle Approval Pending state - Create ToDo for Execution Managers
        if job_file.workflow_state == "Approval Pending":
            print("Triggering assign_to_execution_managers...")
            assign_to_execution_managers(job_file)

        if job_file.workflow_state == "Job File Initiated":
            _close_execution_manager_todos(job_file)  # Issue C: job file approved — close approval todos
            _close_start_job_file_todos(job_file)     # Issue F: close stale Sales Manager todos

            # Set the FINAL Job File Owner (always override - this is the last action)
            set_initiating_sales_manager(job_file, allow_override=False, final=True)

            #  check for assigned supplier company before creating execution documents
            if not job_file.custom_assigned_technical_supplier:
                frappe.throw(_("Assigned Technical Supplier is required"))

            if not job_file.custom_assigned_meter_supplier:
                frappe.throw(_("Assigned Meter Supplier is required"))

            # Create Opportunity from Job File
            opportunity = create_opportunity(job_file)

            # Create ToDo for the Job File owner (Sales Manager) to prepare Quotation
            assign_sales_manager_owner_todo(job_file, opportunity)
          
            # 3. Technical vendor executions

            # Prepare data for Technical Survey
            technical_survey_data = {
                "first_name": job_file.get("first_name"),
                "last_name": job_file.get("last_name"),
                "mobile_number": job_file.get("mobile_number"),
                "email": job_file.get("email"),
                "address_line_1": job_file.get("address_line_1"),
                "address_line_2": job_file.get("address_line_2"),
                "city": job_file.get("city"),
                "state": job_file.get("state"),
                "territory": job_file.get("territory"),
                "existing_load_kw": job_file.get("existing_load_kw"),
                "monthly_consumption": job_file.get("monthly_consumption"),
                "sanctioned_load_kw": job_file.get("sanctioned_load_kw"),
                "required_load_kw": job_file.get("required_load_kw"),
                "discom": job_file.get("discom"),
                # Remapped fields
                "proposed_system_kw__tier": job_file.get("proposed_system"),
                "phase_type_copy": job_file.get("phase_type"),
                # Potential extra fields (using .get() safely)
                "custom_k_number": job_file.get("k_number"),
                "roof_area_sqft": job_file.get("custom_roof_area_sqft"),
                "roof_type": job_file.get("custom_roof_type"),
                "site_type": job_file.get("custom_site_type"),
                "area_suitability": job_file.get("custom_area_suitability"),
                "data_ycke": job_file.get("preferred_visit_date"),  # Scheduled Date
                "data_tila": _normalize_select_value(
                    "Technical Survey",
                    "data_tila",
                    job_file.get("preferred_time_slot"),
                ),  # Schedule Slot
                "custom_opportunity": opportunity.name,
            }

            technical_survey = create_execution(
                "Technical Survey",
                "custom_job_file",
                "custom_lead",
                job_file,
                job_file.custom_assigned_technical_supplier,
                extra_data=technical_survey_data,
            )
            structure_mounting = create_execution(
                "Structure Mounting",
                "job_file",
                "lead",
                job_file,
                job_file.custom_assigned_technical_supplier,
            )
            project_installation = create_execution(
                "Project Installation",
                "job_file",
                "lead",
                job_file,
                job_file.custom_assigned_technical_supplier,
            )
            meter_installation = create_execution(
                "Meter Installation",
                "job_file",
                "lead",
                job_file,
                job_file.custom_assigned_meter_supplier,
            )
            meter_commissioning = create_execution(
                "Meter Commissioning",
                "job_file",
                "lead",
                job_file,
                job_file.custom_assigned_meter_supplier,
            )
            verification_handover = create_execution(
                "Verification Handover",
                "job_file",
                "lead",
                job_file,
                job_file.custom_assigned_technical_supplier,
            )
            # Update Job File fields with created document names
            update_data = {
                "custom_technical_survey": technical_survey.name,
                "custom_structure_mounting": structure_mounting.name,
                "custom_project_installation": project_installation.name,
                "custom_meter_installation": meter_installation.name,
                "custom_meter_commissioning": meter_commissioning.name,
                "custom_verification_handover": verification_handover.name,
                "custom_opportunity": opportunity.name,
            }
            if frappe.db.has_column("Job File", "custom_opportunity"):
                update_data["custom_opportunity"] = opportunity.name

            frappe.db.set_value("Job File", job_file.name, update_data, update_modified=False)
           
            # Create ToDo for Vendor Heads to start the Technical Survey
            assign_vendor_head_todos(job_file, technical_survey.name)

            # 6. Show success message
            opportunity_url = f"/app/opportunity/{opportunity.name}"
            message = f"""Opportunity <b><a href=\"{opportunity_url}\">{opportunity.name}</a></b> and Execution Documents have been created successfully.<br><br>"""
            frappe.msgprint(message, title="Documents Created", indicator="green")

    # Token Amount → Accounts Manager ToDo
    if job_file.has_value_changed("token_amount_recieved") and job_file.token_amount_recieved:
        _create_token_amount_todo(job_file)

    # Link customer to DISCOM Master when discom is set/changed
    if job_file.discom and job_file.customer:
        _link_customer_to_discom(job_file)


def _link_customer_to_discom(job_file):
    """Add Job File's customer to the DISCOM Master's Linked Customers table (if not already present)."""
    discom = frappe.get_doc("DISCOM Master", job_file.discom)

    # Check if this customer + job_file combination already exists
    already_linked = any(
        row.customer == job_file.customer and row.job_file == job_file.name
        for row in discom.linked_customers
    )
    if already_linked:
        return

    discom.append("linked_customers", {
        "customer": job_file.customer,
        "job_file": job_file.name,
        "status": "Pending",
    })
    discom.flags.ignore_permissions = True
    discom.flags.ignore_validate = True
    discom.save()


def _create_token_amount_todo(job_file):
    """Create a ToDo for each Accounts Manager to make a Payment Entry
    when Token Amount is filled on a Job File."""

    if not job_file.customer:
        return

    customer_name = frappe.db.get_value("Customer", job_file.customer, "customer_name") or job_file.customer
    k_number = job_file.k_number or job_file.name
    amount = frappe.utils.fmt_money(job_file.token_amount_recieved, currency="INR")

    description = f"{customer_name} - {k_number}. Create payment entry - {amount}"

    accounts_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Accounts Manager", "parenttype": "User"},
        fields=["parent"],
    )

    if not accounts_managers:
        return

    for manager in accounts_managers:
        user = manager.parent

        if not frappe.db.get_value("User", user, "enabled"):
            continue

        # Avoid duplicate open ToDos
        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Customer",
                "reference_name": job_file.customer,
                "allocated_to": user,
                "status": "Open",
                "description": description,
            },
        )
        if existing:
            continue

        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": user,
                "reference_type": "Customer",
                "reference_name": job_file.customer,
                "description": description,
                "role": "Accounts Manager",
                "priority": "High",
                "status": "Open",
            }
        )
        todo.flags.ignore_permissions = True
        todo.insert()

    frappe.db.commit()


def create_execution(
    doctype,
    jobFileName,
    leadName,
    job_file,
    vendor,
    field_label="Assigned Vendor",
    extra_data=None,
):
    valid_vendor = get_valid_supplier(vendor, field_label)

    data = {
        "doctype": doctype,
        jobFileName: job_file.name,
        leadName: job_file.lead,
        "status": "Draft",
        "custom_k_number": job_file.get("k_number"),
    }

    # CRITICAL: Add customer field from Job File to ensure all execution documents have customer
    # This prevents "Could not find Party" error during quotation creation
    if hasattr(job_file, "customer") and job_file.customer:
        data["customer"] = job_file.customer

    if valid_vendor:
        data["assigned_vendor"] = valid_vendor

    # Add extra data if provided
    if extra_data:
        data.update(extra_data)

    # Ensure Job File + Lead links are always populated, regardless of which fieldnames
    # the caller passes (some doctypes use `custom_job_file`, others use `job_file`,
    # and similarly `custom_lead` vs `lead`).
    meta = frappe.get_meta(doctype)
    for fieldname in ("custom_job_file", "job_file"):
        if meta.has_field(fieldname) and not data.get(fieldname):
            data[fieldname] = job_file.name
    for fieldname in ("custom_lead", "lead"):
        if meta.has_field(fieldname) and not data.get(fieldname):
            data[fieldname] = job_file.lead

    doc = frappe.get_doc(data)

    # Set flags to allow setting read-only fields
    doc.flags.ignore_permissions = True
    doc.flags.ignore_validate = False

    doc.insert()

    # Backfill via DB in case meta/cache/custom-field mismatch caused the insert payload
    # to miss these columns (or another hook cleared them).
    if frappe.db.has_column(doctype, "custom_job_file") and not doc.get("custom_job_file"):
        frappe.db.set_value(
            doctype, doc.name, "custom_job_file", job_file.name, update_modified=False
        )
    if frappe.db.has_column(doctype, "job_file") and not doc.get("job_file"):
        frappe.db.set_value(
            doctype, doc.name, "job_file", job_file.name, update_modified=False
        )

    
    # Link execution doc back to Sales Order (for milestone invoice tracking)
    if job_file.get("sales_order") and frappe.db.has_column(doctype, "custom_sales_order"):
        frappe.db.set_value(
            doctype, doc.name, "custom_sales_order",
            job_file.sales_order, update_modified=False,
        )

    return doc


def get_valid_supplier(vendor, field_label):
    if not vendor:
        return None

    # Block emails
    if "@" in vendor:
        frappe.throw(_(f"{field_label} must be a Supplier, not an email: {vendor}"))

    # Must exist as Supplier
    if not frappe.db.exists("Supplier", vendor):
        frappe.throw(
            _(f"Supplier '{vendor}' does not exist. Please select a valid Supplier.")
        )

    return vendor


def create_opportunity(job_file):
    """
    Create an Opportunity from Job File data.
    Maps Job File fields to custom Opportunity fields:
    - k_number -> custom_k_number
    - proposed_system -> custom_proposed_system
    - required_load_kw -> custom_required_load_kw
    - existing_load_kw -> custom_existing_load_kw
    - negotiated_amount -> opportunity_amount
    """
    existing_opportunity = frappe.db.get_value(
        "Opportunity", {"custom_job_file": job_file.name}, "name"
    )
    if existing_opportunity:
        return frappe.get_doc("Opportunity", existing_opportunity)

    opportunity_from = "Customer" if job_file.customer else "Lead"
    party_name = job_file.customer if job_file.customer else job_file.lead
    if not party_name:
        frappe.throw(_("Customer or Lead is required to create Opportunity."))

    opportunity_data = {
        "doctype": "Opportunity",
        "opportunity_from": opportunity_from,
        "party_name": party_name,
        "custom_job_file": job_file.name,
        "custom_k_number": job_file.get("k_number"),
        "custom_proposed_system": job_file.get("proposed_system"),
        "custom_required_load_kw": job_file.get("required_load_kw"),
        "custom_existing_load_kw": job_file.get("existing_load_kw"),
        "opportunity_amount": job_file.get("negotiated_amount") or 0,
        "status": "Open",
    }

    # Create the opportunity document
    opportunity = frappe.get_doc(opportunity_data)
    opportunity.flags.ignore_permissions = True
    opportunity.insert()
    frappe.db.commit()

    return opportunity


def assign_sales_manager_owner_todo(job_file, opportunity):
    """
    Create a ToDo for the Job File owner when the Job File is initiated.
    The ToDo is only assigned if the owner has the Sales Manager role and is enabled.
    """
    owner = job_file.get("custom_job_file_owner") or frappe.session.user

    if not owner:
        return

    # Ensure owner is active
    if not frappe.db.get_value("User", owner, "enabled"):
        return

    # Owner must be a Sales Manager
    has_sales_manager_role = frappe.db.exists(
        "Has Role", {"parent": owner, "role": "Sales Manager"}
    )
    if not has_sales_manager_role:
        return

    customer_name = job_file.customer or (
        f"{job_file.first_name or ''} {job_file.last_name or ''}".strip()
    )
    description = _("Create quotation for {0}").format(customer_name)

    # Avoid duplicate open ToDos for the same user and opportunity
    existing_todo = frappe.db.exists(
        "ToDo",
        {
            "allocated_to": owner,
            "reference_type": "Opportunity",
            "reference_name": opportunity.name,
            "status": "Open",
            "description": description,
        },
    )

    if existing_todo:
        return

    todo = frappe.get_doc(
        {
            "doctype": "ToDo",
            "allocated_to": owner,
            "reference_type": "Opportunity",
            "reference_name": opportunity.name,
            "description": description,
            "role" : "Sales Manager",
            "priority": "High",
            "status": "Open",
        }
    )
    todo.flags.ignore_permissions = True
    todo.insert()
    frappe.db.commit()



def set_initiating_sales_manager(job_file, allow_override=True, final=False):
    """
    Set Job File Owner to the current user.
    
    Args:
        job_file: Job File document
        allow_override: If True, only set if not already set. If False, always override.
        final: If True, this is the final owner assignment (on Initiate)
    """

    current_user = frappe.session.user
    


    # Detect which field exists
    owner_fields = ["custom_job_file_owner", "custom_job_file_ownerr"]
    target_field = next(
        (f for f in owner_fields if frappe.db.has_column("Job File", f)), None
    )

    if not target_field:
        print("ERROR: No Job File owner field found in database!")
        return
    
   
    current_owner = job_file.get(target_field)
  

   
    # Set the value directly on the document
    job_file.db_set(target_field, current_user, update_modified=False)
    action_type = "FINAL" if final else "temporary"
    

def assign_to_execution_managers(job_file):
    """
    Assign Job File to all users with Execution Manager role
    Creates ToDo for each Execution Manager when approval is pending
    """
    print(f"\n=== assign_to_execution_managers called ===")
    print(f"Job File: {job_file.name}")

    # Get all users with Execution Manager role
    execution_managers = frappe.get_all(
        "Has Role",
        filters={"role": "Execution Manager", "parenttype": "User"},
        fields=["parent"],
    )

    print(f"Found {len(execution_managers)} Execution Managers")

    if not execution_managers:
        frappe.msgprint(
            _("No Execution Managers found to assign this Job File for approval"),
            indicator="orange",
            alert=True,
        )
        return

    # Create ToDo for each Execution Manager
    assigned_count = 0
    errors = []

    for manager in execution_managers:
        user = manager.parent

        # Check if user is enabled
        user_enabled = frappe.db.get_value("User", user, "enabled")
        print(f"    User enabled: {user_enabled}")
        if not user_enabled:
            print(f"    Skipping disabled user: {user}")
            continue

        # Check if ToDo already exists for this user and document
        existing_todo = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Job File",
                "reference_name": job_file.name,
                "allocated_to": user,
                "status": "Open",
            },
        )

        print(f"    Existing ToDo: {existing_todo}")

        if existing_todo:
            print(f"    Skipping - ToDo already exists for user: {user}")
            continue

        try:
            print(f"    Creating ToDo for {user}...")
            # Create ToDo
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": "Job File",
                    "reference_name": job_file.name,
                    "description": f"Job File {job_file.name} requires approval. Negotiated Amount (₹{job_file.negotiated_amount or 0:,.2f}) is less than MRP (₹{job_file.mrp or 0:,.2f}).",
                    "role": "Execution Manager",
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            assigned_count += 1
            print(f"    ✓ Successfully created ToDo: {todo.name}")
        except Exception as e:
            print(f"    ✗ Error creating ToDo: {str(e)}")
            error_msg = f"Failed to create ToDo for {user}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(error_msg, "Job File ToDo Assignment Error")

    if assigned_count > 0:
        frappe.msgprint(
            _("Job File assigned to {0} Execution Manager(s) for approval").format(
                assigned_count
            ),
            indicator="green",
            alert=True,
        )

    if errors:
        frappe.msgprint(
            _("Some assignments failed. Check Error Log for details."),
            indicator="orange",
            alert=True,
        )


def assign_vendor_head_todos(job_file, technical_survey_name):
    """
    Create one ToDo per Vendor Head user for the Technical Survey document
    created when a Job File is initiated. Instructs them to fill the Technical
    Survey and assign a Vendor Executive in the 'Assigned Internal User' field.

    Args:
        job_file: Job File document
        technical_survey_name: Name of the newly created Technical Survey document
    """
    vendor_heads = frappe.get_all(
        "Has Role",
        filters={"role": "Vendor Head", "parenttype": "User"},
        fields=["parent"],
    )

    if not vendor_heads:
        frappe.logger("kaiten_erp").warning(
            f"No Vendor Head users found. Skipping ToDo assignment for Job File {job_file.name}"
        )
        return

    assigned_count = 0

    for head in vendor_heads:
        user = head.parent

        if not frappe.db.get_value("User", user, "enabled"):
            continue

        # Duplicate guard
        existing = frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Technical Survey",
                "reference_name": technical_survey_name,
                "allocated_to": user,
                "status": "Open",
            },
        )
        if existing:
            continue

        customer_first_name = job_file.first_name or job_file.name
        description = f"{customer_first_name} - {technical_survey_name} - Initiate Technical Survey"

        try:
            todo = frappe.get_doc(
                {
                    "doctype": "ToDo",
                    "allocated_to": user,
                    "reference_type": "Technical Survey",
                    "reference_name": technical_survey_name,
                    "role": "Vendor Head",
                    "description": description,
                    "priority": "High",
                    "status": "Open",
                }
            )
            todo.flags.ignore_permissions = True
            todo.insert()
            assigned_count += 1
        except Exception as e:
            frappe.log_error(
                f"Failed to create Vendor Head ToDo for {user} on Technical Survey {technical_survey_name}: {str(e)}",
                "Vendor Head ToDo Assignment Error",
            )

    if assigned_count:
        frappe.logger("kaiten_erp").info(
            f"Created {assigned_count} Vendor Head ToDo(s) for Technical Survey {technical_survey_name}"
        )


def _close_execution_manager_todos(job_file):
    """Close all Open Execution Manager ToDos for this Job File (Issue C)."""
    todos = frappe.db.sql(
        """
        SELECT DISTINCT t.name
        FROM `tabToDo` t
        INNER JOIN `tabHas Role` hr ON hr.parent = t.allocated_to AND hr.parenttype = 'User'
        WHERE t.reference_type = 'Job File'
            AND t.reference_name = %(name)s
            AND t.status = 'Open'
            AND hr.role = 'Execution Manager'
        """,
        {"name": job_file.name},
        as_dict=True,
    )
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} Execution Manager ToDo(s) for Job File {job_file.name}"
        )


def _close_start_job_file_todos(job_file):
    """Close 'Start Job File' Sales Manager ToDos for this Job File (Issue F)."""
    todos = frappe.db.get_all(
        "ToDo",
        filters={
            "reference_type": "Job File",
            "reference_name": job_file.name,
            "status": "Open",
            "description": ["like", "%Start Job File%"],
        },
        fields=["name"],
    )
    for t in todos:
        frappe.db.set_value("ToDo", t.name, "status", "Closed", update_modified=False)
    if todos:
        frappe.logger("kaiten_erp").info(
            f"Closed {len(todos)} 'Start Job File' ToDo(s) for Job File {job_file.name}"
        )
