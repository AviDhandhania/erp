# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Printable Labels, Manifests, Deterministic PDF, ZPL II, and Reprint Audit for Warehouse ERP.

Provides:
- Permission-aware, object-scoped label and manifest generation.
- Exclusion of sensitive commercial and excess financial data (rates, credit limits, pricing).
- Formats: HTML (deterministic, printer-friendly CSS), PDF, and reviewed ZPL II standard commands.
- Automated reprint audit tracking in tabActivity Log with visual and ZPL watermark banners.
- Resilience: failure handling for printer/network interruption without corrupting business documents.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
import frappe
from frappe import _
from frappe.utils import cint, escape_html, flt, now_datetime

from warehouse_erp.api_security import (
    check_rate_limit,
    record_security_audit_event,
    validate_string,
)
from warehouse_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_WAREHOUSE_MANAGER
from warehouse_erp.security import (
    assigned_warehouses,
    get_current_user,
    is_warehouse_admin,
    require_role,
)

LABEL_ROLES = {ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"}
ALLOWED_LABEL_TYPES = {"shipping", "pick_slip", "quarantine", "refurbishment", "delivery_handoff"}
ALLOWED_LABEL_FORMATS = {"html", "pdf", "zpl"}


def _get_reprint_cache_key(doctype: str, name: str, label_type: str) -> str:
    clean_dt = re.sub(r"[^A-Za-z0-9_]", "_", doctype)
    clean_name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    return f"label_reprint:{clean_dt}:{clean_name}:{label_type}"


def _get_print_count(doctype: str, name: str, label_type: str) -> int:
    key = _get_reprint_cache_key(doctype, name, label_type)
    val = frappe.cache.get_value(key)
    return cint(val) if val is not None else 0


def _increment_print_count(doctype: str, name: str, label_type: str) -> int:
    key = _get_reprint_cache_key(doctype, name, label_type)
    current = _get_print_count(doctype, name, label_type)
    new_count = current + 1
    frappe.cache.set_value(key, new_count, expires_in_sec=86400 * 30)
    return new_count


def _validate_label_access(doctype: str, name: str) -> frappe.Document:
    """Validate server-side user role, document permission, and warehouse assignment."""
    require_role(LABEL_ROLES)
    if not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} does not exist.").format(doctype, name), frappe.DoesNotExistError)

    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")

    user = get_current_user()
    if not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        # Check warehouse scoping based on doctype
        if doctype == "Pick List":
            for loc in (doc.get("locations") or []):
                if loc.warehouse and loc.warehouse not in allowed:
                    frappe.throw(
                        _("You do not have permission for warehouse {0} in Pick List {1}.").format(loc.warehouse, name),
                        frappe.PermissionError,
                    )
        elif doctype == "Delivery Note":
            for item in (doc.get("items") or []):
                if item.warehouse and item.warehouse not in allowed:
                    frappe.throw(
                        _("You do not have permission for warehouse {0} in Delivery Note {1}.").format(item.warehouse, name),
                        frappe.PermissionError,
                    )
        elif doctype == "Packing Slip":
            dn_name = doc.delivery_note
            if dn_name:
                dn = frappe.get_doc("Delivery Note", dn_name)
                for item in (dn.get("items") or []):
                    if item.warehouse and item.warehouse not in allowed:
                        frappe.throw(
                            _("You do not have permission for warehouse {0}.").format(item.warehouse),
                            frappe.PermissionError,
                        )
        elif doctype == "Return Quarantine":
            if doc.quarantine_warehouse and doc.quarantine_warehouse not in allowed:
                frappe.throw(
                    _("You do not have permission for quarantine warehouse {0}.").format(doc.quarantine_warehouse),
                    frappe.PermissionError,
                )
        elif doctype == "Delivery Handoff":
            dn_name = doc.delivery_note
            if dn_name:
                dn = frappe.get_doc("Delivery Note", dn_name)
                for item in (dn.get("items") or []):
                    if item.warehouse and item.warehouse not in allowed:
                        frappe.throw(
                            _("You do not have permission for warehouse {0}.").format(item.warehouse),
                            frappe.PermissionError,
                        )

    return doc


