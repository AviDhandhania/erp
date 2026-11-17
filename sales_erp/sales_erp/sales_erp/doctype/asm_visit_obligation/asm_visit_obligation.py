"""ASM Visit Obligation controller managing SIS quarterly/monthly and Buy & Sell cadences."""

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from sales_erp.security import (
    assigned_sales_territories,
    get_current_user,
    is_clothing_admin,
    is_sales_manager,
)


class ASMVisitObligation(Document):
    def validate(self):
        if not self.cycle_id and self.customer and self.cycle_start and self.obligation_type:
            self.cycle_id = f"{self.customer}-{self.obligation_type}-{self.cycle_start}"

        if self.cycle_start and self.due_date and getdate(self.due_date) < getdate(self.cycle_start):
            frappe.throw(frappe._("Target due date cannot be earlier than cycle start."))

        if self.due_date and self.grace_end_date and getdate(self.grace_end_date) < getdate(self.due_date):
            frappe.throw(frappe._("Grace end date cannot be earlier than target due date."))

        if self.status == "Satisfied":
            if not self.satisfied_on:
                self.satisfied_on = now_datetime()
            if not self.satisfied_by:
                self.satisfied_by = get_current_user()


def asm_visit_obligation_query_conditions(user=None):
    """Restrict ASM and RSM visibility to obligations within their assigned territories."""
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return ""
    territories = assigned_sales_territories(user)
    if not territories:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(t) for t in territories)
    return (
        f"(`tabASM Visit Obligation`.`territory` IN ({escaped}) "
        f"OR `tabASM Visit Obligation`.`assigned_asm` = {frappe.db.escape(user)} "
        f"OR `tabASM Visit Obligation`.`supervising_rsm` = {frappe.db.escape(user)})"
    )


def asm_visit_obligation_has_permission(doc, user=None, ptype=None, **kwargs):
    """Document-level permission checking for ASM Visit Obligation."""
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return True

    territories = assigned_sales_territories(user)
    if doc.territory and doc.territory in territories:
        return True

    if doc.assigned_asm == user or doc.supervising_rsm == user:
        return True

    return False
