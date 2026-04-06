# Copyright (c) 2026, Vaibhav and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from kaiten_erp.kaiten_erp.api.gps import log_workflow_location


class StructureMounting(Document):
    def autoname(self):
        k_no = self.custom_k_number

        if not k_no:
            frappe.throw("K Number is required")
        series = make_autoname(".####")
        self.name = f"{self.custom_first_name}-{k_no}-{series}"

    def validate(self):
        log_workflow_location(self)
