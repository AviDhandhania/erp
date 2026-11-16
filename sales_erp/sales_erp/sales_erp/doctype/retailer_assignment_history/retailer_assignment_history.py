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
        if self.previous_asm and not self.previous_salesperson:
            self.previous_salesperson = self.previous_asm
        if self.new_asm and not self.new_salesperson:
            self.new_salesperson = self.new_asm
        if self.previous_salesperson and not self.previous_asm:
            self.previous_asm = self.previous_salesperson
        if self.new_salesperson and not self.new_asm:
            self.new_asm = self.new_salesperson

    def validate(self):
        if not self.is_new():
            frappe.throw(frappe._("Retailer assignment history is immutable."))
