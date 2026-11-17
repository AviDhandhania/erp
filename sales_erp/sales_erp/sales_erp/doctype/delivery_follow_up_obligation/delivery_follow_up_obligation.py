"""Delivery Follow-Up Obligation controller."""

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from sales_erp.security import get_current_user


class DeliveryFollowUpObligation(Document):
    def validate(self):
        if self.posting_date and self.due_date and getdate(self.due_date) < getdate(self.posting_date):
            frappe.throw(frappe._("Follow-up due date cannot be earlier than dispatch date."))

        if self.status in ("Satisfied", "Issue Escalated"):
            if not self.outcome:
                frappe.throw(frappe._("Delivery outcome must be recorded before completing follow-up."))
            if not self.satisfied_on:
                self.satisfied_on = now_datetime()
            if not self.satisfied_by:
                self.satisfied_by = get_current_user()
            if not self.contact_datetime:
                self.contact_datetime = now_datetime()
