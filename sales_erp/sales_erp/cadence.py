"""RSM 80-day periodic retailer visit cadence, tracking, and escalation service.

Enforces the operational model requirements:
- The RSM must personally visit every shop in their supervisory scope at least once within 80 days.
- Advance warning notification / structured obligation record generated as the deadline approaches (day 70).
- 5 grace days follow the 80-day target (days 81-85).
- If no qualifying RSM visit exists after day 85, an escalation notice is sent to administrators.
- Idempotent and timezone-safe across repeated scheduler executions.
- Completing a qualifying RSM visit satisfies active structured obligations.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate

from sales_erp.roles import ROLE_ASM, ROLE_BUSINESS_ADMIN, ROLE_RSM, ROLE_SALESPERSON, ROLE_SALES_MANAGER
from sales_erp.security import (
    assigned_sales_territories,
    get_current_user,
    get_user_roles,
    has_retailer_access,
    is_clothing_admin,
    is_sales_manager,
    require_role,
)
from sales_erp.supervision import (
    get_active_supervising_rsm,
    get_supervised_asms,
    get_territory_supervision,
)

RSM_VISIT_CYCLE_DAYS = 80
RSM_ADVANCE_WARNING_DAYS = 70
RSM_GRACE_PERIOD_DAYS = 5
RSM_ESCALATION_THRESHOLD_DAYS = 85  # 80 + 5

STATUS_COMPLIANT = "Compliant"
STATUS_APPROACHING = "Approaching Deadline"
STATUS_GRACE = "Grace Period"
STATUS_OVERDUE = "Overdue / Escalated"


def get_customer_rsm_visit_status(customer: str, target_date: str | None = None) -> dict:
    """Calculate the 80-day cadence metrics for a single customer on target_date."""
    target_dt = getdate(target_date or nowdate())

    customer_doc = frappe.db.get_value(
        "Customer",
        customer,
        ["name", "customer_name", "territory", "creation", "disabled"],
        as_dict=True,
    )
    if not customer_doc:
        frappe.throw(_("Customer {0} does not exist.").format(customer), frappe.DoesNotExistError)

    territory = customer_doc.territory
    supervision = get_territory_supervision(territory, on_date=target_dt) if territory else None
    asm = supervision.asm if supervision else None
    rsm = supervision.rsm if supervision else None

    # Find the most recent qualifying RSM visit on or before target_dt
    last_visit = frappe.db.sql(
        """
        SELECT name, visit_date, visit_type, visitor_role, salesperson, rsm
        FROM `tabRetailer Visit`
        WHERE customer = %s
          AND docstatus != 2
          AND visitor_role = 'Regional Sales Manager'
          AND visit_type = 'RSM Periodic Review'
          AND DATE(visit_date) <= %s
        ORDER BY visit_date DESC, creation DESC
        LIMIT 1
        """,
        (customer, target_dt),
        as_dict=True,
    )

    if last_visit:
        base_date = getdate(last_visit[0].visit_date)
        last_visit_name = last_visit[0].name
        last_visit_type = last_visit[0].visit_type
        last_visitor = last_visit[0].salesperson
    else:
        # Base from customer creation if no qualifying RSM visit yet recorded
        base_date = getdate(customer_doc.creation) if customer_doc.creation else target_dt
        last_visit_name = None
        last_visit_type = None
        last_visitor = None

    days_elapsed = max(0, (target_dt - base_date).days)
    days_remaining = RSM_VISIT_CYCLE_DAYS - days_elapsed
    due_date = add_days(base_date, RSM_VISIT_CYCLE_DAYS)
    grace_end_date = add_days(base_date, RSM_ESCALATION_THRESHOLD_DAYS)

    if days_elapsed <= RSM_ADVANCE_WARNING_DAYS:
        status = STATUS_COMPLIANT
    elif days_elapsed <= RSM_VISIT_CYCLE_DAYS:
        status = STATUS_APPROACHING
    elif days_elapsed <= RSM_ESCALATION_THRESHOLD_DAYS:
        status = STATUS_GRACE
    else:
        status = STATUS_OVERDUE

    return {
        "customer": customer_doc.name,
        "customer_name": customer_doc.customer_name or customer_doc.name,
        "territory": territory,
        "asm": asm,
        "rsm": rsm,
        "base_date": str(base_date),
        "last_visit": last_visit_name,
        "last_visit_date": str(base_date) if last_visit_name else None,
        "last_visit_type": last_visit_type,
        "last_visitor": last_visitor,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "due_date": str(due_date),
        "grace_end_date": str(grace_end_date),
        "status": status,
        "disabled": bool(customer_doc.disabled),
    }


def sync_rsm_visit_obligation(status_info: dict, target_date: str | None = None) -> str | None:
    """Create or synchronize a structured RSM Visit Obligation for the customer's current cycle."""
    customer = status_info.get("customer")
    if not customer:
        return None

    base_date = status_info.get("base_date")
    cycle_id = f"{customer}-{base_date}"
    rsm = status_info.get("rsm")
    asm = status_info.get("asm")
    territory = status_info.get("territory")
    due_date = status_info.get("due_date")
    grace_end_date = status_info.get("grace_end_date")
    status = status_info.get("status")

    escalation_state = "None"
    if status == STATUS_APPROACHING:
        escalation_state = "Approaching"
    elif status == STATUS_GRACE:
        escalation_state = "Grace"
    elif status == STATUS_OVERDUE:
        escalation_state = "Escalated"

    existing = frappe.db.get_value(
        "RSM Visit Obligation",
        {"cycle_id": cycle_id},
        ["name", "status", "escalation_state"],
        as_dict=True,
    )

    if existing:
        if existing.status in ("Open", "Escalated"):
            new_status = "Escalated" if escalation_state == "Escalated" else "Open"
            if existing.status != new_status or existing.escalation_state != escalation_state:
                frappe.db.set_value(
                    "RSM Visit Obligation",
                    existing.name,
                    {
                        "status": new_status,
                        "escalation_state": escalation_state,
                        "assigned_rsm": rsm,
                        "assigned_asm": asm,
                    },
                )
        return existing.name

    doc = frappe.get_doc(
        {
            "doctype": "RSM Visit Obligation",
            "cycle_id": cycle_id,
            "customer": customer,
            "territory": territory,
            "assigned_rsm": rsm,
            "assigned_asm": asm,
            "cycle_start": base_date,
            "due_date": due_date,
            "grace_end_date": grace_end_date,
            "status": "Escalated" if escalation_state == "Escalated" else "Open",
            "escalation_state": escalation_state,
        }
    )
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name


