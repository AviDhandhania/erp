# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class QualityInspectionEvidence(Document):
    def validate(self):
        if not self.uploader:
            self.uploader = frappe.session.user
        if not self.uploaded_on:
            self.uploaded_on = frappe.utils.now_datetime()
        if not self.revision:
            self.revision = 1
