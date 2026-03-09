# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from kaiten_erp.kaiten_erp.api.lead_vendor import validate_vendor_manager_territory
from kaiten_erp.kaiten_erp.doc_events.lead_validation import validate_vendors


def on_update(doc, method=None):
    """
    Lead on_update hook - Auto-create Job File when Lead workflow_state changes to 'Qualified'
    Also auto-creates Customer when workflow_state becomes 'Qualified'
    """

    # NOTE: We do NOT sync status with workflow_state anymore
    # status field uses standard ERPNext options: Lead, Open, Replied, etc.
    # workflow_state uses your custom workflow: Draft, Contacted, Qualified, etc.
    # They work independently - do not mix them!

    # Only set default status for new leads if empty
    if not doc.status:
        doc.db_set("status", "Lead", update_modified=False)
    
    # Handle Active Sales Manager assignment - create ToDo and set lead_owner
    if doc.has_value_changed("custom_active_sales_manager") and doc.get("custom_active_sales_manager"):
        assign_active_sales_manager(doc)
    
    # Check if workflow_state field has changed using has_value_changed
    if doc.has_value_changed("workflow_state"):
        new_workflow_state = doc.workflow_state
        
        print(f"\n=== Lead Workflow State Changed ===")
        print(f"Lead: {doc.name}")
        print(f"New State: {new_workflow_state}")
        print(f"Current User: {frappe.session.user}")

        # Set Lead Owner when "Mark Contacted" is clicked (Draft/Reopen -> Contacted)
        # This can be overridden by subsequent users until final qualification
        if new_workflow_state == "Contacted":
            print("\n>>> 'Mark Contacted' action detected - Setting Lead Owner (can be overridden) <<<")
            set_lead_owner(doc, allow_override=True, final=False)

        # Check if changed TO "Qualified" - FINAL action
        if new_workflow_state == "Qualified":
            print("\n>>> 'Mark Qualified' action detected - Setting FINAL Lead Owner <<<")
            
            # Set the FINAL Lead Owner (always override - this is the last action)
            set_lead_owner(doc, allow_override=False, final=True)
            
            # Create Job File from Lead
            create_job_file_from_lead(doc)
            
            # Assign Active Sales Manager if set
            if doc.get("custom_active_sales_manager"):
                assign_active_sales_manager(doc)


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


@frappe.whitelist()
def create_job_file_from_lead(lead_name):
    # Accept both Lead document object and lead name string
    if isinstance(lead_name, str):
        lead = frappe.get_doc("Lead", lead_name)
    else:
        # lead_name is actually a Lead document object
        lead = lead_name

    # 0. Auto-create Customer if not exists (CRITICAL: Must happen before Job File creation)
    customer = None
    address = None

    if lead.customer:
        # Customer already linked to Lead
        customer = lead.customer
    else:
        # Create Customer from Lead
        try:
            customer_doc = create_customer_from_lead(lead)
            customer = customer_doc.name

            # Link Customer back to Lead
            lead.customer = customer
            lead.db_set("customer", customer, update_modified=False)

            frappe.msgprint(
                _("Customer {0} created successfully from Lead").format(
                    frappe.get_desk_link("Customer", customer)
                ),
                indicator="green",
                alert=True,
            )
        except Exception as e:
            frappe.log_error(
                title=_("Customer Creation Failed for Lead {0}").format(lead.name),
                message=frappe.get_traceback(),
            )
            frappe.throw(
                _(
                    "Failed to create Customer: {0}. Please create Customer manually before initiating job."
                ).format(str(e)),
                title=_("Customer Creation Failed"),
            )

    # 2. Create Job File (only one) - now with guaranteed customer
    job_file = frappe.get_doc(
        {
            "doctype": "Job File",
            "lead": lead.name,
            "customer": customer,  # Use the customer we just created/validated
            # Copy customer details
            "first_name": lead.get("first_name"),
            "last_name": lead.get("last_name"),
            "company_name": lead.get("company_name"),
            "mobile_number": lead.get("mobile_no"),
            "email": lead.get("email_id"),
            # Copy location details
            "address_line_1": lead.get("custom_address_line_1"),
            "address_line_2": lead.get("custom_address_line_2"),
            "city": lead.get("city") or lead.get("custom_city"),
            "state": lead.get("state"),
            "territory_copy": lead.get("custom_pincode"),
            # Copy electrical details - CRITICAL for Opportunity creation
            "k_number": lead.get("custom_k_number"),
            "existing_load_kw": lead.get("custom_existing_load_kw"),
            "required_load_kw": lead.get("custom_required_load_kw"),
            "sanctioned_load_kw": lead.get("custom_sanctioned_load_kw"),
            "phase_type": lead.get("custom_phase_type"),
            "discom": lead.get("custom_discom"),
            "monthly_consumption": lead.get("custom_monthly_consumption"),
            # Copy proposed system
            "proposed_system": lead.get("custom_proposed_system"),
            # Copy commercial details
            "mrp": lead.get("custom_mrp"),
            "negotiated_amount": lead.get("custom_negotiable_mrp"),
            
        }
    )
    job_file.insert(ignore_permissions=True)
    populate_execution_status(job_file, lead)
    job_file.save(ignore_permissions=True)

    # 5. Link back
    lead.custom_job_file = job_file.name
    lead.save(ignore_permissions=True)

    # 6. Show success message
    job_file_url = f"/app/job-file/{job_file.name}"
    message = f"""Job File <b><a href="{job_file_url}">{job_file.name}</a></b> has been created successfully.<br><br>
    """

    frappe.msgprint(message, title="Job File Created", indicator="green")
    return job_file.name