def close_rsm_visit_obligation(customer: str, rsm: str | None = None, qualifying_visit: str | None = None) -> int:
    """Fulfill open/escalated obligations for this customer upon visit completion."""
    obligations = frappe.get_all(
        "RSM Visit Obligation",
        filters={
            "customer": customer,
            "status": ["in", ["Open", "Escalated"]],
        },
        pluck="name",
    )
    closed_count = 0
    now = now_datetime()
    for name in obligations:
        frappe.db.set_value(
            "RSM Visit Obligation",
            name,
            {
                "status": "Satisfied",
                "qualifying_visit": qualifying_visit,
                "satisfied_on": now,
                "satisfied_by": rsm or get_current_user(),
            },
        )
        closed_count += 1

    # Also close any linked legacy ToDos
    filters = {
        "reference_type": "Customer",
        "reference_name": customer,
        "status": "Open",
    }
    if rsm:
        filters["allocated_to"] = rsm

    open_todos = frappe.get_all("ToDo", filters=filters, pluck="name")
    for todo_name in open_todos:
        todo = frappe.get_doc("ToDo", todo_name)
        if "80-day periodic" in (todo.description or "") or "RSM" in (todo.description or ""):
            todo.status = "Closed"
            todo.flags.ignore_permissions = True
            todo.save()

    return closed_count


