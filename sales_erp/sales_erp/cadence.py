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
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

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
from sales_erp.settings import get_sales_settings

RSM_VISIT_CYCLE_DAYS = 80
RSM_ADVANCE_WARNING_DAYS = 70
RSM_GRACE_PERIOD_DAYS = 5
RSM_ESCALATION_THRESHOLD_DAYS = 85  # 80 + 5

SIS_STOCK_REVIEW_CYCLE_DAYS = 90
SIS_STOCK_REVIEW_WARNING_DAYS = 80
SIS_STOCK_REVIEW_GRACE_DAYS = 5
SIS_STOCK_REVIEW_ESCALATION_DAYS = 95

SIS_GENERAL_VISIT_CYCLE_DAYS = 30
SIS_GENERAL_VISIT_WARNING_DAYS = 25
SIS_GENERAL_VISIT_GRACE_DAYS = 5
SIS_GENERAL_VISIT_ESCALATION_DAYS = 35

BUY_SELL_VISIT_CYCLE_DAYS = 30
BUY_SELL_VISIT_WARNING_DAYS = 25
BUY_SELL_VISIT_GRACE_DAYS = 5
BUY_SELL_VISIT_ESCALATION_DAYS = 35

COLLECTION_WINDOW_START_DAYS = 90
COLLECTION_WINDOW_ESCALATION_DAYS = 120

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

    cfg = get_sales_settings()
    cycle_days = cfg.get("rsm_cycle_days", RSM_VISIT_CYCLE_DAYS)
    warning_days = cfg.get("rsm_warning_days", RSM_ADVANCE_WARNING_DAYS)
    escalation_days = cfg.get("rsm_escalation_days", RSM_ESCALATION_THRESHOLD_DAYS)

    days_elapsed = max(0, (target_dt - base_date).days)
    days_remaining = cycle_days - days_elapsed
    due_date = add_days(base_date, cycle_days)
    grace_end_date = add_days(base_date, escalation_days)

    if days_elapsed <= warning_days:
        status = STATUS_COMPLIANT
    elif days_elapsed <= cycle_days:
        status = STATUS_APPROACHING
    elif days_elapsed <= escalation_days:
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


