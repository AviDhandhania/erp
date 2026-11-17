"""Authenticated APIs. All data is queried with native document permissions."""
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, get_first_day, nowdate, today

from sales_erp import __version__
from sales_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
    ROLE_SALESPERSON,
    ROLE_SALES_MANAGER,
    ROLE_WAREHOUSE_MANAGER,
)
from sales_erp.security import (
    assigned_sales_territories,
    get_active_operational_role,
    get_current_user,
    get_user_roles,
    has_retailer_access,
    is_clothing_admin,
    is_salesperson,
    is_warehouse_operator,
    require_role,
)
from sales_erp.erpnext_client import get_delivery_notes, get_pick_lists

@frappe.whitelist()
def get_user_context():
    require_role({r["role_name"] for r in ALL_ROLES})
    return {"user": get_current_user(), "active_role": get_active_operational_role(),
            "roles": sorted(get_user_roles()),
            "permissions": {"salesperson_portal": is_salesperson(), "warehouse_operations": is_warehouse_operator(), "business_admin": is_clothing_admin()},
            "app_version": __version__}

@frappe.whitelist(methods=["POST"])
def switch_preview_role(role=None):
    # Reject requests from obsolete preview clients. Roles are assigned through User settings.
    frappe.throw(frappe._("Preview role switching has been removed. Ask your administrator to assign roles."), frappe.PermissionError)

def _count(doctype, filters=None):
    return frappe.get_list(doctype, filters=filters or {}, fields=[{"COUNT": "name", "as": "total"}])[0].total or 0


def _sales_customer_scope():
    """Return explicit retailer names, or None for a system/business administrator."""
    if is_clothing_admin():
        return None
    territories = assigned_sales_territories()
    if not territories:
        return []
    return frappe.get_all(
        "Customer",
        filters={"disabled": 0, "territory": ["in", territories]},
        pluck="name",
    )


def _scoped_sales_order_rows(customers, filters, fields, **kwargs):
    filters = dict(filters or {})
    if customers is not None:
        if not customers:
            return []
        filters["customer"] = ["in", customers]
    # Operational users intentionally have no native Sales Order permission.
    # This trusted endpoint uses an explicit assignment/territory scope instead.
    return frappe.get_all("Sales Order", filters=filters, fields=fields, **kwargs)

@frappe.whitelist()
def get_salesperson_dashboard():
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    date = today()
    customers = _sales_customer_scope()
    monthly_sales = _scoped_sales_order_rows(
        customers,
        {"docstatus": 1, "transaction_date": ["between", [str(get_first_day(date)), date]]},
        ["currency", {"SUM": "grand_total", "as": "total"}],
        group_by="currency",
    )
    today_count = _scoped_sales_order_rows(
        customers,
        {"transaction_date": date, "docstatus": ["!=", 2]},
        [{"COUNT": "name", "as": "total"}],
    )
    retailer_filters = {"disabled": 0}
    if customers is not None:
        if not customers:
            retailer_count = 0
        else:
            retailer_filters["name"] = ["in", customers]
            retailer_count = frappe.get_all(
                "Customer", filters=retailer_filters, fields=[{"COUNT": "name", "as": "total"}]
            )[0].total or 0
    else:
        retailer_count = frappe.get_all(
            "Customer", filters=retailer_filters, fields=[{"COUNT": "name", "as": "total"}]
        )[0].total or 0
    recent_orders = _scoped_sales_order_rows(
        customers,
        {"docstatus": ["!=", 2]},
        ["name", "customer", "transaction_date", "total_qty", "grand_total", "status"],
        order_by="modified desc",
        limit=20,
    )
    return {
        "metrics": {
            "today_orders_count": (today_count[0].total or 0) if today_count else 0,
            "assigned_retailers_count": retailer_count,
        },
        "monthly_sales": monthly_sales,
        "recent_orders": recent_orders,
        "shortcuts": [
            {"label": "Catalogue", "url": "/desk/clothing-erp/clothing-catalogue"},
            {"label": "Retailer Applications", "url": "/desk/clothing-erp/retailer-application"},
        ],
    }


def _empty_operational_dashboard():
    return {
        "applications": {"pending_count": 0, "rfi_count": 0, "approved_this_month": 0},
        "visits": {"completed_this_month": 0, "upcoming_obligations_count": 0},
        "cadence": {"rsm_overdue_count": 0, "rsm_grace_count": 0},
        "orders": {"draft_count": 0, "submitted_this_month_count": 0, "submitted_this_month_value": 0.0},
        "exposure": {"total_retailers": 0, "total_approved_limit": 0.0, "total_current_exposure": 0.0, "exceeded_limit_count": 0},
        "collections": {"warning_count": 0, "warning_amount": 0.0, "blocked_count": 0, "blocked_amount": 0.0},
        "delivery_issues": {"open_obligations_count": 0, "escalated_issues_count": 0},
    }


