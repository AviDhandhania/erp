import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from clothing_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from clothing_erp.security import (
    get_current_user,
    get_user_roles,
    has_retailer_access,
    is_clothing_admin,
    is_sales_manager,
    require_role,
)


def get_customer_current_credit_limit(customer_name: str, company: str | None = None) -> float:
    """Retrieve the current credit limit configured for a customer and company in ERPNext."""
    if not company:
        company = (
            frappe.defaults.get_user_default("Company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
        )
        if not company:
            companies = frappe.get_all("Company", limit=1, pluck="name")
            company = companies[0] if companies else None
    if not company or not customer_name:
        return 0.0

    limits = frappe.db.sql(
        """
        SELECT credit_limit
        FROM `tabCustomer Credit Limit`
        WHERE parent = %s AND company = %s
        LIMIT 1
        """,
        (customer_name, company),
        as_dict=True,
    )
    if limits:
        return flt(limits[0].credit_limit)
    return 0.0


def set_customer_credit_limit(customer_name: str, new_limit: float, company: str | None = None):
    """Atomically set the customer credit limit in native ERPNext Customer Credit Limit table."""
    if not company:
        company = (
            frappe.defaults.get_user_default("Company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
        )
        if not company:
            companies = frappe.get_all("Company", limit=1, pluck="name")
            company = companies[0] if companies else None
    if not company:
        frappe.throw(_("Company is required to set credit limit."))

    cust = frappe.get_doc("Customer", customer_name)
    found = False
    for row in cust.get("credit_limits", []):
        if row.company == company:
            row.credit_limit = flt(new_limit)
            found = True
            break
    if not found:
        cust.append("credit_limits", {"company": company, "credit_limit": flt(new_limit)})

    cust.flags.ignore_permissions = True
    cust.save()


class RetailerCreditLimitRequest(Document):
    def before_insert(self):
        user = get_current_user()
        admin = is_clothing_admin(user)

        if not admin and not is_sales_manager(user):
            frappe.throw(
                _("Only Regional Sales Managers or Administrators can propose credit limit changes."),
                frappe.PermissionError,
            )

        if not self.proposer:
            self.proposer = user
        if not self.proposed_on:
            self.proposed_on = now_datetime()
        self.status = "Pending Approval"
        self.approver = None
        self.decided_on = None
        self.rejection_reason = None

        # Prevent duplicate active requests for the same customer & company
        existing_pending = frappe.db.get_value(
            "Retailer Credit Limit Request",
            {
                "customer": self.customer,
                "company": self.company,
                "status": "Pending Approval",
            },
            "name",
        )
        if existing_pending:
            frappe.throw(
                _("A credit limit request ({0}) is already pending approval for this retailer.").format(
                    existing_pending
                ),
                frappe.ValidationError,
            )

    def validate(self):
        user = get_current_user()
        admin = is_clothing_admin(user)

        # 1. Scope / Retailer Access
        if not admin and not has_retailer_access(self.customer, user):
            frappe.throw(
                _("You do not supervise the territory for retailer {0}.").format(self.customer),
                frappe.PermissionError,
            )

        # 2. Company Resolution
        if not self.company:
            self.company = (
                frappe.defaults.get_user_default("Company")
                or frappe.db.get_single_value("Global Defaults", "default_company")
            )
            if not self.company:
                companies = frappe.get_all("Company", limit=1, pluck="name")
                if companies:
                    self.company = companies[0]

        if not self.company:
            frappe.throw(_("Company is required."))

        # 3. Always capture the authentic current limit server-side on creation or while pending
        if self.is_new() or self.status == "Pending Approval":
            self.current_credit_limit = get_customer_current_credit_limit(self.customer, self.company)

        # 4. Limit validations
        proposed = flt(self.proposed_credit_limit)
        if proposed < 0:
            frappe.throw(_("Proposed credit limit cannot be negative."))
        if self.status == "Pending Approval" and proposed == flt(self.current_credit_limit):
            frappe.throw(
                _("Proposed credit limit ({0}) is identical to the current credit limit.").format(
                    proposed
                ),
                frappe.ValidationError,
            )

        # 5. Non-admins cannot alter decision fields
        if not admin and not self.is_new():
            orig = self.get_doc_before_save()
            if orig and orig.status in ("Approved", "Rejected"):
                frappe.throw(
                    _("Decided credit limit requests cannot be modified."),
                    frappe.PermissionError,
                )


@frappe.whitelist(methods=["POST"])
def approve_credit_limit_request(name):
    """Administrator approves a proposed retailer credit limit change."""
    user = get_current_user()
    if not is_clothing_admin(user):
        frappe.throw(
            _("Only administrators can approve credit limit adjustments."),
            frappe.PermissionError,
        )

    doc = frappe.get_doc("Retailer Credit Limit Request", name)
    if doc.status != "Pending Approval":
        frappe.throw(
            _("Credit limit request {0} is already {1}.").format(name, doc.status),
            frappe.ValidationError,
        )

    doc.status = "Approved"
    doc.approver = user
    doc.decided_on = now_datetime()
    doc.save(ignore_permissions=True)

    # Apply the live change to ERPNext Customer
    set_customer_credit_limit(doc.customer, doc.proposed_credit_limit, doc.company)

    # Notify proposer
    if doc.proposer and doc.proposer != user:
        try:
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "type": "Alert",
                    "for_user": doc.proposer,
                    "document_type": "Retailer Credit Limit Request",
                    "document_name": doc.name,
                    "subject": f"Credit limit change approved for {doc.customer_name or doc.customer}",
                    "email_content": (
                        f"Credit limit change for {doc.customer_name} ({doc.customer}) was approved by {user}. "
                        f"New live limit: ₹{doc.proposed_credit_limit:,.2f}."
                    ),
                }
            ).insert(ignore_permissions=True)
        except Exception:
            pass

    return {
        "name": doc.name,
        "status": "Approved",
        "approver": doc.approver,
        "decided_on": str(doc.decided_on),
        "new_limit": doc.proposed_credit_limit,
    }