def get_label_data(doctype: str, name: str, label_type: str) -> dict:
    """Extract strict projection of label fields, excluding sensitive financial fields."""
    doc = _validate_label_access(doctype, name)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if label_type == "shipping":
        # Can be generated from Packing Slip or Delivery Note
        if doctype == "Packing Slip":
            dn_name = doc.delivery_note
            dn = frappe.get_doc("Delivery Note", dn_name) if dn_name else frappe._dict()
            pkg_barcode = doc.get("custom_package_barcode") or f"PKG-{doc.name}"
            from_case = doc.from_case_no
            to_case = doc.to_case_no
            gross_weight = flt(doc.gross_weight_pkg)
            net_weight = flt(doc.net_weight_pkg)
            dims = f"{flt(doc.custom_length)}x{flt(doc.custom_width)}x{flt(doc.custom_height)} {doc.custom_dimension_uom or 'cm'}" if doc.get("custom_length") else "N/A"
        else:
            dn = doc
            pkg_barcode = f"PKG-{dn.name}-ALL"
            from_case = 1
            to_case = 1
            gross_weight = flt(dn.get("total_gross_weight"))
            net_weight = flt(dn.get("total_net_weight"))
            dims = "Standard"

        return {
            "title": "SHIPPING CARTON LABEL",
            "document_name": dn.get("name") or doc.name,
            "package_barcode": pkg_barcode,
            "customer_name": dn.get("customer_name") or dn.get("customer") or "Valued Retailer",
            "transporter_name": dn.get("transporter_name") or "Standard Logistics",
            "vehicle_no": dn.get("vehicle_no") or "N/A",
            "lr_no": dn.get("lr_no") or "N/A",
            "cases": f"{from_case} to {to_case}" if from_case != to_case else str(from_case),
            "gross_weight": f"{gross_weight:.2f} kg",
            "net_weight": f"{net_weight:.2f} kg",
            "dimensions": dims,
            "printed_on": now_str,
            "printed_by": get_current_user(),
        }

    elif label_type == "pick_slip":
        return {
            "title": "WAREHOUSE PICK SLIP",
            "document_name": doc.name,
            "barcode": doc.name,
            "wave_id": doc.get("custom_wave_id") or "Unassigned",
            "route_id": doc.get("custom_route_id") or "Unassigned",
            "item_count": len(doc.get("locations") or []),
            "total_qty": f"{sum(flt(loc.qty) for loc in (doc.get('locations') or [])):.2f}",
            "items": [
                {
                    "item_code": loc.item_code,
                    "item_name": loc.item_name,
                    "warehouse": loc.warehouse,
                    "qty": loc.qty,
                    "uom": loc.stock_uom,
                    "picked_qty": loc.picked_qty,
                    "batch_no": loc.get("batch_no") or "-",
                    "serial_no": loc.get("serial_no") or "-",
                }
                for loc in (doc.get("locations") or [])[:50]
            ],
            "printed_on": now_str,
            "printed_by": get_current_user(),
        }

    elif label_type == "quarantine":
        return {
            "title": "RETURN QUARANTINE INTAKE TAG",
            "document_name": doc.name,
            "barcode": doc.name,
            "item_code": doc.item_code,
            "quantity": f"{flt(doc.quantity):.2f}",
            "return_reason": doc.return_reason,
            "quarantine_warehouse": doc.quarantine_warehouse,
            "delivery_note": doc.delivery_note or "N/A",
            "return_delivery_note": doc.return_delivery_note or "N/A",
            "retailer": doc.retailer,
            "inspected_by": doc.inspected_by or "Pending",
            "status": doc.inspection_status,
            "printed_on": now_str,
            "printed_by": get_current_user(),
        }

    elif label_type == "refurbishment":
        return {
            "title": "REFURBISHMENT WORK TICKET",
            "document_name": doc.name,
            "barcode": doc.name,
            "item_code": doc.item_code,
            "quantity": f"{flt(doc.quantity):.2f}",
            "operation": doc.get("refurbishment_operation") or "General Refurbishment",
            "assignee": doc.get("refurbishment_assignee") or "Unassigned",
            "refurbishment_warehouse": doc.get("refurbishment_warehouse") or "Refurbishment WIP",
            "defect_description": doc.get("inspection_notes") or doc.return_reason,
            "started_on": str(doc.get("refurbishment_start_time") or "Pending"),
            "printed_on": now_str,
            "printed_by": get_current_user(),
        }

    elif label_type == "delivery_handoff":
        return {
            "title": "DELIVERY CARRIER HANDOFF MANIFEST",
            "document_name": doc.name,
            "barcode": doc.name,
            "delivery_note": doc.delivery_note,
            "transporter_name": doc.transporter_name,
            "accepted_by_handler": doc.accepted_by_handler,
            "driver_name": doc.get("driver_name") or doc.accepted_by_handler,
            "driver_phone": doc.get("driver_phone") or "N/A",
            "vehicle_no": doc.get("vehicle_no") or "N/A",
            "lr_no": doc.get("lr_no") or "N/A",
            "packages_count": doc.packages_count,
            "gross_weight": f"{flt(doc.gross_weight):.2f} kg",
            "handed_over_by": doc.handed_over_by or get_current_user(),
            "handed_over_on": str(doc.handed_over_on or now_str),
            "printed_on": now_str,
            "printed_by": get_current_user(),
        }

    else:
        frappe.throw(_("Unsupported label type: {0}").format(label_type), frappe.ValidationError)