@frappe.whitelist()
def get_sales_operational_dashboard():
    """Permission-scoped operational dashboard for applications, visits, overdue cadence,
    orders, exposure, collections, and delivery issues.
    Enforces territory and supervisory scoping on all aggregate queries to guarantee
    zero cross-territory data leakage.
    """
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    admin = is_clothing_admin(user)
    customers = _sales_customer_scope()
    date = today()
    first_day = str(get_first_day(date))

    if customers is not None and not customers:
        return _empty_operational_dashboard()

    # 1. Applications metrics
    app_filters = []
    if not admin:
        assigned_territories = assigned_sales_territories(user)
        if assigned_territories:
            app_filters.append(["territory", "in", assigned_territories])
        else:
            app_filters.append(["salesperson", "=", user])

    pending_apps = frappe.db.count("Retailer Application", filters=[*app_filters, ["status", "in", ["Submitted to RSM", "Pending"]]])
    rfi_apps = frappe.db.count("Retailer Application", filters=[*app_filters, ["status", "=", "More Information Requested"]])
    approved_apps = frappe.db.count("Retailer Application", filters=[*app_filters, ["status", "=", "Approved"], ["reviewed_on", ">=", first_day]])

    # 2. Visits metrics
    visit_filters = [["visit_date", ">=", first_day]]
    if customers is not None:
        visit_filters.append(["customer", "in", customers])
    completed_visits = frappe.db.count("Retailer Visit", filters=visit_filters)

    # 3. Cadence metrics
    if frappe.db.table_exists("RSM Visit Obligation"):
        base_cadence_filters = []
        if not admin:
            assigned_territories = assigned_sales_territories(user)
            if assigned_territories:
                base_cadence_filters.append(["territory", "in", assigned_territories])
            else:
                base_cadence_filters.append(["rsm", "=", user])
        rsm_overdue = frappe.db.count("RSM Visit Obligation", filters=[*base_cadence_filters, ["status", "=", "Overdue"]])
        rsm_grace = frappe.db.count("RSM Visit Obligation", filters=[*base_cadence_filters, ["status", "=", "Grace"]])
        upcoming_ob = frappe.db.count("RSM Visit Obligation", filters=[*base_cadence_filters, ["status", "in", ["Upcoming", "Due", "Grace", "Overdue"]]])
    else:
        rsm_overdue = 0
        rsm_grace = 0
        upcoming_ob = 0

    # 4. Orders metrics
    draft_orders = _scoped_sales_order_rows(customers, {"docstatus": 0}, [{"COUNT": "name", "as": "total"}])
    draft_count = (draft_orders[0].total or 0) if draft_orders else 0

    submitted_orders = _scoped_sales_order_rows(
        customers,
        {"docstatus": 1, "transaction_date": ["between", [first_day, date]]},
        [{"COUNT": "name", "as": "count"}, {"SUM": "grand_total", "as": "total_value"}],
    )
    submitted_count = (submitted_orders[0].count or 0) if submitted_orders else 0
    submitted_value = flt(submitted_orders[0].total_value or 0.0) if submitted_orders else 0.0

    # 5. Exposure metrics
    cust_filters = {"disabled": 0}
    if customers is not None:
        cust_filters["name"] = ["in", customers]
    active_retailers = frappe.get_all("Customer", filters=cust_filters, fields=["name", "customer_name", "territory", "customer_group"])
    total_retailers = len(active_retailers)

    cust_cond = "1=1"
    params = []
    if customers is not None:
        cust_cond = f"customer IN ({', '.join(['%s']*len(customers))})"
        params.extend(customers)

    limits_cond = cust_cond.replace("customer", "parent")
    limits_rows = frappe.db.sql(
        f"SELECT parent, credit_limit FROM `tabCustomer Credit Limit` WHERE {limits_cond}",
        params,
        as_dict=True,
    ) if customers is None or customers else []
    approved_limits_map = {row.parent: flt(row.credit_limit) for row in limits_rows}
    total_approved_limit = sum(approved_limits_map.values())

    dn_rows = frappe.db.sql(
        f"""
        SELECT dn.customer,
               SUM(CASE WHEN dn.is_return = 1 THEN -ABS(dni.amount) ELSE dni.amount END) AS net_delivered
        FROM `tabDelivery Note Item` dni
        JOIN `tabDelivery Note` dn ON dn.name = dni.parent
        WHERE dn.docstatus = 1 AND {cust_cond.replace('customer', 'dn.customer')}
        GROUP BY dn.customer
        """,
        params,
        as_dict=True,
    ) if customers is None or customers else []
    stock_held_map = {row.customer: max(0.0, flt(row.net_delivered)) for row in dn_rows}

    so_rows = frappe.db.sql(
        f"""
        SELECT so.customer,
               SUM(GREATEST(0, soi.qty - soi.delivered_qty) * soi.rate) AS pending_val
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE so.docstatus = 1 AND so.status NOT IN ('Completed', 'Cancelled', 'Closed')
          AND {cust_cond.replace('customer', 'so.customer')}
        GROUP BY so.customer
        """,
        params,
        as_dict=True,
    ) if customers is None or customers else []
    pending_orders_map = {row.customer: flt(row.pending_val) for row in so_rows}

    all_cust_keys = set(approved_limits_map) | set(stock_held_map) | set(pending_orders_map)
    total_current_exposure = 0.0
    exceeded_limit_count = 0
    for c in all_cust_keys:
        exp = stock_held_map.get(c, 0.0) + pending_orders_map.get(c, 0.0)
        total_current_exposure += exp
        lim = approved_limits_map.get(c, 0.0)
        if lim > 0 and exp > lim:
            exceeded_limit_count += 1

    # 6. Collections metrics
    si_cond = f"si.docstatus = 1 AND si.outstanding_amount > 0 AND {cust_cond.replace('customer', 'si.customer')}"
    col_rows = frappe.db.sql(
        f"""
        SELECT
            SUM(CASE WHEN DATEDIFF(%s, si.posting_date) BETWEEN 90 AND 120 THEN 1 ELSE 0 END) AS warn_count,
            SUM(CASE WHEN DATEDIFF(%s, si.posting_date) BETWEEN 90 AND 120 THEN si.outstanding_amount ELSE 0.0 END) AS warn_amt,
            SUM(CASE WHEN DATEDIFF(%s, si.posting_date) > 120 THEN 1 ELSE 0 END) AS block_count,
            SUM(CASE WHEN DATEDIFF(%s, si.posting_date) > 120 THEN si.outstanding_amount ELSE 0.0 END) AS block_amt
        FROM `tabSales Invoice` si
        WHERE {si_cond}
        """,
        [date, date, date, date, *params],
        as_dict=True,
    ) if customers is None or customers else []
    warning_count = cint(col_rows[0].warn_count) if col_rows else 0
    warning_amount = flt(col_rows[0].warn_amt) if col_rows else 0.0
    blocked_count = cint(col_rows[0].block_count) if col_rows else 0
    blocked_amount = flt(col_rows[0].block_amt) if col_rows else 0.0

    # 7. Delivery Issues metrics
    deliv_cond = "1=1"
    deliv_params = []
    if not admin:
        assigned_territories = assigned_sales_territories(user)
        if assigned_territories:
            deliv_cond = f"territory IN ({', '.join(['%s']*len(assigned_territories))})"
            deliv_params.extend(assigned_territories)
        else:
            deliv_cond = "(assigned_asm = %s OR assigned_rsm = %s)"
            deliv_params.extend([user, user])

    if frappe.db.table_exists("Delivery Follow-Up Obligation"):
        deliv_rows = frappe.db.sql(
            f"""
            SELECT
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN status = 'Issue Escalated' THEN 1 ELSE 0 END) AS esc_count
            FROM `tabDelivery Follow-Up Obligation`
            WHERE {deliv_cond}
            """,
            deliv_params,
            as_dict=True,
        )
        open_deliv_count = cint(deliv_rows[0].open_count) if deliv_rows else 0
        esc_deliv_count = cint(deliv_rows[0].esc_count) if deliv_rows else 0
    else:
        open_deliv_count = 0
        esc_deliv_count = 0

    return {
        "applications": {
            "pending_count": pending_apps,
            "rfi_count": rfi_apps,
            "approved_this_month": approved_apps,
        },
        "visits": {
            "completed_this_month": completed_visits,
            "upcoming_obligations_count": upcoming_ob,
        },
        "cadence": {
            "rsm_overdue_count": rsm_overdue,
            "rsm_grace_count": rsm_grace,
        },
        "orders": {
            "draft_count": draft_count,
            "submitted_this_month_count": submitted_count,
            "submitted_this_month_value": submitted_value,
        },
        "exposure": {
            "total_retailers": total_retailers,
            "total_approved_limit": total_approved_limit,
            "total_current_exposure": total_current_exposure,
            "exceeded_limit_count": exceeded_limit_count,
        },
        "collections": {
            "warning_count": warning_count,
            "warning_amount": warning_amount,
            "blocked_count": blocked_count,
            "blocked_amount": blocked_amount,
        },
        "delivery_issues": {
            "open_obligations_count": open_deliv_count,
            "escalated_issues_count": esc_deliv_count,
        },
    }


