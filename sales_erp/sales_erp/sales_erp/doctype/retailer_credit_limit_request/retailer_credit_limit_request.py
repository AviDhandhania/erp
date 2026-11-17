"""Retailer Credit Limit Request workflow, server-side approval, and audit integrity."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from sales_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from sales_erp.security import (
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

        # 2. Company & Currency Resolution
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

        self.currency = (
            frappe.get_cached_value("Company", self.company, "default_currency")
            or "INR"
        )

        # 3. Disallow client edits to decided requests
        if not self.is_new():
            stored = frappe.db.get_value(
                "Retailer Credit Limit Request",
                self.name,
                ["status", "proposed_credit_limit", "customer", "company", "reason"],
                as_dict=True,
            )
            if stored and stored.status in ("Approved", "Rejected") and not getattr(self.flags, "in_decision_service", False):
                frappe.throw(_("Decided credit limit requests cannot be modified."), frappe.PermissionError)

        # 4. Always capture authentic current limit server-side on creation or while pending
        if self.is_new() or self.status == "Pending Approval":
            self.current_credit_limit = get_customer_current_credit_limit(self.customer, self.company)

        # 5. Proposed limit validation
        if flt(self.proposed_credit_limit) < 0:
            frappe.throw(_("Proposed credit limit cannot be negative."), frappe.ValidationError)

        if flt(self.proposed_credit_limit) == flt(self.current_credit_limit):
            frappe.throw(
                _("Proposed credit limit ({0} {1:,.2f}) must differ from the current limit.").format(
                    self.currency, flt(self.current_credit_limit)
                ),
                frappe.ValidationError,
            )

        if not (self.reason or "").strip():
            frappe.throw(_("A valid reason/justification is required."), frappe.ValidationError)


@frappe.whitelist(methods=["POST"])
def approve_credit_limit_request(name):
    """Administrator approves a proposed retailer credit limit change with row-locking and live limit checks."""
    user = get_current_user()
    if not is_clothing_admin(user):
        frappe.throw(
            _("Only administrators can approve credit limit adjustments."),
            frappe.PermissionError,
        )

    # Row-lock transition
    rows = frappe.db.sql(
        """
        SELECT name, status, current_credit_limit, proposed_credit_limit, customer, company, currency, proposer, customer_name
        FROM `tabRetailer Credit Limit Request`
        WHERE name = %s
        FOR UPDATE
        """,
        (name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Credit limit request {0} does not exist.").format(name), frappe.DoesNotExistError)

    req = rows[0]
    if req.status != "Pending Approval":
        frappe.throw(
            _("Credit limit request {0} is already {1}.").format(name, req.status),
            frappe.ValidationError,
        )

    # Detect live ERPNext Customer credit limit changes
    live_limit = get_customer_current_credit_limit(req.customer, req.company)
    if flt(live_limit) != flt(req.current_credit_limit):
        frappe.throw(
            _("The live credit limit for customer {0} changed to {1:,.2f} while this request was pending approval. "
              "Please review the live limit before approving.").format(req.customer, flt(live_limit)),
            frappe.ValidationError,
        )

    doc = frappe.get_doc("Retailer Credit Limit Request", name)
    doc.flags.in_decision_service = True
    doc.status = "Approved"
    doc.approver = user
    doc.decided_on = now_datetime()
    doc.save(ignore_permissions=True)

    # Apply the live change to ERPNext Customer
    set_customer_credit_limit(doc.customer, doc.proposed_credit_limit, doc.company)

    # Notify proposer
    if doc.proposer and doc.proposer != user:
        try:
            curr = doc.currency or "INR"
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
                        f"New live limit: {curr} {doc.proposed_credit_limit:,.2f}."
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
    """Administrator rejects a proposed retailer credit limit change with row-locking and mandatory reason."""
    user = get_current_user()
    if not is_clothing_admin(user):
        frappe.throw(
            _("Only administrators can reject credit limit adjustments."),
            frappe.PermissionError,
        )

    reason = (reason or "").strip()
    if not reason:
        frappe.throw(
            _("A non-empty rejection reason is required when rejecting a credit limit request."),
            frappe.ValidationError,
        )

    # Row-lock transition
    rows = frappe.db.sql(
        """
        SELECT name, status, proposer, customer, customer_name
        FROM `tabRetailer Credit Limit Request`
        WHERE name = %s
        FOR UPDATE
        """,
        (name,),
        as_dict=True,
    )
    if not rows:
        frappe.throw(_("Credit limit request {0} does not exist.").format(name), frappe.DoesNotExistError)

    req = rows[0]
    if req.status != "Pending Approval":
        frappe.throw(
            _("Credit limit request {0} is already {1}.").format(name, req.status),
            frappe.ValidationError,
        )

    doc = frappe.get_doc("Retailer Credit Limit Request", name)
    doc.flags.in_decision_service = True
    doc.status = "Rejected"
    doc.approver = user
    doc.decided_on = now_datetime()
    doc.rejection_reason = reason
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
                        f"Reason: {doc.rejection_reason}."
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


def retailer_credit_limit_request_query_conditions(user=None):
    """Permission query conditions for Retailer Credit Limit Request."""
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return ""
    territories = assigned_sales_territories(user)
    if not territories:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(t) for t in territories)
    return f"`tabRetailer Credit Limit Request`.`territory` IN ({escaped})"


def retailer_credit_limit_request_has_permission(doc, user=None, ptype=None, **kwargs):
    """Document-level permission check for Retailer Credit Limit Request."""
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return True
    if ptype in ("create", "write", "delete", "cancel") and not is_sales_manager(user):
        return False
    territories = set(assigned_sales_territories(user))
    doc_territory = getattr(doc, "territory", None) or (
        frappe.db.get_value("Customer", doc.customer, "territory") if getattr(doc, "customer", None) else None
    )
    return bool(doc_territory and doc_territory in territories)