def get_customer_asm_visit_status(customer: str, target_date: str | None = None) -> list[dict]:
    """Calculate the ASM cadence obligations (SIS quarterly/monthly, Buy & Sell monthly & collections, EBOC) for a customer."""
    target_dt = getdate(target_date or nowdate())
    customer_doc = frappe.db.get_value(
        "Customer",
        customer,
        ["name", "customer_name", "customer_group", "territory", "creation", "disabled"],
        as_dict=True,
    )
    if not customer_doc:
        frappe.throw(_("Customer {0} does not exist.").format(customer), frappe.DoesNotExistError)

    cfg = get_sales_settings()
    sis_stock_cycle = cfg.get("sis_stock_review_cycle_days", SIS_STOCK_REVIEW_CYCLE_DAYS)
    sis_stock_warn = cfg.get("sis_stock_review_warning_days", SIS_STOCK_REVIEW_WARNING_DAYS)
    sis_stock_esc = cfg.get("sis_stock_review_escalation_days", SIS_STOCK_REVIEW_ESCALATION_DAYS)

    sis_gen_cycle = cfg.get("sis_general_visit_cycle_days", SIS_GENERAL_VISIT_CYCLE_DAYS)
    sis_gen_warn = cfg.get("sis_general_visit_warning_days", SIS_GENERAL_VISIT_WARNING_DAYS)
    sis_gen_esc = cfg.get("sis_general_visit_grace_days", SIS_GENERAL_VISIT_GRACE_DAYS) + sis_gen_cycle

    bs_cycle = cfg.get("buy_sell_visit_cycle_days", BUY_SELL_VISIT_CYCLE_DAYS)
    bs_warn = cfg.get("buy_sell_visit_warning_days", BUY_SELL_VISIT_WARNING_DAYS)
    bs_esc = cfg.get("buy_sell_visit_grace_days", BUY_SELL_VISIT_GRACE_DAYS) + bs_cycle

    col_start = cfg.get("collection_window_start_days", COLLECTION_WINDOW_START_DAYS)
    col_esc = cfg.get("collection_window_escalation_days", COLLECTION_WINDOW_ESCALATION_DAYS)

    territory = customer_doc.territory
    supervision = get_territory_supervision(territory, on_date=target_dt) if territory else None
    asm = supervision.asm if supervision else None
    rsm = supervision.rsm if supervision else None
    retailer_type = customer_doc.customer_group or "Buy & Sell"

    items = []

    # 1. SIS Retailer Cadence
    if retailer_type == "SIS (Shop-in-Shop)":
        # A. Quarterly Stock Review (90 days)
        last_stock_review = frappe.db.sql(
            """
            SELECT name, visit_date, visit_type, salesperson
            FROM `tabRetailer Visit`
            WHERE customer = %s
              AND docstatus != 2
              AND visit_type = 'Stock Review'
              AND DATE(visit_date) <= %s
            ORDER BY visit_date DESC, creation DESC
            LIMIT 1
            """,
            (customer, target_dt),
            as_dict=True,
        )
        base_stock_date = getdate(last_stock_review[0].visit_date) if last_stock_review else (getdate(customer_doc.creation) if customer_doc.creation else target_dt)
        elapsed_stock = max(0, (target_dt - base_stock_date).days)
        due_stock = add_days(base_stock_date, sis_stock_cycle)
        grace_stock = add_days(base_stock_date, sis_stock_esc)

        if elapsed_stock <= sis_stock_warn:
            stk_status = STATUS_COMPLIANT
            stk_esc = "None"
        elif elapsed_stock <= sis_stock_cycle:
            stk_status = STATUS_APPROACHING
            stk_esc = "Approaching"
        elif elapsed_stock <= sis_stock_esc:
            stk_status = STATUS_GRACE
            stk_esc = "Grace"
        else:
            stk_status = STATUS_OVERDUE
            stk_esc = "Escalated"

        items.append({
            "obligation_type": "Quarterly Stock Review",
            "cycle_id": f"{customer}-Quarterly Stock Review-{base_stock_date}",
            "customer": customer_doc.name,
            "customer_name": customer_doc.customer_name or customer_doc.name,
            "retailer_type": retailer_type,
            "territory": territory,
            "asm": asm,
            "rsm": rsm,
            "base_date": str(base_stock_date),
            "last_visit": last_stock_review[0].name if last_stock_review else None,
            "days_elapsed": elapsed_stock,
            "due_date": str(due_stock),
            "grace_end_date": str(grace_stock),
            "status": stk_status,
            "escalation_state": stk_esc,
        })

        # B. Monthly General Visit (30 days)
        last_gen_visit = frappe.db.sql(
            """
            SELECT name, visit_date, visit_type, salesperson
            FROM `tabRetailer Visit`
            WHERE customer = %s
              AND docstatus != 2
              AND visit_type = 'General Visit'
              AND DATE(visit_date) <= %s
            ORDER BY visit_date DESC, creation DESC
            LIMIT 1
            """,
            (customer, target_dt),
            as_dict=True,
        )
        base_gen_date = getdate(last_gen_visit[0].visit_date) if last_gen_visit else (getdate(customer_doc.creation) if customer_doc.creation else target_dt)
        elapsed_gen = max(0, (target_dt - base_gen_date).days)
        due_gen = add_days(base_gen_date, sis_gen_cycle)
        grace_gen = add_days(base_gen_date, sis_gen_esc)

        if elapsed_gen <= sis_gen_warn:
            gen_status = STATUS_COMPLIANT
            gen_esc = "None"
        elif elapsed_gen <= sis_gen_cycle:
            gen_status = STATUS_APPROACHING
            gen_esc = "Approaching"
        elif elapsed_gen <= sis_gen_esc:
            gen_status = STATUS_GRACE
            gen_esc = "Grace"
        else:
            gen_status = STATUS_OVERDUE
            gen_esc = "Escalated"

        items.append({
            "obligation_type": "Monthly General Visit",
            "cycle_id": f"{customer}-Monthly General Visit-{base_gen_date}",
            "customer": customer_doc.name,
            "customer_name": customer_doc.customer_name or customer_doc.name,
            "retailer_type": retailer_type,
            "territory": territory,
            "asm": asm,
            "rsm": rsm,
            "base_date": str(base_gen_date),
            "last_visit": last_gen_visit[0].name if last_gen_visit else None,
            "days_elapsed": elapsed_gen,
            "due_date": str(due_gen),
            "grace_end_date": str(grace_gen),
            "status": gen_status,
            "escalation_state": gen_esc,
        })

    # 2. Buy & Sell and EBOC Retailer Cadence
    elif retailer_type in ("Buy & Sell", "Buy & Sell - Stock Correction", "EBOC"):
        # A. Monthly Sample & Order Visit (30 days)
        last_so_visit = frappe.db.sql(
            """
            SELECT name, visit_date, visit_type, salesperson
            FROM `tabRetailer Visit`
            WHERE customer = %s
              AND docstatus != 2
              AND visit_type IN ('Sample & Order Taking', 'General Visit', 'Stock Review')
              AND DATE(visit_date) <= %s
            ORDER BY visit_date DESC, creation DESC
            LIMIT 1
            """,
            (customer, target_dt),
            as_dict=True,
        )
        base_so_date = getdate(last_so_visit[0].visit_date) if last_so_visit else (getdate(customer_doc.creation) if customer_doc.creation else target_dt)
        elapsed_so = max(0, (target_dt - base_so_date).days)
        due_so = add_days(base_so_date, bs_cycle)
        grace_so = add_days(base_so_date, bs_esc)

        if elapsed_so <= bs_warn:
            so_status = STATUS_COMPLIANT
            so_esc = "None"
        elif elapsed_so <= bs_cycle:
            so_status = STATUS_APPROACHING
            so_esc = "Approaching"
        elif elapsed_so <= bs_esc:
            so_status = STATUS_GRACE
            so_esc = "Grace"
        else:
            so_status = STATUS_OVERDUE
            so_esc = "Escalated"

        obligation_label = "Monthly Stock Review" if retailer_type == "EBOC" else "Monthly Sample & Order"
        items.append({
            "obligation_type": obligation_label,
            "cycle_id": f"{customer}-{obligation_label}-{base_so_date}",
            "customer": customer_doc.name,
            "customer_name": customer_doc.customer_name or customer_doc.name,
            "retailer_type": retailer_type,
            "territory": territory,
            "asm": asm,
            "rsm": rsm,
            "base_date": str(base_so_date),
            "last_visit": last_so_visit[0].name if last_so_visit else None,
            "days_elapsed": elapsed_so,
            "due_date": str(due_so),
            "grace_end_date": str(grace_so),
            "status": so_status,
            "escalation_state": so_esc,
        })

        # B. Outstanding Collections in 90-120 days from Delivery Date / Invoice Posting (Buy & Sell only)
        if retailer_type in ("Buy & Sell", "Buy & Sell - Stock Correction"):
            unpaid_invoices = frappe.db.sql(
                """
                SELECT name, posting_date, outstanding_amount, grand_total
                FROM `tabSales Invoice`
                WHERE customer = %s
                  AND docstatus = 1
                  AND outstanding_amount > 0
                  AND DATE(posting_date) <= %s
                ORDER BY posting_date ASC
                """,
                (customer, target_dt),
                as_dict=True,
            )
            for inv in unpaid_invoices:
                inv_date = getdate(inv.posting_date)
                elapsed_inv = max(0, (target_dt - inv_date).days)
                if elapsed_inv >= col_start:
                    due_col = add_days(inv_date, col_start)
                    grace_col = add_days(inv_date, col_esc)
                    if elapsed_inv <= col_esc:
                        col_status = STATUS_GRACE
                        col_esc = "Grace"
                    else:
                        col_status = STATUS_OVERDUE
                        col_esc = "Escalated"

                    items.append({
                        "obligation_type": "Payment Collection Follow-up",
                        "cycle_id": f"{customer}-Payment Collection Follow-up-{inv.name}",
                        "customer": customer_doc.name,
                        "customer_name": customer_doc.customer_name or customer_doc.name,
                        "retailer_type": retailer_type,
                        "territory": territory,
                        "asm": asm,
                        "rsm": rsm,
                        "base_date": str(inv_date),
                        "invoice_no": inv.name,
                        "outstanding_amount": float(inv.outstanding_amount),
                        "days_elapsed": elapsed_inv,
                        "due_date": str(due_col),
                        "grace_end_date": str(grace_col),
                        "status": col_status,
                        "escalation_state": col_esc,
                        "notes": f"Invoice {inv.name} has outstanding balance of {inv.outstanding_amount} ({elapsed_inv} days since invoice).",
                    })

    return items