@frappe.whitelist(methods=["POST"])
def reject_credit_limit_request(name, reason=None):
    """Administrator rejects a proposed retailer credit limit change."""
    user = get_current_user()
    if not is_clothing_admin(user):
        frappe.throw(
            _("Only administrators can reject credit limit adjustments."),
            frappe.PermissionError,
        )

    doc = frappe.get_doc("Retailer Credit Limit Request", name)
    if doc.status != "Pending Approval":
        frappe.throw(
            _("Credit limit request {0} is already {1}.").format(name, doc.status),
            frappe.ValidationError,
        )

    doc.status = "Rejected"
    doc.approver = user
    doc.decided_on = now_datetime()
    doc.rejection_reason = (reason or "").strip()
    doc.save(ignore_permissions=True)

    # Notify proposer
    if doc.proposer and doc.proposer != user:
        try:
            frappe.get_doc(
                {
                    "doctype": "Notification Log",
                    "type": "Alert",
                    "for_user": doc.proposer,
                    "document_type": "Retailer Credit Limit Request",
                    "document_name": doc.name,
                    "subject": f"Credit limit change rejected for {doc.customer_name or doc.customer}",
                    "email_content": (
                        f"Credit limit change for {doc.customer_name} ({doc.customer}) was rejected by {user}.\n"
                        f"Reason: {doc.rejection_reason or 'No reason provided'}."
                    ),
                }
            ).insert(ignore_permissions=True)
        except Exception:
            pass

    return {
        "name": doc.name,
        "status": "Rejected",
        "approver": doc.approver,
        "decided_on": str(doc.decided_on),
        "rejection_reason": doc.rejection_reason,
    }


@frappe.whitelist(methods=["POST"])
def propose_credit_limit(customer, proposed_limit, reason, company=None, source_visit=None):
    """Convenience API to propose a credit limit adjustment for a retailer."""
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()

    if not is_clothing_admin(user) and not has_retailer_access(customer, user):
        frappe.throw(
            _("You do not supervise the territory for retailer {0}.").format(customer),
            frappe.PermissionError,
        )

    doc = frappe.get_doc(
        {
            "doctype": "Retailer Credit Limit Request",
            "customer": customer,
            "company": company,
            "proposed_credit_limit": flt(proposed_limit),
            "reason": reason,
            "source_visit": source_visit,
        }
    ).insert()

    return {
        "name": doc.name,
        "customer": doc.customer,
        "proposed_credit_limit": doc.proposed_credit_limit,
        "status": doc.status,
    }