@frappe.whitelist()
def get_unified_sales_worklist(target_date=None):
    """Retrieve prioritized actionable worklist across visits, deliveries, and collections.
    Scoped strictly to the authenticated user's assigned territories and supervision.
    """
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    user = get_current_user()
    admin = is_clothing_admin(user)
    target_dt = getdate(target_date or nowdate())
    customers = _sales_customer_scope()

    if customers is not None and not customers:
        return {"worklist": [], "count": 0}

    worklist = []

    # 1. Delivery Follow-Ups
    if frappe.db.table_exists("Delivery Follow-Up Obligation"):
        deliv_filters = [["status", "in", ["Pending", "Issue Escalated"]]]
        if not admin:
            assigned_territories = assigned_sales_territories(user)
            if assigned_territories:
                deliv_filters.append(["territory", "in", assigned_territories])
            else:
                deliv_filters.append(["assigned_asm", "=", user])
        follow_ups = frappe.get_all(
            "Delivery Follow-Up Obligation",
            filters=deliv_filters,
            fields=["name", "delivery_note", "customer", "customer_name", "territory", "due_date", "status"],
            limit=20,
        )
        for fu in follow_ups:
            priority = "high" if fu.status == "Issue Escalated" or getdate(fu.due_date) < target_dt else "normal"
            worklist.append({
                "type": "delivery_follow_up",
                "reference": fu.name,
                "customer": fu.customer,
                "customer_name": fu.customer_name,
                "territory": fu.territory,
                "title": _("Delivery Follow-Up for {0} (DN: {1})").format(fu.customer_name, fu.delivery_note),
                "due_date": str(fu.due_date),
                "status": fu.status,
                "priority": priority,
            })

    # 2. Overdue Collections
    from sales_erp.cadence import get_collection_obligations
    collections = get_collection_obligations(target_date=str(target_dt), page=1, page_size=20)
    for col in collections.get("collections", []):
        days = cint(col.get("days_elapsed", 0))
        priority = "high" if days >= 120 else "medium"
        worklist.append({
            "type": "collection",
            "reference": col["name"],
            "customer": col["customer"],
            "customer_name": col["customer_name"],
            "territory": col.get("territory"),
            "title": _("Collection Reminder: Invoice {0} overdue by {1} days").format(col["name"], days),
            "due_date": str(col.get("due_date", col["posting_date"])),
            "status": "Order Blocked" if days >= 120 else "Warning",
            "outstanding_amount": flt(col["outstanding_amount"]),
            "priority": priority,
        })

    # Sort worklist: high priority first, then by due_date
    priority_order = {"high": 0, "medium": 1, "normal": 2}
    worklist.sort(key=lambda x: (priority_order.get(x["priority"], 3), x.get("due_date", "")))

    return {"worklist": worklist, "count": len(worklist)}

