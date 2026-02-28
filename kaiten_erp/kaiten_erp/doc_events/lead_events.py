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
    # Check if workflow_state field has changed using has_value_changed
    if doc.has_value_changed("workflow_state"):
        new_workflow_state = doc.workflow_state

        # Check if changed TO "Qualified"
        if new_workflow_state == "Qualified":
            create_job_file_from_lead(doc)


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
    job_file.execution_status = []

    for stage, doctype, vendor_field in [
        ("Technical Survey", "Technical Survey", "custom_assigned_technical_supplier")
        # ("Structure Mounting", "Structure Mounting", "custom_assigned_technical_supplier"),
        # ("Project Installation", "Project Installation", "custom_assigned_technical_supplier"),
        # ("Meter Installation", "Meter Installation", "custom_assigned_meter_supplier"),
        # ("Meter Commissioning", "Meter Commissioning", "custom_assigned_meter_supplier"),
        # ("Verification Handover", "Verification Handover", "custom_assigned_technical_supplier"),
    ]:
        vendor = job_file.get(vendor_field)

        # Fetch related execution document if it exists
        existing_doc = frappe.get_all(
            doctype,
            filters={"custom_job_file": job_file.name, "custom_lead": lead.name},
            fields=["name", "workflow_state"],
            limit=1,
        )

        status = existing_doc[0].workflow_state if existing_doc else "Not Created"

        job_file.append(
            "table_royw",
            {
                "stage": stage,
                "supplier": vendor,
                "status": status,
                "referrence_doctype": doctype,
            },
        )


8
