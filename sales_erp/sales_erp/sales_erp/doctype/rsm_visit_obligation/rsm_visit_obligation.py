"""RSM Visit Obligation controller managing structured 80-day cadence tracking."""

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate, now_datetime

from sales_erp.security import (
    assigned_sales_territories,
    get_current_user,
    get_user_roles,
    is_clothing_admin,
    is_sales_manager,
)


class RSMVisitObligation(Document):
    def validate(self):
        if not self.cycle_id and self.customer and self.cycle_start:
            self.cycle_id = f"{self.customer}-{self.cycle_start}"

        if self.cycle_start and self.due_date and getdate(self.due_date) < getdate(self.cycle_start):
            frappe.throw(frappe._("Target due date cannot be earlier than cycle start."))

        if self.due_date and self.grace_end_date and getdate(self.grace_end_date) < getdate(self.due_date):
            frappe.throw(frappe._("Grace end date cannot be earlier than target due date."))

        if self.status == "Satisfied":
            if not self.satisfied_on:
                self.satisfied_on = now_datetime()
            if not self.satisfied_by:
                self.satisfied_by = get_current_user()


def rsm_visit_obligation_query_conditions(user=None):
    """Restrict RSM and ASM visibility to obligations within their assigned territories."""
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return ""
    territories = assigned_sales_territories(user)
    if not territories:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(t) for t in territories)
    return (
        f"(`tabRSM Visit Obligation`.`territory` IN ({escaped}) "
        f"OR `tabRSM Visit Obligation`.`assigned_rsm` = {frappe.db.escape(user)} "
        f"OR `tabRSM Visit Obligation`.`assigned_asm` = {frappe.db.escape(user)})"
    )


def rsm_visit_obligation_has_permission(doc, user=None, ptype=None, **kwargs):
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return True
    if ptype in ("create", "delete", "write") and not is_clothing_admin(user):
        return False
    territories = set(assigned_sales_territories(user))
    doc_territory = getattr(doc, "territory", None)
    if doc_territory and doc_territory in territories:
        return True
    if getattr(doc, "assigned_rsm", None) == user or getattr(doc, "assigned_asm", None) == user:
        return True
    return False
