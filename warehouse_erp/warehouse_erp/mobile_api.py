# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Versioned Mobile API Contract for Warehouse ERP (v1).
Exposes lightweight, mobile-optimized, versioned endpoints for warehouse fulfillment,
barcode scanning, pick-pack-dispatch workflows, and delivery handoffs.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from warehouse_erp.api_security import check_rate_limit, record_security_audit_event
from warehouse_erp.fulfillment import (
    complete_pick_list,
    create_delivery_note_from_pick,
    create_packing_slip,
    dispatch_delivery_note,
    get_fulfillment_task,
    get_fulfillment_tasks,
    get_warehouse_work_queues,
    record_delivery_handoff,
    undo_pick_item_scan,
    verify_pick_item,
)
from warehouse_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_WAREHOUSE_MANAGER
from warehouse_erp.security import (
    assigned_warehouses,
    get_current_user,
    is_warehouse_admin,
    require_role,
)

API_VERSION = "v1"
APP_VERSION = "1.0.0"
MOBILE_WAREHOUSE_ROLES = {ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN}


@frappe.whitelist()
def get_mobile_warehouse_boot():
    """Return mobile bootstrap state including active warehouse manager context,
    assigned warehouses, system capabilities, and version contract.
    """
    check_rate_limit("get_mobile_warehouse_boot", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    user = get_current_user()
    admin = is_warehouse_admin(user)
    warehouses = assigned_warehouses(user) if not admin else ["*"]

    return {
        "api_version": API_VERSION,
        "app_version": APP_VERSION,
        "server_time": now_datetime().isoformat(),
        "user": user,
        "role": ROLE_BUSINESS_ADMIN if admin else ROLE_WAREHOUSE_MANAGER,
        "assigned_warehouses": warehouses,
        "features": {
            "barcode_scanner": True,
            "serial_tracking": True,
            "batch_tracking": True,
            "expiry_validation": True,
            "package_dimension_capture": True,
            "offline_scanning": True,
            "immutable_delivery_handoff": True,
            "default_page_size": 20,
        },
    }


@frappe.whitelist()
def get_mobile_tasks(task_type="pick", state="all", page=1, page_size=20, search=None):
    """Return paginated fulfillment tasks for mobile list views."""
    check_rate_limit("get_mobile_tasks", limit=120, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    data = get_fulfillment_tasks(
        task_type=task_type,
        state=state,
        search=search,
        page=page,
        page_size=page_size,
    )
    return {
        "api_version": API_VERSION,
        "task_type": data["task_type"],
        "tasks": data["tasks"],
        "pagination": data["pagination"],
    }


@frappe.whitelist()
def get_mobile_task_detail(task_type, name):
    """Return task detail projection optimized for mobile picking, packing, and dispatch."""
    check_rate_limit("get_mobile_task_detail", limit=120, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    detail = get_fulfillment_task(task_type=task_type, name=name)
    detail["api_version"] = API_VERSION
    return detail


@frappe.whitelist(methods=["POST"])
def verify_mobile_scan(pick_list, location, barcode, quantity=1, warehouse=None):
    """Verify single or bulk barcode scan for a Pick List row."""
    check_rate_limit("verify_mobile_scan", limit=180, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = verify_pick_item(
        pick_list=pick_list,
        location=location,
        barcode=barcode,
        quantity=quantity,
        warehouse=warehouse,
    )
    res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def undo_mobile_scan(pick_list, location, barcode=None, quantity=1):
    """Reverse a scanned item quantity."""
    check_rate_limit("undo_mobile_scan", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = undo_pick_item_scan(
        pick_list=pick_list,
        location=location,
        barcode=barcode,
        quantity=quantity,
    )
    res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def complete_mobile_pick(pick_list):
    """Submit a completed Pick List from mobile scanner."""
    check_rate_limit("complete_mobile_pick", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = complete_pick_list(pick_list)
    res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def create_mobile_delivery_note(pick_list):
    """Generate native draft Delivery Note from a submitted Pick List."""
    check_rate_limit("create_mobile_delivery_note", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = create_delivery_note_from_pick(pick_list)
    res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def create_mobile_packing_slip(
    delivery_note,
    from_case_no=None,
    to_case_no=None,
    gross_weight_pkg=0.0,
    net_weight_pkg=0.0,
    package_barcode=None,
    length=None,
    width=None,
    height=None,
    dimension_uom="cm",
):
    """Create a packing slip with package identity and dimensions."""
    check_rate_limit("create_mobile_packing_slip", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = create_packing_slip(
        delivery_note=delivery_note,
        from_case_no=from_case_no,
        to_case_no=to_case_no,
        gross_weight_pkg=gross_weight_pkg,
        net_weight_pkg=net_weight_pkg,
        package_barcode=package_barcode,
        length=length,
        width=width,
        height=height,
        dimension_uom=dimension_uom,
    )
    res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def dispatch_mobile_delivery(
    delivery_note,
    transporter_name=None,
    vehicle_no=None,
    lr_no=None,
    lr_date=None,
):
    """Submit and dispatch Delivery Note with carrier tracking details."""
    check_rate_limit("dispatch_mobile_delivery", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = dispatch_delivery_note(
        delivery_note=delivery_note,
        transporter_name=transporter_name,
        vehicle_no=vehicle_no,
        lr_no=lr_no,
        lr_date=lr_date,
    )
    res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def record_mobile_handoff(
    delivery_note,
    transporter_name,
    accepted_by_handler,
    packages_count=1,
    gross_weight=0.0,
    vehicle_no=None,
    lr_no=None,
    lr_date=None,
    driver_name=None,
    driver_phone=None,
    proof_photo=None,
    notes=None,
    request_id=None,
):
    """Record an immutable delivery handoff event with carrier signature/name."""
    check_rate_limit("record_mobile_handoff", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = record_delivery_handoff(
        delivery_note=delivery_note,
        transporter_name=transporter_name,
        accepted_by_handler=accepted_by_handler,
        packages_count=packages_count,
        gross_weight=gross_weight,
        vehicle_no=vehicle_no,
        lr_no=lr_no,
        lr_date=lr_date,
        driver_name=driver_name,
        driver_phone=driver_phone,
        proof_photo=proof_photo,
        notes=notes,
        request_id=request_id,
    )
    res["api_version"] = API_VERSION
    return res


@frappe.whitelist()
def get_mobile_work_queues(warehouse=None, queue_type="wave"):
    """Retrieve wave or route work queues for mobile operators."""
    check_rate_limit("get_mobile_work_queues", limit=60, window_seconds=60)
    require_role(MOBILE_WAREHOUSE_ROLES)
    res = get_warehouse_work_queues(warehouse=warehouse, queue_type=queue_type)
    res["api_version"] = API_VERSION
    return res
