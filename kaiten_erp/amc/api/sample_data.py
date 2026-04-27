import frappe
from frappe.utils import add_days, getdate, today


def get_or_create_customer():
    customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
    if customer:
        return customer

    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": "Sample AMC Customer",
        "customer_type": "Company",
        "customer_group": "Commercial",
        "territory": "All Territories"
    })
    customer.insert(ignore_permissions=True)
    frappe.db.commit()
    return customer.name


def get_or_create_employee():
    employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")
    if employee:
        return employee

    employee = frappe.get_doc({
        "doctype": "Employee",
        "employee_name": "Sample AMC Technician",
        "status": "Active"
    })
    employee.insert(ignore_permissions=True)
    frappe.db.commit()
    return employee.name


def get_or_create_item():
    item = frappe.db.get_value("Item", {}, "name")
    if item:
        return item

    item_group = frappe.db.get_value("Item Group", {}, "name")
    if not item_group:
        item_group = "All Item Groups"

    item = frappe.get_doc({
        "doctype": "Item",
        "item_code": "AMC-SAMPLE-ITEM",
        "item_name": "AMC Sample Item",
        "is_stock_item": 0,
        "item_group": item_group,
        "stock_uom": "Nos"
    })
    item.insert(ignore_permissions=True)
    frappe.db.commit()
    return item.name


def get_or_create_job_file(customer):
    job_file = frappe.db.get_value("Job File", {}, "name")
    if job_file:
        return job_file

    job_file = frappe.get_doc({
        "doctype": "Job File",
        "customer": customer,
        "k_number": "JOB-SAMPLE-0001",
        "job_priority": "Medium"
    })
    job_file.insert(ignore_permissions=True)
    frappe.db.commit()
    return job_file.name


def get_or_create_address(customer):
    address = frappe.db.get_value(
        "Address",
        {"address_title": "Sample Site Address"},
        "name"
    )
    if address:
        return address

    address = frappe.get_doc({
        "doctype": "Address",
        "address_title": "Sample Site Address",
        "address_line1": "123 Sample Street",
        "city": "Sample City",
        "state": "Karnataka",
        "country": "India",
        "address_type": "Office",
        "links": [
            {
                "link_doctype": "Customer",
                "link_name": customer
            }
        ]
    })
    address.insert(ignore_permissions=True)
    frappe.db.commit()
    return address.name


def create_sample_data():
    customer = get_or_create_customer()
    employee = get_or_create_employee()
    item = get_or_create_item()
    job_file = get_or_create_job_file(customer)
    address = get_or_create_address(customer)

    site = frappe.get_doc({
        "doctype": "Solar Site Profile",
        "site_name": "Sample AMC Site",
        "job_file": job_file,
        "customer": customer,
        "site_type": "Commercial",
        "address": address,
        "status": "Active",
        "system_capacity": 15,
        "no_of_panels": 45,
        "inverter_make": "Sample Inverter",
        "inverter_model": "SI-5000",
        "inverter_serial_no": "INV-12345",
        "installation_date": getdate(today()),
        "notes": "Created for AMC sample data."
    })
    site.insert(ignore_permissions=True)
    frappe.db.commit()

    contract = frappe.get_doc({
        "doctype": "AMC Contract",
        "naming_series": "AMC-.YYYY.-.#####",
        "customer": customer,
        "solar_site": site.name,
        "contract_type": "Premium",
        "status": "Draft",
        "start_date": today(),
        "end_date": add_days(today(), 365),
        "contract_value": 120000,
        "visits_per_year": 4,
        "includes_inverter": 1,
        "includes_cleaning": 1,
        "parts_limit": 15000,
        "sla_response_hours": 24,
        "sla_resolution_hours": 72,
        "assigned_manager": frappe.session.user,
        "notes": "Sample AMC contract for a commercial site."
    })
    contract.insert(ignore_permissions=True)
    frappe.db.commit()

    visit = frappe.get_doc({
        "doctype": "Service Visit",
        "naming_series": "SV-.YYYY.-.#####",
        "amc_contract": contract.name,
        "visit_type": "Preventive",
        "status": "Scheduled",
        "scheduled_date": add_days(today(), 7),
        "scheduled_time": "10:00:00",
        "technician": employee,
        "work_done": "Performed preventive inspection and cleaned panels.",
        "checklist": [
            {"check_item": "PV string health", "category": "Performance", "status": "OK", "remarks": "All strings healthy."},
            {"check_item": "Inverter status", "category": "Electrical", "status": "OK", "remarks": "No faults detected."}
        ],
        "parts_used": [
            {"item": item, "qty": 1, "rate": 5000, "billable": 0}
        ]
    })
    visit.insert(ignore_permissions=True)
    frappe.db.commit()

    complaint = frappe.get_doc({
        "doctype": "Complaint",
        "naming_series": "CMP-.YYYY.-.#####",
        "customer": customer,
        "solar_site": site.name,
        "amc_contract": contract.name,
        "source": "Call",
        "priority": "High",
        "status": "Open",
        "issue_category": "No Generation",
        "description": "Customer reports zero solar output from the array since this morning.",
        "assigned_to": employee,
        "notes": "Sample complaint linked to AMC contract."
    })
    complaint.insert(ignore_permissions=True)
    frappe.db.commit()

    renewal = frappe.get_doc({
        "doctype": "Renewal Notice",
        "naming_series": "RNW-.YYYY.-.#####",
        "amc_contract": contract.name,
        "proposed_value": 125000,
        "status": "Pending"
    })
    renewal.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "customer": customer,
        "employee": employee,
        "job_file": job_file,
        "site": site.name,
        "contract": contract.name,
        "visit": visit.name,
        "complaint": complaint.name,
        "renewal_notice": renewal.name
    }
