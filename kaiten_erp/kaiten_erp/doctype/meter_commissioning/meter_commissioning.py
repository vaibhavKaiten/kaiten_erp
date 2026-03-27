# Copyright (c) 2026, up411@gmail.com and contributors
# For license information, please see license.txt


from frappe.model.document import Document
from frappe.model.naming import make_autoname

class MeterCommissioning(Document):
    def autoname(self):
        k_no = self.custom_k_number

        if not k_no:
            frappe.throw("K Number is required")
        series = make_autoname(".####")
        self.name = f"{self.first_name}-{k_no}-{series}"