def sync_rsm_visit_todo(status_info: dict, target_date: str | None = None) -> str | None:
    """Synchronize both structured obligation and linked operational ToDo for supervising RSM."""
    sync_rsm_visit_obligation(status_info, target_date=target_date)

    rsm = status_info.get("rsm")
    customer = status_info.get("customer")
    customer_name = status_info.get("customer_name")
    status = status_info.get("status")

    if not rsm or not customer or status == STATUS_COMPLIANT:
        return None

    existing = frappe.db.get_value(
        "ToDo",
        {
            "reference_type": "Customer",
            "reference_name": customer,
            "allocated_to": rsm,
            "status": "Open",
        },
        "name",
    )
    if existing:
        return existing

    desc = (
        f"RSM 80-day periodic shop review due for {customer_name} ({customer}). "
        f"Status: {status}. Deadline: {status_info['due_date']} (Grace ends {status_info['grace_end_date']})."
    )

    todo = frappe.get_doc(
        {
            "doctype": "ToDo",
            "allocated_to": rsm,
            "reference_type": "Customer",
            "reference_name": customer,
            "description": desc,
            "date": status_info["due_date"],
            "status": "Open",
            "priority": "High" if status in (STATUS_GRACE, STATUS_OVERDUE) else "Medium",
        }
    )
    todo.flags.ignore_permissions = True
    todo.insert()
    return todo.name


def send_administrator_escalation(status_info: dict, target_date: str | None = None) -> list[str]:
    """Notify administrators when an RSM visit exceeds the 85-day grace threshold."""
    if status_info.get("status") != STATUS_OVERDUE:
        return []

    customer = status_info["customer"]
    customer_name = status_info["customer_name"]
    rsm = status_info.get("rsm") or "Unassigned"
    days_elapsed = status_info["days_elapsed"]
    target_dt = getdate(target_date or nowdate())

    # Record escalation on the structured obligation
    obligation_name = sync_rsm_visit_obligation(status_info, target_date=target_date)
    if obligation_name:
        last_escalated = frappe.db.get_value("RSM Visit Obligation", obligation_name, "last_escalated_on")
        if last_escalated and getdate(last_escalated) == target_dt:
            return []  # Already escalated today
        frappe.db.set_value("RSM Visit Obligation", obligation_name, "last_escalated_on", now_datetime())

    subject = (
        f"ESCALATION: Shop {customer_name} overdue for RSM visit ({days_elapsed} days elapsed). "
        f"Responsible RSM: {rsm}"
    )

    admin_users = frappe.db.sql(
        """
        SELECT DISTINCT u.name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` r ON r.parent = u.name
        WHERE u.enabled = 1
          AND u.user_type = 'System User'
          AND r.role IN (%(admin_role)s, 'System Manager')
        """,
        {"admin_role": ROLE_BUSINESS_ADMIN},
        pluck="name",
    )

    created = []
    for admin in admin_users:
        recent_notice = frappe.db.get_value(
            "Notification Log",
            filters={
                "for_user": admin,
                "document_type": "Customer",
                "document_name": customer,
                "creation": [">=", f"{target_dt} 00:00:00"],
            },
            fieldname="name",
        )
        if recent_notice:
            continue

        notification = frappe.get_doc(
            {
                "doctype": "Notification Log",
                "type": "Alert",
                "for_user": admin,
                "document_type": "Customer",
                "document_name": customer,
                "subject": subject,
                "email_content": (
                    f"Retail shop '{customer_name}' ({customer}) in territory '{status_info.get('territory')}' "
                    f"has not received a qualifying periodic review visit from the assigned Regional Sales Manager ({rsm}) "
                    f"in {days_elapsed} days. The 80-day cycle deadline ({status_info['due_date']}) and 5-day grace period "
                    f"({status_info['grace_end_date']}) have both passed."
                ),
            }
        )
        notification.flags.ignore_permissions = True
        notification.insert()
        created.append(notification.name)

    return created


