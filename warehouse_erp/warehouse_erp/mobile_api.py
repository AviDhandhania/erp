# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Versioned Mobile API Contract for Warehouse ERP (v1).
Exposes lightweight, mobile-optimized, versioned endpoints for warehouse fulfillment,
barcode scanning, pick-pack-dispatch workflows, and delivery handoffs.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from warehouse_erp import labels, returns
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
            "customer_returns": True,
            "refurbishment_tracking": True,
            "thermal_label_printing": True,
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


@frappe.whitelist(methods=["POST"])
def intake_mobile_return(
    delivery_note,
    item_code,
    quantity,
    quarantine_warehouse,
    return_reason,
    serial_no=None,
    batch_no=None,
    photo_evidence=None,
    notes=None,
    request_id=None,
):
    """Intake customer return garment into quarantine isolation via mobile scanner."""
    check_rate_limit("intake_mobile_return", limit=60, window_seconds=60)
    res = returns.intake_customer_return(
        delivery_note=delivery_note,
        item_code=item_code,
        quantity=quantity,
        quarantine_warehouse=quarantine_warehouse,
        return_reason=return_reason,
        serial_no=serial_no,
        batch_no=batch_no,
        photo_evidence=photo_evidence,
        notes=notes,
        request_id=request_id,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def move_mobile_refurbishment(
    quarantine_name,
    refurbishment_warehouse,
    request_id=None,
):
    """Move inspected garment to refurbishment staging."""
    check_rate_limit("move_mobile_refurbishment", limit=60, window_seconds=60)
    res = returns.move_to_refurbishment(
        quarantine_name=quarantine_name,
        refurbishment_warehouse=refurbishment_warehouse,
        request_id=request_id,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def assign_mobile_refurbishment(
    quarantine_name,
    assignee,
    operation,
    estimated_cost=0.0,
    consumed_material=None,
    photo_before=None,
    notes=None,
    request_id=None,
):
    """Assign refurbishment operation to a technician."""
    check_rate_limit("assign_mobile_refurbishment", limit=60, window_seconds=60)
    res = returns.assign_refurbishment(
        quarantine_name=quarantine_name,
        assignee=assignee,
        operation=operation,
        estimated_cost=estimated_cost,
        consumed_material=consumed_material,
        photo_before=photo_before,
        notes=notes,
        request_id=request_id,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def complete_mobile_refurbishment_work(
    quarantine_name,
    photo_after=None,
    consumed_material=None,
    actual_cost=None,
    notes=None,
    require_reinspection=True,
    request_id=None,
):
    """Record completion of refurbishment work and submit for reinspection."""
    check_rate_limit("complete_mobile_refurbishment_work", limit=60, window_seconds=60)
    res = returns.complete_refurbishment_work(
        quarantine_name=quarantine_name,
        photo_after=photo_after,
        consumed_material=consumed_material,
        actual_cost=actual_cost,
        notes=notes,
        require_reinspection=require_reinspection,
        request_id=request_id,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def reinspect_mobile_refurbishment(
    quarantine_name,
    decision,
    notes=None,
    request_id=None,
):
    """Reinspect refurbished garment (Passed or Rejected)."""
    check_rate_limit("reinspect_mobile_refurbishment", limit=60, window_seconds=60)
    res = returns.post_refurbishment_reinspection(
        quarantine_name=quarantine_name,
        decision=decision,
        notes=notes,
        request_id=request_id,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def complete_mobile_refurbishment(
    quarantine_name,
    target_saleable_warehouse,
    notes=None,
    request_id=None,
):
    """Restock passed refurbished garment to saleable stock."""
    check_rate_limit("complete_mobile_refurbishment", limit=60, window_seconds=60)
    res = returns.complete_refurbishment(
        quarantine_name=quarantine_name,
        target_saleable_warehouse=target_saleable_warehouse,
        notes=notes,
        request_id=request_id,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist()
def get_mobile_return_financial_status(delivery_note_or_quarantine):
    """Query return financial status (pending commercial approval)."""
    check_rate_limit("get_mobile_return_financial_status", limit=60, window_seconds=60)
    res = returns.get_return_financial_status(delivery_note_or_quarantine)
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist()
def get_mobile_returns_dashboard(warehouse=None):
    """Return operational return & refurbishment SLA queues."""
    check_rate_limit("get_mobile_returns_dashboard", limit=60, window_seconds=60)
    res = returns.get_returns_operational_dashboard(warehouse=warehouse)
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist()
def get_mobile_document_label(doctype, name, label_type=None, label_format="html"):
    """Get label or manifest data and formatted template for mobile/thermal printing."""
    check_rate_limit("get_mobile_document_label", limit=120, window_seconds=60)
    res = labels.get_document_label(
        doctype=doctype,
        name=name,
        label_type=label_type,
        label_format=label_format,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res


@frappe.whitelist(methods=["POST"])
def print_mobile_task_label(doctype, name, label_type=None, label_format="html", simulate_failure=False):
    """Print label or manifest with audit tracking and reprint watermark."""
    check_rate_limit("print_mobile_task_label", limit=60, window_seconds=60)
    res = labels.print_task_label(
        doctype=doctype,
        name=name,
        label_type=label_type,
        label_format=label_format,
        simulate_failure=simulate_failure,
    )
    if isinstance(res, dict):
        res["api_version"] = API_VERSION
    return res
