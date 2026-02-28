# Copyright (c) 2026, Vaibhav and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from kaiten_erp.kaiten_erp.api.gps import log_workflow_location


class VerificationHandover(Document):
    def validate(self):
        log_workflow_location(self)