def evaluate_rsm_visit_cadence(target_date: str | None = None, notify: bool = True) -> dict:
    """Evaluate 80-day visit cadence for all customers and record obligations / escalations."""
    target_dt = getdate(target_date or nowdate())

    customers = frappe.db.sql(
        """
        SELECT DISTINCT c.name
        FROM `tabCustomer` c
        INNER JOIN `tabASM Supervision` s ON s.territory = c.territory AND s.status = 'Active'
        WHERE (c.disabled IS NULL OR c.disabled = 0)
        ORDER BY c.name ASC
        """,
        pluck="name",
    )

    metrics = {
        "evaluated": len(customers),
        "compliant": 0,
        "approaching": 0,
        "grace": 0,
        "overdue": 0,
        "todos_created": 0,
        "escalations_sent": 0,
    }

    for cust in customers:
        status_info = get_customer_rsm_visit_status(cust, target_date=target_dt)
        st = status_info["status"]
        if st == STATUS_COMPLIANT:
            metrics["compliant"] += 1
            close_rsm_visit_obligation(cust, status_info.get("rsm"))
        elif st == STATUS_APPROACHING:
            metrics["approaching"] += 1
            if notify and sync_rsm_visit_todo(status_info, target_date=target_dt):
                metrics["todos_created"] += 1
        elif st == STATUS_GRACE:
            metrics["grace"] += 1
            if notify and sync_rsm_visit_todo(status_info, target_date=target_dt):
                metrics["todos_created"] += 1
        elif st == STATUS_OVERDUE:
            metrics["overdue"] += 1
            if notify:
                if sync_rsm_visit_todo(status_info, target_date=target_dt):
                    metrics["todos_created"] += 1
                sent = send_administrator_escalation(status_info, target_date=target_dt)
                metrics["escalations_sent"] += len(sent)

    return metrics


@frappe.whitelist()
def get_rsm_visit_cadence_report(
    rsm: str | None = None,
    territory: str | None = None,
    status: str | None = None,
    target_date: str | None = None,
) -> dict:
    """Return permission-scoped 80-day RSM visit cadence records and summary."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    roles = get_user_roles(user)
    target_dt = getdate(target_date or nowdate())

    admin = is_clothing_admin(user)
    allowed_territories = None

    if not admin:
        user_territories = set(assigned_sales_territories(user))
        if not user_territories:
            return {
                "records": [],
                "summary": {"total": 0, "compliant": 0, "approaching": 0, "grace": 0, "overdue": 0},
                "user_scope": "No active territory assignments",
            }

        if territory:
            if territory not in user_territories:
                frappe.throw(
                    _("You are not authorized to view territory {0}.").format(territory),
                    frappe.PermissionError,
                )
            allowed_territories = [territory]
        else:
            allowed_territories = sorted(user_territories)

        if rsm and rsm != user and not is_sales_manager(user):
            frappe.throw(
                _("You are not authorized to filter by RSM {0}.").format(rsm),
                frappe.PermissionError,
            )
    else:
        if territory:
            allowed_territories = [territory]

    conditions = ["(c.disabled IS NULL OR c.disabled = 0)"]
    params = []

    if allowed_territories is not None:
        conditions.append("c.territory IN ({})".format(", ".join("%s" for _ in allowed_territories)))
        params.extend(allowed_territories)

    query = f"""
        SELECT DISTINCT c.name, c.customer_name, c.territory
        FROM `tabCustomer` c
        WHERE {' AND '.join(conditions)}
        ORDER BY c.customer_name ASC
    """
    customers = frappe.db.sql(query, params, as_dict=True)

    records = []
    summary = {
        "total": 0,
        "compliant": 0,
        "approaching": 0,
        "grace": 0,
        "overdue": 0,
    }

    for cust in customers:
        item = get_customer_rsm_visit_status(cust.name, target_date=target_dt)
        if rsm and item.get("rsm") != rsm:
            continue

        item_status = item["status"]
        if item_status == STATUS_COMPLIANT:
            summary["compliant"] += 1
        elif item_status == STATUS_APPROACHING:
            summary["approaching"] += 1
        elif item_status == STATUS_GRACE:
            summary["grace"] += 1
        elif item_status == STATUS_OVERDUE:
            summary["overdue"] += 1
        summary["total"] += 1

        if status and item_status != status:
            continue

        records.append(item)

    if admin:
        scope = "Administrator scope — all territories"
    elif ROLE_SALES_MANAGER in roles:
        scope = f"RSM scope — {user}"
    else:
        scope = f"ASM scope — {user}"

    return {
        "records": records,
        "summary": summary,
        "user_scope": scope,
    }