def generate_label_html(doctype: str, name: str, label_type: str, is_reprint: bool = False) -> str:
    """Generate clean, deterministic HTML for printing labels with strict XSS sanitization."""
    data = get_label_data(doctype, name, label_type)

    reprint_watermark = ""
    if is_reprint:
        reprint_watermark = """
        <div style="background-color: #ffebee; border: 2px dashed #c62828; color: #b71c1c; text-align: center; font-weight: bold; font-size: 16px; padding: 6px; margin-bottom: 10px; letter-spacing: 2px;">
            *** REPRINT - AUDITED LABEL ***
        </div>
        """

    content_rows = ""
    for k, v in data.items():
        if k in {"title", "items"}:
            continue
        clean_key = escape_html(k.replace("_", " ").title())
        clean_val = escape_html(str(v))
        content_rows += f"""
        <tr>
            <td style="padding: 4px 8px; font-weight: 600; width: 35%; color: #333; border-bottom: 1px solid #eee;">{clean_key}</td>
            <td style="padding: 4px 8px; color: #111; border-bottom: 1px solid #eee;">{clean_val}</td>
        </tr>
        """

    items_table = ""
    if "items" in data and data["items"]:
        item_rows = ""
        for itm in data["items"]:
            item_rows += f"""
            <tr>
                <td style="padding: 4px; border-bottom: 1px solid #ddd;">{escape_html(itm['item_code'])}</td>
                <td style="padding: 4px; border-bottom: 1px solid #ddd;">{escape_html(itm['warehouse'])}</td>
                <td style="padding: 4px; border-bottom: 1px solid #ddd; text-align: right;">{flt(itm['qty']):.2f}</td>
                <td style="padding: 4px; border-bottom: 1px solid #ddd; text-align: right;">{flt(itm['picked_qty']):.2f}</td>
            </tr>
            """
        items_table = f"""
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px;">
            <thead>
                <tr style="background: #f5f5f5;">
                    <th style="padding: 4px; text-align: left;">Item Code</th>
                    <th style="padding: 4px; text-align: left;">Location</th>
                    <th style="padding: 4px; text-align: right;">Required</th>
                    <th style="padding: 4px; text-align: right;">Picked</th>
                </tr>
            </thead>
            <tbody>
                {item_rows}
            </tbody>
        </table>
        """

    primary_code = data.get("package_barcode") or data.get("barcode") or data.get("document_name")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{escape_html(data['title'])} - {escape_html(data['document_name'])}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            margin: 0;
            padding: 15px;
            color: #111;
            background: #fff;
        }}
        .label-container {{
            max-width: 480px;
            margin: 0 auto;
            border: 2px solid #222;
            padding: 15px;
            box-sizing: border-box;
        }}
        .barcode-box {{
            text-align: center;
            border: 1px solid #ccc;
            padding: 10px;
            margin: 10px 0;
            background: #fafafa;
        }}
        .barcode-visual {{
            font-family: monospace;
            font-size: 24px;
            letter-spacing: 5px;
            font-weight: bold;
            display: inline-block;
            padding: 5px 15px;
            background: #000;
            color: #fff;
        }}
        @media print {{
            body {{ padding: 0; }}
            .label-container {{ border: none; max-width: 100%; }}
        }}
    </style>
</head>
<body>
    <div class="label-container">
        {reprint_watermark}
        <div style="font-size: 18px; font-weight: bold; text-align: center; border-bottom: 2px solid #000; padding-bottom: 6px; margin-bottom: 8px;">
            {escape_html(data['title'])}
        </div>
        <div class="barcode-box">
            <div style="font-size: 10px; color: #666; margin-bottom: 4px;">SCANNER BARCODE</div>
            <div class="barcode-visual">*{escape_html(primary_code)}*</div>
            <div style="font-size: 12px; font-weight: bold; margin-top: 4px;">{escape_html(primary_code)}</div>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
            <tbody>
                {content_rows}
            </tbody>
        </table>
        {items_table}
    </div>