def sync_asm_visit_obligation(item: dict, target_date: str | None = None) -> str | None:
    """Create or synchronize an ASM Visit Obligation record idempotently."""
    cycle_id = item.get("cycle_id")
    customer = item.get("customer")
    if not cycle_id or not customer:
        return None

    # Only create/sync structured obligation if it is approaching, grace, or overdue
    if item.get("status") == STATUS_COMPLIANT:
        return None

    existing = frappe.db.get_value(
        "ASM Visit Obligation",
        {"cycle_id": cycle_id},
        ["name", "status", "escalation_state"],
        as_dict=True,
    )

    new_status = "Overdue / Escalated" if item.get("status") == STATUS_OVERDUE else ("Grace Period" if item.get("status") == STATUS_GRACE else "Open")
    escalation_state = item.get("escalation_state", "None")

    if existing:
        if existing.status in ("Open", "Grace Period", "Overdue / Escalated"):
            if existing.status != new_status or existing.escalation_state != escalation_state:
                update_vals = {
                    "status": new_status,
                    "escalation_state": escalation_state,
                    "assigned_asm": item.get("asm"),
                    "supervising_rsm": item.get("rsm"),
                }
                if item.get("outstanding_amount") is not None:
                    update_vals["outstanding_amount"] = flt(item.get("outstanding_amount"))
                frappe.db.set_value(
                    "ASM Visit Obligation",
                    existing.name,
                    update_vals,
                )
        return existing.name

    doc = frappe.get_doc({
        "doctype": "ASM Visit Obligation",
        "obligation_type": item.get("obligation_type"),
        "cycle_id": cycle_id,
        "customer": customer,
        "retailer_type": item.get("retailer_type"),
        "territory": item.get("territory"),
        "assigned_asm": item.get("asm"),
        "supervising_rsm": item.get("rsm"),
        "cycle_start": item.get("base_date"),
        "due_date": item.get("due_date"),
        "grace_end_date": item.get("grace_end_date"),
        "status": new_status,
        "escalation_state": escalation_state,
        "invoice_no": item.get("invoice_no"),
        "outstanding_amount": flt(item.get("outstanding_amount", 0.0)),
        "notes": item.get("notes"),
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name


def close_asm_visit_obligation(customer: str, visit_doc=None, obligation_type: str | None = None) -> int:
    """Fulfill open/grace/escalated ASM obligations upon qualifying visit completion."""
    filters = {
        "customer": customer,
        "status": ["in", ["Open", "Grace Period", "Overdue / Escalated"]],
    }
    if obligation_type:
        filters["obligation_type"] = obligation_type

    obligations = frappe.get_all("ASM Visit Obligation", filters=filters, pluck="name")
    closed = 0
    now = now_datetime()
    user = get_current_user()
    for name in obligations:
        frappe.db.set_value(
            "ASM Visit Obligation",
            name,
            {
                "status": "Satisfied",
                "qualifying_visit": visit_doc.name if visit_doc else None,
                "satisfied_on": now,
                "satisfied_by": user,
            },
        )
        closed += 1
    return closed


def evaluate_asm_visit_cadence(target_date: str | None = None) -> dict:
    """Daily scheduler job evaluating ASM visit obligations across all active retailers."""
    target_dt = getdate(target_date or nowdate())
    customers = frappe.get_all(
        "Customer",
        filters={"disabled": 0},
        fields=["name", "customer_name", "territory", "customer_group"],
    )
    results = {
        "evaluated": len(customers),
        "created_or_updated": 0,
        "obligations": [],
    }
    for cust in customers:
        items = get_customer_asm_visit_status(cust.name, target_date=target_dt)
        for item in items:
            obl_name = sync_asm_visit_obligation(item, target_date=target_dt)
            if obl_name:
                results["created_or_updated"] += 1
                results["obligations"].append(obl_name)
    return results


@frappe.whitelist()
def get_asm_cadence_directory(
    obligation_type=None,
    status=None,
    territory=None,
    asm=None,
    page=1,
    page_size=20,
):
    """List ASM visit obligations scoped strictly to user's assigned territories."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    admin = is_clothing_admin(user)

    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), 50)

    filters = {}
    if not admin:
        user_territories = assigned_sales_territories(user)
        if not user_territories:
            return {"obligations": [], "pagination": {"page": page, "page_size": page_size, "has_more": False}}
        if territory:
            if territory not in user_territories:
                frappe.throw(_("Access denied to territory {0}").format(territory), frappe.PermissionError)
            filters["territory"] = territory
        else:
            filters["territory"] = ["in", user_territories]
    else:
        if territory:
            filters["territory"] = territory

    if obligation_type:
        filters["obligation_type"] = obligation_type
    if status:
        filters["status"] = status
    if asm:
        filters["assigned_asm"] = asm

    rows = frappe.get_all(
        "ASM Visit Obligation",
        filters=filters,
        fields=[
            "name",
            "obligation_type",
            "cycle_id",
            "customer",
            "customer_name",
            "retailer_type",
            "territory",
            "assigned_asm",
            "supervising_rsm",
            "cycle_start",
            "due_date",
            "grace_end_date",
            "status",
            "escalation_state",
            "invoice_no",
            "outstanding_amount",
            "qualifying_visit",
            "satisfied_on",
            "satisfied_by",
        ],
        order_by="due_date asc, creation desc",
        start=(page - 1) * page_size,
        limit=page_size + 1,
    )

    has_more = len(rows) > page_size
    return {
        "obligations": rows[:page_size],
        "pagination": {"page": page, "page_size": page_size, "has_more": has_more},
    }


@frappe.whitelist()
def get_collection_obligations(customer=None, target_date=None, page=1, page_size=20):
    """Retrieve unpaid invoices in the 90-120 day collection window scoped to user's assigned territories."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    admin = is_clothing_admin(user)

    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), 50)
    target_dt = getdate(target_date or nowdate())

    allowed_territories = None if admin else assigned_sales_territories(user)
    if not admin and not allowed_territories:
        return {"collections": [], "pagination": {"page": page, "page_size": page_size, "has_more": False}}

    conditions = ["si.docstatus = 1", "si.outstanding_amount > 0", "DATE(si.posting_date) <= %s"]
    params = [target_dt]

    if customer:
        if not admin and not has_retailer_access(customer, user):
            frappe.throw(_("Access denied to retailer {0}").format(customer), frappe.PermissionError)
        conditions.append("si.customer = %s")
        params.append(customer)
    elif allowed_territories is not None:
        conditions.append("c.territory IN ({})".format(", ".join("%s" for _ in allowed_territories)))
        params.extend(allowed_territories)

    query = f"""
        SELECT si.name, si.customer, si.customer_name, si.posting_date, si.due_date,
               si.outstanding_amount, si.grand_total, si.currency, c.territory,
               DATEDIFF(%s, si.posting_date) AS days_elapsed
        FROM `tabSales Invoice` si
        JOIN `tabCustomer` c ON c.name = si.customer
        WHERE {' AND '.join(conditions)}
          AND DATEDIFF(%s, si.posting_date) >= 90
        ORDER BY days_elapsed DESC, si.posting_date ASC
        LIMIT %s OFFSET %s
    """
    all_params = [target_dt, *params, target_dt, page_size + 1, (page - 1) * page_size]
    rows = frappe.db.sql(query, all_params, as_dict=True)
    has_more = len(rows) > page_size
    return {
        "collections": rows[:page_size],
        "pagination": {"page": page, "page_size": page_size, "has_more": has_more},
    }


