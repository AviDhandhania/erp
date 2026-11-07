import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from clothing_erp.roles import ROLE_SALESPERSON
from clothing_erp.security import get_current_user, get_user_roles, has_retailer_access, is_sales_manager


class RetailerVisit(Document):
    def validate(self):
        if ROLE_SALESPERSON in get_user_roles() and not is_sales_manager():
            self.salesperson = get_current_user()
            if not has_retailer_access(self.customer):
                frappe.throw(frappe._("You do not have access to this retailer."), frappe.PermissionError)
        if self.outcome == "Follow-up Required" and not self.follow_up_date:
            frappe.throw(frappe._("Follow-up Date is required for this outcome."))
        if self.follow_up_date and getdate(self.follow_up_date) < getdate(nowdate()):
            frappe.throw(frappe._("Follow-up Date cannot be in the past."))