def create_customer_from_lead(lead):
    """
    Create Customer from Lead

    Args:
        lead: Lead document

    Returns:
        Customer document
    """
    # Check if customer already exists
    customer_name = lead.company_name or f"{lead.first_name} {lead.last_name}"

    existing_customer = frappe.db.get_value(
        "Customer", {"customer_name": customer_name}, "name"
    )

    if existing_customer:
        return frappe.get_doc("Customer", existing_customer)

    # Create new customer
    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Company" if lead.company_name else "Individual",
            "customer_group": "Commercial",
            "territory": "India",
            "gst_category": "Unregistered",
            # Contact details
            "mobile_no": lead.mobile_no,
            "email_id": lead.email_id,
        }
    )

    customer.insert(ignore_permissions=True)

    # Create Address if available
    if lead.get("custom_address_line_1"):
        create_customer_address(customer.name, lead)

    return customer


def create_customer_address(customer_name, lead):
    """Create Address for Customer"""
    try:
        address = frappe.get_doc(
            {
                "doctype": "Address",
                "address_title": customer_name,
                "address_line1": lead.get("custom_address_line_1") or "Not Provided",
                "city": lead.get("city") or "Not Provided",
                "state": lead.get("state") or "Delhi",
                "country": "India",
                "address_type": "Billing",
                "links": [{"link_doctype": "Customer", "link_name": customer_name}],
            }
        )
        address.insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Address creation failed: {str(e)}")


def validate_and_get_vendor(vendor_identifier):
    """
    Validate that vendor_identifier is a valid Supplier.
    Returns Supplier name if valid, None otherwise.

    Args:
        vendor_identifier: Supplier name/ID

    Returns:
        Supplier name if valid and exists, None otherwise
    """
    if not vendor_identifier:
        return None

    # Reject email addresses immediately
    if "@" in str(vendor_identifier):
        frappe.logger().warning(
            f"Vendor identifier '{vendor_identifier}' appears to be an email. "
            "Vendor fields must contain Supplier IDs only."
        )
        return None

    # Check if it's a valid Supplier
    if frappe.db.exists("Supplier", vendor_identifier):
        return vendor_identifier

    # Not found
    frappe.logger().warning(
        f"Vendor identifier '{vendor_identifier}' not found in Supplier list"
    )
    return None


