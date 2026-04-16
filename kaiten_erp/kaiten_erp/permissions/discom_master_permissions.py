# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

"""
DISCOM Master — Document-level Permission Check.

Only DISCOM Manager (and System Manager / Administrator) can access DISCOM Master records.
All other roles see nothing.
"""

import frappe


def has_permission(doc, ptype=None, user=None):
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)

	if any(r in roles for r in ["System Manager", "Administrator"]):
		return True

	if "DISCOM Manager" in roles:
		return True

	return False


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)

	if any(r in roles for r in ["System Manager", "Administrator"]):
		return ""  # No restriction for admins

	if "DISCOM Manager" in roles:
		return ""  # DISCOM Manager can see all records

	return "1=0"  # All other roles see nothing
