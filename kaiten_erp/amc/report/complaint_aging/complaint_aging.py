import frappe
from frappe import _
from frappe.utils import now_datetime, date_diff, today


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Complaint No"), "fieldname": "name", "fieldtype": "Link", "options": "Complaint", "width": 140},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Issue Category"), "fieldname": "issue_category", "fieldtype": "Data", "width": 150},
		{"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Reported On"), "fieldname": "reported_on", "fieldtype": "Datetime", "width": 160},
		{"label": _("Days Open"), "fieldname": "days_open", "fieldtype": "Int", "width": 90},
		{"label": _("SLA Deadline"), "fieldname": "sla_deadline", "fieldtype": "Datetime", "width": 160},
		{"label": _("SLA Status"), "fieldname": "sla_status", "fieldtype": "Data", "width": 120},
		{"label": _("Assigned To"), "fieldname": "assigned_to", "fieldtype": "Link", "options": "Employee", "width": 150},
	]


def get_data(filters):
	filters = filters or {}
	status_filter = filters.get("status") or ["Open", "Assigned", "In Progress", "Escalated"]
	if isinstance(status_filter, str):
		status_filter = [status_filter]

	complaints = frappe.db.sql(
		"""
		SELECT
			name, customer, issue_category, priority, status,
			reported_on, sla_deadline, assigned_to
		FROM `tabComplaint`
		WHERE docstatus < 2
			AND status IN %(statuses)s
		ORDER BY
			FIELD(priority, 'Critical', 'High', 'Medium', 'Low'),
			reported_on ASC
		""",
		{"statuses": status_filter},
		as_dict=True,
	)

	now = now_datetime()
	data = []
	for row in complaints:
		days_open = date_diff(today(), row.reported_on.date()) if row.reported_on else 0

		if row.sla_deadline:
			if now > row.sla_deadline:
				sla_status = "Breached"
			else:
				remaining = int((row.sla_deadline - now).total_seconds() / 3600)
				sla_status = f"OK ({remaining}h left)"
		else:
			sla_status = "No SLA"

		data.append({
			"name": row.name,
			"customer": row.customer,
			"issue_category": row.issue_category,
			"priority": row.priority,
			"status": row.status,
			"reported_on": row.reported_on,
			"days_open": days_open,
			"sla_deadline": row.sla_deadline,
			"sla_status": sla_status,
			"assigned_to": row.assigned_to,
		})

	return data