def create_opportunity_from_lead(lead):
    """
    Auto-create Opportunity when Lead workflow_state changes to 'Initiate Job'
    Implements duplicate protection and field mapping

    Args:
        lead: Lead document
    """
    # Duplicate protection - check if Opportunity already exists for this Lead
    existing_opportunity = frappe.db.get_value(
        "Opportunity", {"opportunity_from": "Lead", "party_name": lead.name}, "name"
    )

    if existing_opportunity:
        frappe.msgprint(
            _("Opportunity {0} already exists for this Lead").format(
                frappe.get_desk_link("Opportunity", existing_opportunity)
            ),
            indicator="blue",
            alert=True,
        )
        return

    # Validate required fields
    if not lead.get("custom_proposed_system"):
        frappe.msgprint(
            _(
                "Proposed System is required to create Opportunity. Skipping Opportunity creation."
            ),
            indicator="orange",
            alert=True,
        )
        return

    if not lead.get("custom_negotiable_mrp"):
        frappe.msgprint(
            _(
                "Negotiable MRP is required to create Opportunity. Skipping Opportunity creation."
            ),
            indicator="orange",
            alert=True,
        )
        return

    try:
        # Create Opportunity with field mapping
        opportunity = frappe.get_doc(
            {
                "doctype": "Opportunity",
                "opportunity_from": "Lead",
                "party_name": lead.name,
                "opportunity_type": "Sales",
                "status": "Open",
                "expected_closing": frappe.utils.today(),
                # Field mapping from Lead
                "customer_name": lead.lead_name
                or f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
                "contact_email": lead.email_id,
                "contact_mobile": lead.mobile_no or lead.phone,
                "territory": lead.territory
                or lead.get("custom_territory_display")
                or lead.get("custom_assignment_territory")
                or "All Territories",
                "company": frappe.defaults.get_user_default("Company")
                or frappe.db.get_single_value("Global Defaults", "default_company"),
                # Source tracking
                "source": lead.source,
                # Amount from negotiable_mrp
                "opportunity_amount": lead.get("custom_negotiable_mrp") or 0,
                # Proposed System from Lead
                "custom_proposed_system": lead.get("custom_proposed_system"),
            }
        )

        # Add proposed system as an Opportunity item with negotiable_mrp as rate
        if lead.get("custom_proposed_system"):
            # Get item UOM
            item_details = frappe.db.get_value(
                "Item", lead.custom_proposed_system, ["stock_uom"], as_dict=True
            )

            opportunity.append(
                "items",
                {
                    "item_code": lead.custom_proposed_system,
                    "qty": 1,
                    "uom": item_details.get("stock_uom") if item_details else "Nos",
                    "rate": lead.get("custom_negotiable_mrp") or 0,
                },
            )

        # Set the same lead owner as opportunity owner
        if lead.lead_owner:
            opportunity.opportunity_owner = lead.lead_owner

        opportunity.insert(ignore_permissions=True)
        frappe.db.commit()

        frappe.msgprint(
            _("Opportunity {0} created successfully from Lead").format(
                frappe.get_desk_link("Opportunity", opportunity.name)
            ),
            indicator="green",
            alert=True,
        )

        # Log audit entry
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Info",
                "reference_doctype": "Lead",
                "reference_name": lead.name,
                "content": _(
                    "Auto-created Opportunity {0} when Lead workflow_state changed to 'Initiate Job'"
                ).format(opportunity.name),
            }
        ).insert(ignore_permissions=True)

    except Exception as e:
        frappe.log_error(
            title=_("Opportunity Creation Failed for Lead {0}").format(lead.name),
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            _("Failed to create Opportunity: {0}").format(str(e)),
            indicator="red",
            alert=True,
        )


def populate_execution_status(job_file, lead):
    """Initialize the Job Execution Status table with all six stages."""
    # Reset Job Execution Status table
    job_file.set("table_royw", [])

    # Define all six execution stages
    stages = [
        "Technical Survey",
        "Structure Mounting", 
        "Project Installation",
        "Meter Installation",
        "Meter Commissioning",
        "Verification Handover"
    ]

    for stage in stages:
        # At Job File creation time, execution documents don't exist yet
        # They will be created when Job File workflow changes to "Job File Initiated"
        # So we initialize all with "Not Created" status
        job_file.append(
            "table_royw",
            {
                "stage": stage,
                "supplier": None,  # Will be populated when execution documents are created
                "status": "Not Created",
                "referrence_doctype": None,  # Will be set to the actual document name when created
            },
        )


@frappe.whitelist()
def refresh_execution_status(job_file_name):
    """Refresh the execution status table for an existing Job File with all six stages."""
    job_file = frappe.get_doc("Job File", job_file_name)
    
    # Get the linked Lead
    lead = frappe.get_doc("Lead", job_file.lead) if job_file.lead else None
    
    # Re-populate the execution status table
    populate_execution_status(job_file, lead)
    
    # Save the Job File
    job_file.save(ignore_permissions=True)
    
    frappe.msgprint(
        f"Execution status table refreshed for Job File {job_file_name}. Now showing all 6 stages.",
        indicator="green",
        alert=True
    )
    
    return "Success"


def set_lead_owner(lead, allow_override=True, final=False):
    """
    Set Lead Owner to the current user.
    
    Args:
        lead: Lead document
        allow_override: If True, only set if not already set. If False, always override.
        final: If True, this is the final owner assignment (on Mark Qualified)
    """

    current_user = frappe.session.user
    
    print(f"\n=== set_lead_owner called ===")
    print(f"Lead: {lead.name}")
    print(f"Current User: {current_user}")
    print(f"Allow Override: {allow_override}")
    print(f"Final Assignment: {final}")

    # Lead has a standard field 'lead_owner'
    current_owner = lead.get("lead_owner")
    print(f"Current Owner: {current_owner}")

    # If allow_override is True and owner is already set, don't change
    if allow_override and current_owner:
        print(f"Lead owner already set to: {current_owner}, not overriding")
        return

    # Set the value directly on the document
    lead.db_set("lead_owner", current_user, update_modified=False)
    
    action_type = "FINAL" if final else "temporary"
    print(f"✓ Lead owner set to: {current_user} ({action_type})")
    
    message = f"Lead Owner set to {frappe.utils.get_fullname(current_user)}"
    if final:
        message += " (Final - Cannot be changed)"
    
    frappe.msgprint(
        message,
        indicator="green",
        alert=True,
    )


