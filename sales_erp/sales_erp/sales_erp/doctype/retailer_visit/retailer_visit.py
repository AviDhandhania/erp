import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, nowdate

from sales_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from sales_erp.security import (
    get_current_user,
    get_user_roles,
    has_retailer_access,
    is_clothing_admin,
    is_sales_manager,
    require_role,
)
from sales_erp.supervision import (
    assert_rsm_supervises_asm,
    get_active_supervising_rsm,
    get_territory_supervision,
)


class RetailerVisit(Document):
    def validate(self):
        user = get_current_user()
        roles = get_user_roles()
        admin = is_clothing_admin(user)

        # 1. Retailer Access Check
        if not admin and not has_retailer_access(self.customer, user):
            frappe.throw(frappe._("You do not have access to this retailer."), frappe.PermissionError)

        # 2. ASM vs RSM Scoping
        if ROLE_SALESPERSON in roles and not is_sales_manager(user) and not admin:
            self.salesperson = user
            self.visitor_role = "Area Sales Manager"

            if self.visit_type == "RSM Periodic Review":
                frappe.throw(
                    frappe._("Area Sales Managers cannot file an RSM Periodic Review."),
                    frappe.PermissionError,
                )

            # Auto-populate supervising RSM from active ASM Supervision
            supervising_rsm = get_active_supervising_rsm(self.salesperson)
            if supervising_rsm:
                self.rsm = supervising_rsm
            else:
                customer_territory = frappe.db.get_value("Customer", self.customer, "territory")
                if customer_territory:
                    supervision = get_territory_supervision(customer_territory)
                    if supervision and supervision.rsm:
                        self.rsm = supervision.rsm

            if not self.review_status:
                self.review_status = "Submitted"

        elif is_sales_manager(user) and not admin:
            if not self.salesperson or self.salesperson == user:
                self.salesperson = user
                self.visitor_role = "Regional Sales Manager"
                self.rsm = user
                if not self.review_status or self.review_status == "Submitted":
                    self.review_status = "Reviewed by RSM"
                    self.reviewed_by = user
                    self.reviewed_on = now_datetime()

        # 3. Follow-up Date Validations
        if self.outcome == "Follow-up Required" and not self.follow_up_date:
            frappe.throw(frappe._("Follow-up Date is required for this outcome."))
        if self.follow_up_date and getdate(self.follow_up_date) < getdate(nowdate()):
            frappe.throw(frappe._("Follow-up Date cannot be in the past."))

    def on_update(self):
        # Fulfill/close RSM visit obligation if this is a qualifying RSM visit
        if self.visitor_role == "Regional Sales Manager" or self.visit_type == "RSM Periodic Review":
            try:
                from sales_erp.cadence import close_rsm_visit_obligation
                close_rsm_visit_obligation(self.customer, self.salesperson or self.rsm)
            except Exception:
                pass


@frappe.whitelist(methods=["POST"])
def review_visit(name, status, notes=None):
    """Supervising RSM or Administrator reviews an ASM's Retailer Visit."""
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    doc = frappe.get_doc("Retailer Visit", name)
    doc.check_permission("write")

    if not is_clothing_admin(user):
        assert_rsm_supervises_asm(user, doc.salesperson)

    valid_statuses = {"Reviewed by RSM", "Action Required"}
    if status not in valid_statuses:
        frappe.throw(
            frappe._("Invalid review status '{0}'. Must be one of: {1}").format(
                status, ", ".join(valid_statuses)
            ),
            frappe.ValidationError,
        )

    doc.review_status = status
    doc.reviewed_by = user
    doc.reviewed_on = now_datetime()
    doc.review_notes = (notes or "").strip()
    doc.save(ignore_permissions=True)

    return {
        "name": doc.name,
        "review_status": doc.review_status,
        "reviewed_by": doc.reviewed_by,
        "reviewed_on": doc.reviewed_on,
        "review_notes": doc.review_notes,
    }