def is_retailer_order_blocked_by_collection(customer: str, target_date: str | None = None) -> tuple[bool, str | None]:
    """Check if retailer has overdue invoices exceeding 120 days causing an order block."""
    cfg = get_sales_settings()
    if not cfg.get("enforce_collection_hard_block"):
        return False, None

    target_dt = getdate(target_date or nowdate())
    col_esc_days = cfg.get("collection_window_escalation_days", 120)

    overdue_invoices = frappe.db.sql(
        """
        SELECT name, posting_date, outstanding_amount, grand_total
        FROM `tabSales Invoice`
        WHERE customer = %s
          AND docstatus = 1
          AND outstanding_amount > 0
          AND DATE(posting_date) <= %s
        ORDER BY posting_date ASC
        """,
        (customer, target_dt),
        as_dict=True,
    )
    for inv in overdue_invoices:
        inv_date = getdate(inv.posting_date)
        elapsed = max(0, (target_dt - inv_date).days)
        if elapsed >= col_esc_days:
            return (
                True,
                _("Retailer {0} has unpaid invoice {1} overdue by {2} days (threshold: {3} days). New orders are blocked until payment is collected.").format(
                    customer, inv.name, elapsed, col_esc_days
                ),
            )

    return False, None


@frappe.whitelist(methods=["GET"])
def get_seasonal_calendar_status(target_date: str | None = None) -> dict:
    """Calculate the active seasonal window (Spring/Summer vs Autumn/Winter) and pre-booking status."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    cfg = get_sales_settings()
    target_dt = getdate(target_date or nowdate())
    month = target_dt.month
    year = target_dt.year

    ss_start = cfg.get("spring_summer_start_month", 2)
    aw_start = cfg.get("autumn_winter_start_month", 8)

    if ss_start <= month < aw_start:
        current_season = "Spring/Summer"
        season_year = year
        next_season = "Autumn/Winter"
        next_season_start = f"{year}-{aw_start:02d}-01"
    else:
        current_season = "Autumn/Winter"
        season_year = year if month >= aw_start else year - 1
        next_season = "Spring/Summer"
        next_year = year + 1 if month >= aw_start else year
        next_season_start = f"{next_year}-{ss_start:02d}-01"

    prebooking_days = cfg.get("seasonal_prebooking_days", 60)
    days_to_next = (getdate(next_season_start) - target_dt).days
    prebooking_active = 0 <= days_to_next <= prebooking_days

    return {
        "current_season": current_season,
        "season_year": season_year,
        "next_season": next_season,
        "next_season_start": next_season_start,
        "days_to_next_season": days_to_next,
        "prebooking_active": prebooking_active,
    }


