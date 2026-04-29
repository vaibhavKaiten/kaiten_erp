import frappe
from frappe import _
from frappe.utils import today, add_days, date_diff


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Contract No"), "fieldname": "name", "fieldtype": "Link", "options": "AMC Contract", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Site"), "fieldname": "site_name", "fieldtype": "Data", "width": 200},
		{"label": _("Capacity (kWp)"), "fieldname": "system_capacity", "fieldtype": "Float", "width": 110},
		{"label": _("Contract Type"), "fieldname": "contract_type", "fieldtype": "Data", "width": 120},
		{"label": _("Start Date"), "fieldname": "start_date", "fieldtype": "Date", "width": 100},
		{"label": _("End Date"), "fieldname": "end_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Contract Value"), "fieldname": "contract_value", "fieldtype": "Currency", "width": 130},
		{"label": _("Renewal Notice"), "fieldname": "renewal_notice", "fieldtype": "Data", "width": 130},
	]


def get_data(filters):
	filters = filters or {}
	days_ahead = int(filters.get("days_ahead", 90))
	expiry_cutoff = add_days(today(), days_ahead)

	contracts = frappe.db.sql(
		"""
		SELECT
			ac.name,
			ac.customer,
			ac.contract_type,
			ac.start_date,
			ac.end_date,
			ac.contract_value,
			ac.solar_site,
			sp.site_name,
			sp.system_capacity
		FROM `tabAMC Contract` ac
		LEFT JOIN `tabSolar Site Profile` sp ON sp.name = ac.solar_site
		WHERE ac.docstatus = 1
			AND ac.status = 'Active'
			AND ac.end_date <= %s
			AND ac.end_date >= %s
		ORDER BY ac.end_date ASC
		""",
		(expiry_cutoff, today()),
		as_dict=True,
	)

	data = []
	for row in contracts:
		days_left = date_diff(row.end_date, today())
		renewal_notice = frappe.db.get_value(
			"Renewal Notice",
			{"amc_contract": row.name, "docstatus": ["!=", 2]},
			"name",
		)
		data.append({
			"name": row.name,
			"customer": row.customer,
			"site_name": row.site_name or "",
			"system_capacity": row.system_capacity or 0,
			"contract_type": row.contract_type,
			"start_date": row.start_date,
			"end_date": row.end_date,
			"days_left": days_left,
			"contract_value": row.contract_value,
			"renewal_notice": renewal_notice or "—",
		})

	return data