def get_user_from_sales_person(sales_person_name):
    """
    Resolve User email from Sales Person via Employee linkage.
    Sales Person → Employee → user_id
    
    Args:
        sales_person_name: Name of the Sales Person
        
    Returns:
        str: User email or None if not found/linked
    """
    if not sales_person_name:
        return None
    
    # Primary: Get employee from Sales Person.employee field
    employee = frappe.db.get_value("Sales Person", sales_person_name, "employee")
    
    # Fallback: Check if Employee has sales_person field pointing back
    if not employee:
        employee = frappe.db.get_value("Employee", {"sales_person": sales_person_name}, "name")
    
    if not employee:
        frappe.logger().warning(
            f"Sales Person '{sales_person_name}' has no linked Employee. "
            "Cannot resolve user for ToDo assignment."
        )
        return None
    
    # Get user_id from Employee
    user_id = frappe.db.get_value("Employee", employee, "user_id")
    
    if not user_id:
        frappe.logger().warning(
            f"Employee '{employee}' (linked to Sales Person '{sales_person_name}') "
            "has no user_id. Cannot assign ToDo."
        )
        return None
    
    return user_id


def assign_active_sales_manager(doc):
    """
    Create ToDo for Active Sales Manager.
    - Resolves Sales Person → Employee → User
    - Closes any stale "Start Job File" ToDo for this Lead (when manager changes)
    - Creates new ToDo for the new manager
    - Note: lead_owner is set separately by workflow button clicks (Contacted/Qualified)
    
    Args:
        doc: Lead document
    """
    sales_person = doc.get("custom_active_sales_manager")
    if not sales_person:
        return
    
    # Resolve user from Sales Person
    user = get_user_from_sales_person(sales_person)
    if not user:
        # Warning already logged in helper function
        return
    
    # Validate user is enabled
    user_enabled = frappe.db.get_value("User", user, "enabled")
    if not user_enabled:
        frappe.logger().warning(
            f"User '{user}' (linked to Sales Person '{sales_person}') is disabled. "
            "Skipping ToDo assignment."
        )
        return
    
    # Close any existing open "Start Job File" ToDo for this Lead (cleanup on manager change)
    existing_todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Lead",
            "reference_name": doc.name,
            "status": "Open",
            "description": ["like", "%Start Job File%"],
        },
        fields=["name", "allocated_to"],
    )
    
    for todo in existing_todos:
        # Close old ToDos (whether same user or different user)
        frappe.db.set_value("ToDo", todo.name, "status", "Closed", update_modified=False)
        frappe.logger().info(
            f"Closed ToDo {todo.name} for Lead {doc.name} (manager changed/reassigned)"
        )
    
    # Duplicate guard: Check if an open ToDo already exists for this exact user + Lead combo
    # (shouldn't happen after the cleanup above, but defensive check)
    existing_open_todo = frappe.db.exists(
        "ToDo",
        {
            "reference_type": "Lead",
            "reference_name": doc.name,
            "allocated_to": user,
            "status": "Open",
        },
    )
    
    if existing_open_todo:
        # Already have an open ToDo for this user - don't create duplicate
        frappe.logger().info(
            f"Open ToDo already exists for user {user} on Lead {doc.name}. Skipping creation."
        )
    else:
        # Create new ToDo
        description = _("Start Job File – {0}").format(doc.name)
        
        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": user,
                "reference_type": "Lead",
                "reference_name": doc.name,
                "description": description,
                "priority": "High",
                "status": "Open",
            }
        )
        todo.flags.ignore_permissions = True
        todo.insert()
        frappe.db.commit()
        
        frappe.logger().info(
            f"Created ToDo for Sales Manager {user} on Lead {doc.name}"
        )
    
    # Show success message
    user_fullname = frappe.utils.get_fullname(user) or user
    frappe.msgprint(
        _("Active Sales Manager assigned: {0}. ToDo created.").format(
            user_fullname
        ),
        indicator="green",
        alert=True,
    )
