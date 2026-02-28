# Copyright (c) 2026, Kaiten Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from kaiten_erp.kaiten_erp.api.gps import log_workflow_location


class TechnicalSurvey(Document):
    def validate(self):
        self._normalize_schedule_slot()
        log_workflow_location(self)

    def _normalize_schedule_slot(self):
        """Prevent invalid multiline Select value from blocking workflow save."""
        value = (self.get("data_tila") or "").strip()
        if not value:
            return

        field = self.meta.get_field("data_tila")
        if not field or field.fieldtype != "Select":
            return

        valid_options = [opt.strip() for opt in (field.options or "").split("\n") if opt.strip()]
        if value in valid_options:
            return

        for part in [v.strip() for v in value.split("\n") if v.strip()]:
            if part in valid_options:
                self.set("data_tila", part)
                return