@frappe.whitelist()
def get_warehouse_dashboard():
    require_role({ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN})
    return {"metrics": {"open_pick_lists": _count("Pick List", {"docstatus": ["!=", 2], "status": ["!=", "Completed"]}), "draft_delivery_notes": _count("Delivery Note", {"docstatus": 0})},
            "pick_tasks": get_pick_lists(), "delivery_notes": get_delivery_notes(),
            "shortcuts": [{"label": "Pick Lists", "url": "/desk/pick-list"}, {"label": "Delivery Notes", "url": "/desk/delivery-note"}]}


@frappe.whitelist()
def get_retailer_directory(search=None, page=1, page_size=20):
    """Permission-aware retailer directory for the salesperson application."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    search = (search or "").strip()[:80]
    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), 50)
    query = {
        "doctype": "Customer",
        "filters": {"disabled": 0},
        "fields": ["name", "customer_name", "territory", "customer_group", "mobile_no", "email_id"],
        "order_by": "customer_name asc, name asc",
        "start": (page - 1) * page_size,
        "limit": page_size + 1,
    }
    if search:
        pattern = f"%{search}%"
        query["or_filters"] = {"name": ["like", pattern], "customer_name": ["like", pattern], "mobile_no": ["like", pattern]}
    rows = frappe.get_list(**query)
    return {"retailers": rows[:page_size], "page": page, "has_more": len(rows) > page_size}


@frappe.whitelist()
def get_retailer_detail(customer):
    """Return one assigned retailer and authorized recent order history."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    if not has_retailer_access(customer):
        frappe.throw(frappe._("You do not have access to this retailer."), frappe.PermissionError)
    retailer = frappe.get_doc("Customer", customer).as_dict(
        no_nulls=True
    )
    allowed = {"name", "customer_name", "territory", "customer_group", "mobile_no", "email_id", "primary_address"}
    return {
        "retailer": {key: retailer[key] for key in allowed if key in retailer},
        "recent_orders": frappe.get_all(
            "Sales Order",
            filters={"customer": customer, "docstatus": ["!=", 2]},
            fields=["name", "transaction_date", "status", "currency", "grand_total"],
            order_by="transaction_date desc, modified desc",
            limit=10,
        ),
    }
