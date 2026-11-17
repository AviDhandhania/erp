"""Delivery Follow-Up Obligation service and lifecycle tracking.

Generates and tracks post-dispatch retailer follow-up obligations for Area Sales Managers.
Enforces the operational model requirements:
- After a warehouse hands an order to delivery, the responsible ASM must follow up with the retailer.
- Confirms delivery outcome, date/time, contact person, shortages, damages, or refusal issues.
- Territory and supervision scoping: ASM sees obligations in their assigned territory;
  RSM sees obligations for their supervised ASMs; administrators have global oversight.
- Concurrency protection: row-locking ensures atomic, idempotent follow-up completion.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate

from sales_erp.roles import (
    ROLE_ASM,
    ROLE_BUSINESS_ADMIN,
    ROLE_RSM,
    ROLE_SALESPERSON,
    ROLE_SALES_MANAGER,
)
from sales_erp.security import (
    assigned_sales_territories,
    get_current_user,
    get_user_roles,
    has_retailer_access,
    is_clothing_admin,
    is_sales_manager,
    require_role,
)
from sales_erp.supervision import get_territory_supervision

DELIVERY_FOLLOW_UP_WINDOW_DAYS = 3

VALID_OUTCOMES = {
    "Delivered in Full & Good Condition": "Satisfied",
    "Shortage Reported": "Issue Escalated",
    "Damage Reported": "Issue Escalated",
    "Delivery Refused / Returned": "Issue Escalated",
    "Retailer Unavailable": "Pending Contact",
}

STATUSES = {"all", "pending", "satisfied", "escalated"}
MAX_PAGE_SIZE = 50


def on_delivery_note_submitted(doc, method=None):
    """DocEvent hook: generate ASM delivery follow-up obligation upon Delivery Note submission."""
    create_delivery_follow_up_obligation(doc)


def create_delivery_follow_up_obligation(delivery_note) -> frappe.Document | None:
    """Create an app-owned Delivery Follow-Up Obligation from a submitted native Delivery Note."""
    if isinstance(delivery_note, str):
        delivery_note = frappe.get_doc("Delivery Note", delivery_note)

    if not delivery_note or delivery_note.docstatus != 1:
        return None

    existing = frappe.db.get_value(
        "Delivery Follow-Up Obligation",
        {"delivery_note": delivery_note.name},
        "name",
    )
    if existing:
        return frappe.get_doc("Delivery Follow-Up Obligation", existing)

    customer = delivery_note.customer
    customer_doc = frappe.db.get_value(
        "Customer",
        customer,
        ["name", "customer_name", "territory"],
        as_dict=True,
    )
    if not customer_doc:
        return None

    territory = customer_doc.territory
    posting_date = getdate(delivery_note.posting_date or nowdate())
    supervision = get_territory_supervision(territory, on_date=posting_date) if territory else None

    asm = supervision.asm if supervision else None
    rsm = supervision.rsm if supervision else None

    due_date = add_days(posting_date, DELIVERY_FOLLOW_UP_WINDOW_DAYS)

    obligation = frappe.get_doc(
        {
            "doctype": "Delivery Follow-Up Obligation",
            "delivery_note": delivery_note.name,
            "customer": customer,
            "customer_name": customer_doc.customer_name,
            "territory": territory,
            "assigned_asm": asm,
            "assigned_rsm": rsm,
            "posting_date": posting_date,
            "due_date": due_date,
            "status": "Pending Contact",
        }
    )
    obligation.flags.ignore_permissions = True
    obligation.insert()
    return obligation


@frappe.whitelist(methods=["POST"])
def record_delivery_follow_up(
    obligation: str,
    outcome: str,
    contact_person: str | None = None,
    contact_datetime: str | None = None,
    issue_notes: str | None = None,
) -> dict:
    """Atomically record retailer delivery outcome and close/escalate the follow-up obligation."""
    user = get_current_user()
    if not user or user == "Guest":
        frappe.throw(_("Authentication required."), frappe.PermissionError)

    outcome = str(outcome or "").strip()
    if outcome not in VALID_OUTCOMES:
        frappe.throw(
            _("Invalid delivery outcome. Must be one of: {0}").format(
                ", ".join(VALID_OUTCOMES.keys())
            )
        )

    obligation_name = str(obligation or "").strip()
    if not frappe.db.exists("Delivery Follow-Up Obligation", obligation_name):
        frappe.throw(_("Delivery Follow-Up Obligation {0} not found.").format(obligation_name), frappe.DoesNotExistError)

    # Row-lock for concurrency protection
    frappe.db.sql(
        "SELECT name FROM `tabDelivery Follow-Up Obligation` WHERE name = %s FOR UPDATE",
        (obligation_name,),
    )

    doc = frappe.get_doc("Delivery Follow-Up Obligation", obligation_name)

    # Permission check: assigned ASM, supervising RSM, or admin
    if not _can_record_follow_up(doc, user):
        frappe.throw(
            _("You do not have permission to record follow-up for this retailer territory."),
            frappe.PermissionError,
        )

    if doc.status == "Satisfied":
        frappe.throw(_("This delivery follow-up obligation has already been completed."))

    new_status = VALID_OUTCOMES[outcome]
    doc.outcome = outcome
    doc.contact_person = str(contact_person or "").strip()[:140] or None
    doc.contact_datetime = contact_datetime or now_datetime()
    doc.issue_notes = str(issue_notes or "").strip() or None
    doc.status = new_status

    if new_status in ("Satisfied", "Issue Escalated"):
        doc.satisfied_on = now_datetime()
        doc.satisfied_by = user

        # Record a permanent audit Retailer Visit for delivery verification
        visit = frappe.get_doc(
            {
                "doctype": "Retailer Visit",
                "customer": doc.customer,
                "salesperson": doc.assigned_asm or user,
                "rsm": doc.assigned_rsm,
                "visit_date": doc.contact_datetime,
                "visitor_role": "Area Sales Manager",
                "visit_type": "Delivery Follow-up",
                "outcome": "Issue Reported" if new_status == "Issue Escalated" else "Closed",
                "notes": (
                    f"Delivery Follow-up for {doc.delivery_note}\n"
                    f"Outcome: {outcome}\n"
                    f"Contact: {doc.contact_person or 'N/A'}\n"
                    f"Notes: {doc.issue_notes or 'None'}"
                ),
            }
        )
        visit.flags.ignore_permissions = True
        visit.insert()
        doc.qualifying_visit = visit.name

    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()

    return {
        "obligation": doc.name,
        "delivery_note": doc.delivery_note,
        "status": doc.status,
        "outcome": doc.outcome,
        "qualifying_visit": doc.qualifying_visit,
    }


def _can_record_follow_up(doc, user: str) -> bool:
    """Validate whether user is authorized to perform and record this follow-up."""
    if is_clothing_admin(user) or user == "Administrator":
        return True
    roles = get_user_roles(user)
    if not (roles & {ROLE_ASM, ROLE_SALESPERSON, ROLE_RSM, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}):
        return False
    territories = set(assigned_sales_territories(user))
    if doc.territory and doc.territory in territories:
        return True
    if doc.assigned_asm == user or doc.assigned_rsm == user:
        return True
    return False


@frappe.whitelist()
def get_delivery_follow_up_obligations(
    status: str = "all",
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Retrieve delivery follow-up obligations scoped to the user's assigned sales territories."""
    user = get_current_user()
    if not user or user == "Guest":
        frappe.throw(_("Authentication required."), frappe.PermissionError)

    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), MAX_PAGE_SIZE)
    status = str(status or "all").strip().lower()

    filters = {}
    if status == "pending":
        filters["status"] = "Pending Contact"
    elif status == "satisfied":
        filters["status"] = "Satisfied"
    elif status == "escalated":
        filters["status"] = "Issue Escalated"

    search = str(search or "").strip()
    if search:
        filters["customer_name"] = ["like", f"%{search}%"]

    # Uses get_list so delivery_follow_up_query_conditions and docperms apply
    rows = frappe.get_list(
        "Delivery Follow-Up Obligation",
        filters=filters,
        fields=[
            "name",
            "delivery_note",
            "customer",
            "customer_name",
            "territory",
            "assigned_asm",
            "assigned_rsm",
            "posting_date",
            "due_date",
            "status",
            "outcome",
            "contact_person",
            "contact_datetime",
            "issue_notes",
            "qualifying_visit",
            "satisfied_on",
            "satisfied_by",
            "creation",
        ],
        order_by="due_date asc, creation desc",
        start=(page - 1) * page_size,
        limit=page_size + 1,
    )

    has_more = len(rows) > page_size
    records = rows[:page_size]

    return {
        "obligations": records,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        },
    }


def delivery_follow_up_query_conditions(user=None) -> str:
    """SQL condition restricting follow-up visibility to authorized territory personnel."""
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return ""
    territories = assigned_sales_territories(user)
    if not territories:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(t) for t in territories)
    return (
        f"(`tabDelivery Follow-Up Obligation`.`territory` IN ({escaped}) "
        f"OR `tabDelivery Follow-Up Obligation`.`assigned_rsm` = {frappe.db.escape(user)} "
        f"OR `tabDelivery Follow-Up Obligation`.`assigned_asm` = {frappe.db.escape(user)})"
    )


def delivery_follow_up_has_permission(doc, ptype="read", user=None, **kwargs) -> bool:
    """Document permission check for Delivery Follow-Up Obligation."""
    user = user or frappe.session.user
    if is_clothing_admin(user) or user == "Administrator":
        return True
    if ptype in ("create", "delete") and not is_clothing_admin(user):
        return False
    territories = set(assigned_sales_territories(user))
    doc_territory = getattr(doc, "territory", None)
    if doc_territory and doc_territory in territories:
        return True
    if getattr(doc, "assigned_asm", None) == user or getattr(doc, "assigned_rsm", None) == user:
        return True
    return False