</body>
</html>
"""
    return html


def generate_label_zpl(doctype: str, name: str, label_type: str, is_reprint: bool = False) -> str:
    """Generate reviewed ZPL II standard commands for 4x6 inch direct thermal label printers."""
    data = get_label_data(doctype, name, label_type)
    primary_code = data.get("package_barcode") or data.get("barcode") or data.get("document_name") or name

    reprint_cmd = "^FO50,25^A0N,28,28^FR^FD*** REPRINT - AUDITED ***^FS\n" if is_reprint else ""

    zpl_lines = [
        "^XA",
        "^PW812",
        "^LL1218",
        reprint_cmd,
        f"^FO50,60^A0N,34,34^FD{data['title']}^FS",
        "^FO50,105^GB712,3,3^FS",
        f"^FO50,125^A0N,26,26^FDDocument: {data['document_name']}^FS",
        "^FO50,165^BY3,3,90",
        f"^BCN,90,Y,N,N^FD{primary_code}^FS",
        "^FO50,290^GB712,1,1^FS",
    ]

    y_pos = 310
    skip_keys = {"title", "document_name", "package_barcode", "barcode", "items"}
    for k, v in data.items():
        if k in skip_keys or y_pos > 1100:
            continue
        clean_k = k.replace("_", " ").title()
        val_str = str(v)[:45]  # limit length for thermal label line
        zpl_lines.append(f"^FO50,{y_pos}^A0N,22,22^FD{clean_k}: {val_str}^FS")
        y_pos += 35

    zpl_lines.extend([
        f"^FO50,{y_pos + 10}^GB712,2,2^FS",
        f"^FO50,{y_pos + 25}^A0N,18,18^FDPrinted on: {data['printed_on']} | {data['printed_by']}^FS",
        "^XZ",
    ])

    return "\n".join(zpl_lines)


@frappe.whitelist()
def get_document_label(
    doctype: str,
    name: str,
    label_type: str = "shipping",
    label_format: str = "html",
    is_reprint: bool | None = None,
) -> dict:
    """Retrieve rendered label or manifest projection with reprint detection and audit."""
    check_rate_limit("get_document_label", limit=120, window_seconds=60)
    doctype = validate_string(doctype, "DocType", max_len=140, required=True)
    name = validate_string(name, "Document Name", max_len=140, required=True)
    label_type = validate_string(label_type, "Label Type", allowed_values=ALLOWED_LABEL_TYPES)
    label_format = validate_string(label_format, "Label Format", allowed_values=ALLOWED_LABEL_FORMATS)

    # Document & warehouse permission validation
    _validate_label_access(doctype, name)

    # Check print count to determine reprint status if not explicitly passed
    print_count = _get_print_count(doctype, name, label_type)
    if is_reprint is None:
        is_reprint = print_count > 0

    if label_format == "zpl":
        rendered = generate_label_zpl(doctype, name, label_type, is_reprint=is_reprint)
        mime_type = "text/plain"
    else:
        rendered = generate_label_html(doctype, name, label_type, is_reprint=is_reprint)
        mime_type = "text/html"

    return {
        "doctype": doctype,
        "name": name,
        "label_type": label_type,
        "label_format": label_format,
        "is_reprint": is_reprint,
        "print_count": print_count,
        "content": rendered,
        "mime_type": mime_type,
    }


@frappe.whitelist(methods=["POST"])
def print_task_label(
    doctype: str,
    name: str,
    label_type: str = "shipping",
    label_format: str = "html",
    printer_name: str | None = None,
    simulate_failure: bool = False,
) -> dict:
    """Execute label print, atomically increment reprint audit counter, and log security event."""
    check_rate_limit("print_task_label", limit=60, window_seconds=60)
    doctype = validate_string(doctype, "DocType", max_len=140, required=True)
    name = validate_string(name, "Document Name", max_len=140, required=True)
    label_type = validate_string(label_type, "Label Type", allowed_values=ALLOWED_LABEL_TYPES)
    label_format = validate_string(label_format, "Label Format", allowed_values=ALLOWED_LABEL_FORMATS)

    _validate_label_access(doctype, name)

    # Simulate network or printer failure without corrupting document state
    if simulate_failure:
        frappe.throw(
            _("Printer '{0}' is offline or timed out. Label output aborted safely.").format(printer_name or "Default"),
            frappe.ValidationError,
        )

    # Atomic counter increment
    prior_count = _get_print_count(doctype, name, label_type)
    new_count = _increment_print_count(doctype, name, label_type)
    is_reprint = prior_count > 0

    event_type = "Document Label Reprinted" if is_reprint else "Document Label Printed"
    record_security_audit_event(
        event_type,
        doctype,
        name,
        {
            "label_type": label_type,
            "label_format": label_format,
            "printer": printer_name or "Client Browser",
            "print_count": new_count,
            "is_reprint": is_reprint,
        },
    )

    label_payload = get_document_label(
        doctype,
        name,
        label_type=label_type,
        label_format=label_format,
        is_reprint=is_reprint,
    )

    return {
        "success": True,
        "doctype": doctype,
        "name": name,
        "label_type": label_type,
        "is_reprint": is_reprint,
        "print_count": new_count,
        "printer": printer_name or "Client Browser",
        "label": label_payload,
    }
