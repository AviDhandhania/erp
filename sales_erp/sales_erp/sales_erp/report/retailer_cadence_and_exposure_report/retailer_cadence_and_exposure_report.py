"""Permission-aware operational report evaluating retailer cadence obligations and credit exposure."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from sales_erp.cadence import (
    get_customer_rsm_visit_status,
    is_retailer_order_blocked_by_collection,
)
from sales_erp.ordering import get_retailer_stock_exposure
from sales_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER
from sales_erp.security import (
    assigned_sales_territories,
    get_current_user,
    is_clothing_admin,
    require_role,
)
from sales_erp.supervision import get_territory_supervision


def execute(filters=None):
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    filters = frappe._dict(filters or {})
    data = _get_data(filters)

    counts = Counter(row["cadence_status"] for row in data)
    chart = {
        "data": {
            "labels": ["OK", "Upcoming", "Grace", "Overdue"],
            "datasets": [
                {
                    "name": _("Retailers"),
                    "values": [counts.get("OK", 0), counts.get("Upcoming", 0), counts.get("Grace", 0), counts.get("Overdue", 0)],
                }
            ],
        },
        "type": "donut",
    }
    exceeded_count = sum(1 for row in data if row["exposure_status"] == "Exceeded Limit")
    blocked_count = sum(1 for row in data if row["order_block_status"] == "Blocked")
    summary = [
        {
            "value": len(data),
            "label": _("Total Retailers"),
            "datatype": "Int",
            "indicator": "Blue",
        },
        {
            "value": exceeded_count,
            "label": _("Exceeded Exposure"),
            "datatype": "Int",
            "indicator": "Red" if exceeded_count else "Green",
        },
        {
            "value": counts.get("Overdue", 0),
            "label": _("Overdue Cadence"),
            "datatype": "Int",
            "indicator": "Red" if counts.get("Overdue", 0) else "Green",
        },
        {
            "value": blocked_count,
            "label": _("Order Blocked"),
            "datatype": "Int",
            "indicator": "Orange" if blocked_count else "Blue",
        },
    ]
    return _columns(), data, None, chart, summary


def _get_data(filters):
    user = get_current_user()
    admin = is_clothing_admin(user)
    today = nowdate()

    query_filters = {"disabled": 0}
    if not admin:
        assigned = assigned_sales_territories(user)
        if not assigned:
            return []
        query_filters["territory"] = ["in", assigned]

    if filters.territory:
        if not admin and filters.territory not in (assigned or []):
            return []
        query_filters["territory"] = filters.territory

    if filters.customer_group:
        query_filters["customer_group"] = filters.customer_group

    customers = frappe.get_list(
        "Customer",
        filters=query_filters,
        fields=["name", "customer_name", "territory", "customer_group"],
        order_by="territory asc, customer_name asc",
        limit_page_length=0,
    )

    data = []
    for c in customers:
        supervision = get_territory_supervision(c.territory, on_date=today) if c.territory else None
        asm = supervision.asm if supervision else ""
        rsm = supervision.rsm if supervision else ""

        exposure = get_retailer_stock_exposure(c.name)
        approved_limit = exposure["approved_limit"]
        stock_held = exposure["stock_held_at_shop"]
        pending_orders = exposure["pending_orders_value"]
        total_exposure = exposure["total_exposure"]
        available_exposure = exposure["available_exposure"]
        exceeded = exposure["exceeds_limit"]
        exp_status = "Exceeded Limit" if exceeded else "Normal"

        rsm_status = get_customer_rsm_visit_status(c.name, today)
        cadence_status = rsm_status.get("status", "OK")
        last_rsm_visit = rsm_status.get("last_visit_date")

        blocked, _ = is_retailer_order_blocked_by_collection(c.name, today)
        block_status = "Blocked" if blocked else "Active"

        if filters.exposure_status and filters.exposure_status != "All" and exp_status != filters.exposure_status:
            continue
        if filters.cadence_status and filters.cadence_status != "All" and cadence_status != filters.cadence_status:
            continue

        data.append({
            "customer": c.name,
            "customer_name": c.customer_name,
            "territory": c.territory,
            "customer_group": c.customer_group,
            "assigned_asm": asm,
            "supervising_rsm": rsm,
            "approved_limit": approved_limit,
            "stock_held_at_shop": stock_held,
            "pending_orders_value": pending_orders,
            "total_exposure": total_exposure,
            "available_exposure": available_exposure or 0.0,
            "exposure_status": exp_status,
            "cadence_status": cadence_status,
            "last_rsm_visit": str(last_rsm_visit) if last_rsm_visit else "",
            "order_block_status": block_status,
        })

    return data


def _columns():
    return [
        {"label": _("Retailer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 140},
        {"label": _("Retailer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
        {"label": _("Territory"), "fieldname": "territory", "fieldtype": "Link", "options": "Territory", "width": 140},
        {"label": _("Operating Type"), "fieldname": "customer_group", "fieldtype": "Link", "options": "Customer Group", "width": 140},
        {"label": _("ASM"), "fieldname": "assigned_asm", "fieldtype": "Data", "width": 140},
        {"label": _("RSM"), "fieldname": "supervising_rsm", "fieldtype": "Data", "width": 140},
        {"label": _("Approved Limit"), "fieldname": "approved_limit", "fieldtype": "Currency", "width": 130},
        {"label": _("Stock at Shop"), "fieldname": "stock_held_at_shop", "fieldtype": "Currency", "width": 130},
        {"label": _("Pending Orders"), "fieldname": "pending_orders_value", "fieldtype": "Currency", "width": 130},
        {"label": _("Total Exposure"), "fieldname": "total_exposure", "fieldtype": "Currency", "width": 130},
        {"label": _("Available Exposure"), "fieldname": "available_exposure", "fieldtype": "Currency", "width": 130},
        {"label": _("Exposure Status"), "fieldname": "exposure_status", "fieldtype": "Data", "width": 120},
        {"label": _("Cadence Status"), "fieldname": "cadence_status", "fieldtype": "Data", "width": 120},
        {"label": _("Last RSM Visit"), "fieldname": "last_rsm_visit", "fieldtype": "Date", "width": 110},
        {"label": _("Order Status"), "fieldname": "order_block_status", "fieldtype": "Data", "width": 110},
    ]
