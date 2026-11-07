import frappe
from frappe.model.document import Document


class RetailerAssignmentHistory(Document):
    def before_insert(self):
        if not self.flags.clothing_assignment_event:
            frappe.throw(
                frappe._(
                    "Assignment history can only be created by the reassignment action."
                ),
                frappe.PermissionError,
            )

    def validate(self):
        if not self.is_new():
            frappe.throw(frappe._("Retailer assignment history is immutable."))
