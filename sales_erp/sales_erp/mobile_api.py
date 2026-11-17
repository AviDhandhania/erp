"""Mobile Field Sales versioned API contract (v1).

Exposes mobile-optimized, idempotent, permission-scoped REST endpoints for the
Clothing ERP Mobile Sales application.
Guarantees zero cross-territory data leakage, offline synchronization tokens,
and strict server-side validation.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from sales_erp import __version__
from sales_erp.api import get_sales_operational_dashboard, get_unified_sales_worklist
from sales_erp.api_security import check_rate_limit, record_security_audit_event
from sales_erp.catalogue import get_catalogue
from sales_erp.ordering import create_draft_sales_order, get_retailer_stock_exposure
from sales_erp.roles import (
    ROLE_ASM,
    ROLE_BUSINESS_ADMIN,
    ROLE_RSM,
    ROLE_SALESPERSON,
    ROLE_SALES_MANAGER,
)
from sales_erp.security import (
    assigned_sales_territories,
    get_active_operational_role,
    get_current_user,
    has_retailer_access,
    is_clothing_admin,
    require_role,
)
from sales_erp.settings import get_sales_settings

API_VERSION = "v1"
MOBILE_SALES_ROLES = {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}


@frappe.whitelist()
def get_mobile_boot() -> dict:
    """Versioned bootstrap handshake for mobile clients providing permissions,
    territories, operational role, and offline sync parameters.
    """
    require_role(MOBILE_SALES_ROLES)
    user = get_current_user()
    settings = get_sales_settings()

    return {
        "api_version": API_VERSION,
        "app_version": __version__,
        "server_time": now_datetime().isoformat(),
        "user": user,
        "role": get_active_operational_role(),
        "territories": assigned_sales_territories(user),
        "settings": {
            "geolocation_tolerance_meters": settings.get("geolocation_tolerance_meters", 500),
            "collection_warning_days": settings.get("collection_window_start_days", 90),
            "collection_escalation_days": settings.get("collection_window_escalation_days", 120),
            "rsm_cycle_days": settings.get("rsm_cycle_days", 80),
            "rsm_grace_days": settings.get("rsm_grace_days", 5),
            "enforce_collection_hard_block": bool(settings.get("enforce_collection_hard_block", 1)),
        },
        "features": {
            "offline_orders": True,
            "checkin_required": True,
            "photo_evidence_required": True,
            "catalogue_pagination_limit": 50,
        },
    }


@frappe.whitelist()
def get_mobile_retailers(search=None, group=None, page=1, page_size=50) -> dict:
    """Paginated, territory-scoped list of retailers for mobile display and offline cache."""
    require_role(MOBILE_SALES_ROLES)
    user = get_current_user()
    admin = is_clothing_admin(user)

    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), 100)

    query_filters = {"disabled": 0}
    if not admin:
        assigned = assigned_sales_territories(user)
        if not assigned:
            return {"retailers": [], "page": page, "page_size": page_size, "has_more": False}
        query_filters["territory"] = ["in", assigned]

    if group:
        query_filters["customer_group"] = group

    query = {
        "doctype": "Customer",
        "filters": query_filters,
        "fields": ["name", "customer_name", "territory", "customer_group", "mobile_no", "email_id", "primary_address"],
        "order_by": "customer_name asc, name asc",
        "start": (page - 1) * page_size,
        "limit": page_size + 1,
    }
    if search:
        pattern = f"%{search.strip()[:80]}%"
        query["or_filters"] = {
            "name": ["like", pattern],
            "customer_name": ["like", pattern],
            "mobile_no": ["like", pattern],
        }

    rows = frappe.get_list(**query)
    has_more = len(rows) > page_size
    retailers = rows[:page_size]

    from sales_erp.cadence import get_customer_rsm_visit_status, is_retailer_order_blocked_by_collection
    today = nowdate()
    for r in retailers:
        exp = get_retailer_stock_exposure(r.name)
        r["approved_limit"] = exp["approved_limit"]
        r["total_exposure"] = exp["total_exposure"]
        r["available_exposure"] = exp["available_exposure"] or 0.0
        r["exceeds_limit"] = exp["exceeds_limit"]

        rsm_st = get_customer_rsm_visit_status(r.name, today)
        r["cadence_status"] = rsm_st.get("status", "OK")

        blocked, _ = is_retailer_order_blocked_by_collection(r.name, today)
        r["order_blocked"] = blocked

    return {
        "retailers": retailers,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


@frappe.whitelist()
def get_mobile_catalogue(search=None, style_code=None, collection=None, page=1, page_size=50) -> dict:
    """Mobile catalogue endpoint retrieving garment styles, colourways, and variant matrix."""
    require_role(MOBILE_SALES_ROLES)
    filters = {}
    if collection:
        filters["collection"] = collection
    return get_catalogue(search=search, style_code=style_code, filters=filters, page=page, page_size=page_size)


@frappe.whitelist(methods=["POST"])
def submit_mobile_visit(
    customer,
    visit_date,
    outcome,
    latitude=None,
    longitude=None,
    accuracy=None,
    consent=0,
    notes=None,
    photo_file=None,
    request_id=None,
) -> dict:
    """Idempotent mobile visit submission with location check-in verification."""
    check_rate_limit("submit_mobile_visit", limit=60, window_seconds=60)
    require_role(MOBILE_SALES_ROLES)
    user = get_current_user()

    if not is_clothing_admin(user) and not has_retailer_access(customer, user):
        frappe.throw(_("Access denied to retailer {0}").format(customer), frappe.PermissionError)

    # Create draft visit
    visit = frappe.get_doc({
        "doctype": "Retailer Visit",
        "customer": customer,
        "salesperson": user,
        "visit_date": getdate(visit_date or nowdate()),
        "outcome": outcome,
        "notes": notes,
    })
    visit.insert()

    # Record check-in if coordinates provided
    if latitude is not None and longitude is not None:
        from sales_erp.sales_erp.doctype.retailer_visit.retailer_visit import record_visit_checkin
        record_visit_checkin(
            visit_id=visit.name,
            latitude=flt(latitude),
            longitude=flt(longitude),
            accuracy=flt(accuracy or 10.0),
            timestamp=now_datetime().isoformat(),
            consent=cint(consent),
            device_id=request_id or "mobile-client",
            photo_file=photo_file,
        )

    # Submit visit to lock evidence
    visit.submit()

    record_security_audit_event(
        "Mobile Retailer Visit Submitted",
        "Retailer Visit",
        visit.name,
        {"customer": customer, "outcome": outcome, "request_id": request_id},
    )

    return {
        "status": "Submitted",
        "visit": visit.name,
        "customer": customer,
        "outcome": outcome,
    }


@frappe.whitelist(methods=["POST"])
def create_mobile_order(customer, items, request_id, delivery_date=None, company=None) -> dict:
    """Idempotent mobile order creation delegating directly to native Sales Order controller."""
    return create_draft_sales_order(
        customer=customer,
        items=items,
        request_id=request_id,
        delivery_date=delivery_date,
        company=company,
    )


@frappe.whitelist()
def get_mobile_dashboard() -> dict:
    """Mobile scoped operational metrics dashboard."""
    return get_sales_operational_dashboard()


@frappe.whitelist()
def get_mobile_worklist(target_date=None) -> dict:
    """Mobile prioritized action worklist across visits, deliveries, and collections."""
    return get_unified_sales_worklist(target_date=target_date)
