# Copyright (c) 2026, Vaibhav and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from kaiten_erp.kaiten_erp.api.gps import log_workflow_location
from ...permissions.vendor_permissions import get_supplier_users


class StructureMounting(Document):
    def validate(self):
        log_workflow_location(self)

    def on_change(self):
        """
        Triggered when field values change (after commit)
        Used to detect workflow_state changes and trigger auto-assignment
        """
        # Check if workflow_state changed to 'Assigned to Vendor'
        if self.has_value_changed('workflow_state'):
            if self.workflow_state == "Assigned to Vendor":
                self._auto_assign_to_vendor_managers()

    def _auto_assign_to_vendor_managers(self):
        """
        Automatically assign the Structure Mounting to all Vendor Managers
        linked to the assigned_vendor supplier company.
        
        Steps:
        1. Find all users with 'Vendor Manager' role for the supplier
        2. Share the document with write access
        3. Create ToDo assignments for each manager
        """
        if not self.assigned_vendor:
            return

        # Get all users with "Vendor Manager" role linked to this supplier
        vendor_managers = get_supplier_users(self.assigned_vendor, role="Vendor Manager")

        if not vendor_managers:
            frappe.msgprint(
                f"No users with 'Vendor Manager' role found for supplier: {self.assigned_vendor}"
            )
            return

        # Assign to each vendor manager
        for manager in vendor_managers:
            # Share document with write access
            frappe.share.add(
                doctype=self.doctype,
                name=self.name,
                user=manager,
                perm_level=1,
                write=1,
                flags={"ignore_share_permission": True}
            )

            # Create ToDo assignment
            customer_name = self._get_customer_display_name()
            if customer_name:
                description = f"Structure mounting for customer: {customer_name}"
            else:
                description = f"Structure mounting - {self.name}"
            
            todo = frappe.get_doc({
                "doctype": "ToDo",
                "title": f"Structure Mounting - {self.name}",
                "description": description,
                "reference_type": "Structure Mounting",
                "reference_name": self.name,
                "allocated_to": manager,
                "assigned_by": frappe.session.user,
                "status": "Open"
            })
            todo.insert(ignore_permissions=True)

    def _get_customer_display_name(self):
        first_name = getattr(self, "first_name", None) or getattr(self, "custom_first_name", None)
        last_name = getattr(self, "last_name", None) or getattr(self, "custom_last_name", None)
        full_name = " ".join(filter(None, [first_name, last_name])).strip()
        if full_name:
            return full_name

        if self.customer:
            customer_name = frappe.db.get_value("Customer", self.customer, "customer_name")
            if customer_name:
                return customer_name

        if self.lead:
            lead_name = frappe.db.get_value("Lead", self.lead, "lead_name")
            if lead_name:
                return lead_name

        return None
