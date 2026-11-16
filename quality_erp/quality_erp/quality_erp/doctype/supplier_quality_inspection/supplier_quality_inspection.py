import frappe
from frappe.model.document import Document
from quality_erp.security import assert_can_approve_quality_gate, get_current_user


class SupplierQualityInspection(Document):
    def validate(self):
        if not self.inspector:
            self.inspector = get_current_user()

        # Enforce server-side security gate check if status is set to Approved
        if self.status == "Approved" and self.has_value_changed("status"):
            assert_can_approve_quality_gate(self.stage)
