import frappe
from frappe.model.document import Document
from quality_erp.security import get_current_user


class ReturnQuarantine(Document):
    def validate(self):
        if not self.inspected_by:
            self.inspected_by = get_current_user()
