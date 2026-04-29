import frappe
from frappe import _
from frappe.utils import today, add_days


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Visit No"), "fieldname": "name", "fieldtype": "Link", "options": "Service Visit", "width": 140},
		{"label": _("Scheduled Date"), "fieldname": "scheduled_date", "fieldtype": "Date", "width": 110},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Site"), "fieldname": "site_name", "fieldtype": "Data", "width": 200},
		{"label": _("Visit Type"), "fieldname": "visit_type", "fieldtype": "Data", "width": 120},
		{"label": _("Technician"), "fieldname": "technician", "fieldtype": "Link", "options": "Employee", "width": 160},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Contract"), "fieldname": "amc_contract", "fieldtype": "Link", "options": "AMC Contract", "width": 140},
	]


def get_data(filters):
	filters = filters or {}
	from_date = filters.get("from_date") or today()
	to_date = filters.get("to_date") or add_days(today(), 60)
	technician = filters.get("technician")

	conditions = "sv.scheduled_date >= %(from_date)s AND sv.scheduled_date <= %(to_date)s"
	params = {"from_date": from_date, "to_date": to_date}

	if technician:
		conditions += " AND sv.technician = %(technician)s"
		params["technician"] = technician

	visits = frappe.db.sql(
		f"""
		SELECT
			sv.name,
			sv.scheduled_date,
			sv.customer,
			sv.solar_site,
			sv.visit_type,
			sv.technician,
			sv.status,
			sv.amc_contract,
			sp.site_name
		FROM `tabService Visit` sv
		LEFT JOIN `tabSolar Site Profile` sp ON sp.name = sv.solar_site
		WHERE sv.docstatus < 2
			AND sv.status IN ('Scheduled', 'In Progress')
			AND {conditions}
		ORDER BY sv.scheduled_date ASC
		""",
		params,
		as_dict=True,
	)

	data = []
	for row in visits:
		data.append({
			"name": row.name,
			"scheduled_date": row.scheduled_date,
			"customer": row.customer,
			"site_name": row.site_name or "",
			"visit_type": row.visit_type,
			"technician": row.technician,
			"status": row.status,
			"amc_contract": row.amc_contract,
		})

	return data
