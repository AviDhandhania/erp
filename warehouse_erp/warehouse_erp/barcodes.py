# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Unified Barcode Platform for Clothing ERP Suite.

Provides:
1. Distinct Identifier Namespaces & Symbologies (GS1 GTIN, Native Item Barcode,
   Internal Code 128 SKU, Serial No, Batch No, Location, Package, Pick List,
   Delivery Note, Return Quarantine, Quality Cycle / Report).
2. GS1 Modulo 10 and Code 128 Check-Digit Verification.
   Strict Policy: Never generate random EAN-13 numbers and claim they are globally valid.
3. Collision-Safe Server Allocation & Immutable Assignment.
4. One Typed Server-Side Scan Resolver (`resolve_scan`) with Contextual Validation.
5. Single and Bounded Bulk Barcode Generation with Rate Limiting.
6. Deterministic Barcode Previews.
"""

from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

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

# ---------------------------------------------------------------------------
# 1. Namespaces and Symbologies
# ---------------------------------------------------------------------------
NS_GS1_GTIN = "gs1_gtin"
NS_ITEM_BARCODE = "item_barcode"
NS_INTERNAL_SKU = "internal_sku"
NS_SERIAL_NO = "serial_no"
NS_BATCH_NO = "batch_no"
NS_LOCATION = "location"
NS_PACKAGE = "package"
NS_PICK_LIST = "pick_list"
NS_DELIVERY_NOTE = "delivery_note"
NS_RETURN_QUARANTINE = "return_quarantine"
NS_QUALITY_CYCLE = "quality_cycle"
NS_QUALITY_INSPECTION = "quality_inspection"

ALL_NAMESPACES = {
    NS_GS1_GTIN,
    NS_ITEM_BARCODE,
    NS_INTERNAL_SKU,
    NS_SERIAL_NO,
    NS_BATCH_NO,
    NS_LOCATION,
    NS_PACKAGE,
    NS_PICK_LIST,
    NS_DELIVERY_NOTE,
    NS_RETURN_QUARANTINE,
    NS_QUALITY_CYCLE,
    NS_QUALITY_INSPECTION,
}

BARCODE_ROLES = {ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"}


# ---------------------------------------------------------------------------
# 2. Check-Digit Routines (GS1 Modulo 10 & Code 128)
# ---------------------------------------------------------------------------
def compute_gs1_mod10_check_digit(digits: str) -> int:
    """Compute standard GS1 Modulo 10 check digit.
    
    Weights 3 and 1 alternate from right to left (last digit of data has weight 3).
    """
    clean_digits = str(digits or "").strip()
    if not clean_digits.isdigit():
        raise ValueError(f"GS1 Modulo 10 input must be purely numeric, got '{clean_digits}'")

    total = sum(
        int(d) * (3 if i % 2 == 0 else 1)
        for i, d in enumerate(reversed(clean_digits))
    )
    return (10 - (total % 10)) % 10


def validate_gs1_mod10_check_digit(barcode: str) -> bool:
    """Verify standard GS1 Modulo 10 check digit for EAN-13, EAN-8, UPC-A, GTIN-14."""
    clean = str(barcode or "").strip()
    if not clean.isdigit() or len(clean) < 8:
        return False
    data, check_digit = clean[:-1], int(clean[-1])
    try:
        expected = compute_gs1_mod10_check_digit(data)
        return expected == check_digit
    except ValueError:
        return False


def validate_ean13(barcode: str) -> bool:
    """Strictly validate EAN-13 format (13 digits + valid check digit)."""
    clean = str(barcode or "").strip()
    return len(clean) == 13 and validate_gs1_mod10_check_digit(clean)


def validate_upca(barcode: str) -> bool:
    """Strictly validate UPC-A format (12 digits + valid check digit)."""
    clean = str(barcode or "").strip()
    return len(clean) == 12 and validate_gs1_mod10_check_digit(clean)


def validate_ean8(barcode: str) -> bool:
    """Strictly validate EAN-8 format (8 digits + valid check digit)."""
    clean = str(barcode or "").strip()
    return len(clean) == 8 and validate_gs1_mod10_check_digit(clean)


def validate_code128_charset(text: str) -> bool:
    """Validate that text contains only printable ASCII characters (32 to 126)."""
    clean = str(text or "")
    if not clean or len(clean) > 140:
        return False
    return all(32 <= ord(c) <= 126 for c in clean)


# ---------------------------------------------------------------------------
# 3. Namespace Classification
# ---------------------------------------------------------------------------
def classify_barcode_namespace(raw_scan: str) -> dict[str, Any]:
    """Classify a scan text into one of eleven distinct namespaces."""
    scan = str(raw_scan or "").strip()[:140]
    if not scan:
        return {
            "raw": raw_scan,
            "normalized": "",
            "namespace": "unknown",
            "symbology": "unknown",
            "valid_check_digit": None,
        }

    # 1. Package Carton
    if re.match(r"^PKG-[A-Za-z0-9_-]+$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_PACKAGE,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 2. Internal SKU
    if re.match(r"^SKU-[A-Za-z0-9_-]+$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_INTERNAL_SKU,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 3. Warehouse Location
    if re.match(r"^(LOC|WH)-[A-Za-z0-9_\s-]+$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_LOCATION,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 4. Pick List
    if re.match(r"^(PL-\d{4}-\d+|PICK-[A-Za-z0-9_-]+)$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_PICK_LIST,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 5. Delivery Note
    if re.match(r"^(MAT-DN-\d{4}-\d+|DN-[A-Za-z0-9_-]+)$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_DELIVERY_NOTE,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 6. Return Quarantine
    if re.match(r"^(RQ-\d{4}-\d+|RET-[A-Za-z0-9_-]+)$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_RETURN_QUARANTINE,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 7. Quality Cycle
    if re.match(r"^PQC-\d{4}-\d+$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_QUALITY_CYCLE,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 8. Quality Inspection Report
    if re.match(r"^SQI-\d{4}-\d+$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_QUALITY_INSPECTION,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 9. Serial No explicit prefix
    if re.match(r"^SR-[A-Za-z0-9_-]+$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_SERIAL_NO,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 10. Batch No explicit prefix
    if re.match(r"^BATCH-[A-Za-z0-9_-]+$", scan, re.IGNORECASE):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_BATCH_NO,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    # 11. GS1 GTIN / EAN / UPC Numeric Barcodes
    if scan.isdigit() and len(scan) in (8, 12, 13, 14):
        is_valid = validate_gs1_mod10_check_digit(scan)
        symbology = "EAN-13" if len(scan) == 13 else ("UPC-A" if len(scan) == 12 else ("EAN-8" if len(scan) == 8 else "GTIN-14"))
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_GS1_GTIN,
            "symbology": symbology,
            "valid_check_digit": is_valid,
        }

    # 12. Database Fallback Lookups
    if frappe.db.exists("Serial No", scan):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_SERIAL_NO,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    if frappe.db.exists("Batch", scan):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_BATCH_NO,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    if frappe.db.exists("Item Barcode", {"barcode": scan}):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_ITEM_BARCODE,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    if frappe.db.exists("Item", scan):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_INTERNAL_SKU,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    if frappe.db.exists("Warehouse", scan):
        return {
            "raw": raw_scan,
            "normalized": scan,
            "namespace": NS_LOCATION,
            "symbology": "Code 128",
            "valid_check_digit": True,
        }

    return {
        "raw": raw_scan,
        "normalized": scan,
        "namespace": "unknown",
        "symbology": "Code 128" if validate_code128_charset(scan) else "unknown",
        "valid_check_digit": None,
    }


# ---------------------------------------------------------------------------
# 4. Collision-Safe Barcode Allocation
# ---------------------------------------------------------------------------
def generate_internal_sku_barcode(item_code: str, size: str | None = None) -> str:
    """Generate deterministic, collision-safe internal Code 128 barcode."""
    clean_item = re.sub(r"[^A-Za-z0-9_-]", "-", str(item_code or "").strip())
    clean_size = re.sub(r"[^A-Za-z0-9_-]", "", str(size or "").strip()).upper()

    base_sku = f"SKU-{clean_item}-{clean_size}" if clean_size else f"SKU-{clean_item}"
    candidate = base_sku

    # Check collision against tabItem Barcode for different item
    seq = 1
    while True:
        existing = frappe.db.sql(
            """
            SELECT parent FROM `tabItem Barcode`
            WHERE barcode = %s
            """,
            (candidate,),
            as_dict=True,
        )
        if not existing or existing[0].parent == item_code:
            break
        candidate = f"{base_sku}-{seq}"
        seq += 1

    return candidate


@frappe.whitelist(methods=["POST"])
def allocate_item_barcode(
    item_code: str,
    size: str | None = None,
    barcode: str | None = None,
    barcode_type: str = "Code 128",
) -> dict[str, Any]:
    """Allocate an immutable barcode to an ERPNext Item or variant.
    
    Validates check digits for GS1 types, ensures collision safety,
    and preserves existing barcodes without silent overwrites.
    """
    check_rate_limit("allocate_item_barcode", limit=60, window_seconds=60)
    require_role(BARCODE_ROLES)
    item_code = validate_string(item_code, "Item Code", max_len=140, required=True)

    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item '{0}' does not exist.").format(item_code), frappe.DoesNotExistError)

    # If barcode provided by user/manufacturer, validate format and uniqueness
    if barcode:
        barcode = validate_string(barcode, "Barcode", max_len=140, required=True)
        # Check digit enforcement for GS1 types
        if barcode_type in ("EAN", "EAN-13", "UPC-A", "EAN-8", "GTIN-14"):
            if not validate_gs1_mod10_check_digit(barcode):
                frappe.throw(
                    _("Invalid check digit for {0} barcode '{1}'.").format(barcode_type, barcode),
                    frappe.ValidationError,
                )
        elif not validate_code128_charset(barcode):
            frappe.throw(
                _("Barcode '{0}' contains invalid characters for Code 128.").format(barcode),
                frappe.ValidationError,
            )

        # Collision check across all items
        existing = frappe.db.sql(
            """
            SELECT parent FROM `tabItem Barcode`
            WHERE barcode = %s
            """,
            (barcode,),
            as_dict=True,
        )
        if existing and existing[0].parent != item_code:
            frappe.throw(
                _("Barcode '{0}' is already allocated to item '{1}'.").format(barcode, existing[0].parent),
                frappe.ValidationError,
            )
    else:
        barcode = generate_internal_sku_barcode(item_code, size)
        barcode_type = "Code 128"

    item_doc = frappe.get_doc("Item", item_code)
    # Check if already registered on this item
    for row in item_doc.get("barcodes") or []:
        if row.barcode == barcode:
            return {
                "success": True,
                "item_code": item_code,
                "barcode": barcode,
                "barcode_type": row.barcode_type or barcode_type,
                "is_existing": True,
            }

    # Add child row to native tabItem Barcode immutably
    item_doc.append("barcodes", {
        "barcode": barcode,
        "barcode_type": barcode_type,
    })
    item_doc.save(ignore_permissions=True)

    record_security_audit_event(
        "Item Barcode Allocated",
        "Item",
        item_code,
        {
            "barcode": barcode,
            "barcode_type": barcode_type,
            "size": size,
            "allocated_by": get_current_user(),
        },
    )

    return {
        "success": True,
        "item_code": item_code,
        "barcode": barcode,
        "barcode_type": barcode_type,
        "is_existing": False,
    }


@frappe.whitelist(methods=["POST"])
def bulk_allocate_barcodes(
    items: list[dict[str, Any]] | str,
    company: str | None = None,
) -> dict[str, Any]:
    """Allocate barcodes in bounded bulk batches (max 500 items per request)."""
    check_rate_limit("bulk_allocate_barcodes", limit=20, window_seconds=60)
    require_role(BARCODE_ROLES)

    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            frappe.throw(_("Invalid items payload; must be JSON array."), frappe.ValidationError)

    if not isinstance(items, list):
        frappe.throw(_("Items must be a list."), frappe.ValidationError)

    if len(items) > 500:
        frappe.throw(
            _("Bulk barcode allocation bounded to maximum 500 items per request; received {0}.").format(len(items)),
            frappe.ValidationError,
        )

    results = []
    for entry in items:
        code = entry.get("item_code")
        sz = entry.get("size")
        bcode = entry.get("barcode")
        btype = entry.get("barcode_type") or "Code 128"
        if not code:
            continue
        try:
            res = allocate_item_barcode(item_code=code, size=sz, barcode=bcode, barcode_type=btype)
            results.append(res)
        except Exception as e:
            results.append({
                "item_code": code,
                "success": False,
                "error": str(e),
            })

    return {
        "success": True,
        "total_requested": len(items),
        "total_processed": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# 5. Barcode SVG / Visual Preview
# ---------------------------------------------------------------------------
@frappe.whitelist()
def preview_barcode(barcode: str, barcode_type: str = "Code 128") -> dict[str, Any]:
    """Generate SVG preview and validation metadata for a barcode."""
    check_rate_limit("preview_barcode", limit=120, window_seconds=60)
    clean_barcode = str(barcode or "").strip()[:140]
    classification = classify_barcode_namespace(clean_barcode)

    svg_content = ""
    try:
        import barcode as pybarcode
        from barcode.writer import SVGWriter

        btype_lower = barcode_type.lower().replace("-", "").replace(" ", "")
        if btype_lower in ("code128", "code_128", "code 128", "c128"):
            bc_class = pybarcode.get_barcode_class("code128")
        elif btype_lower in ("ean13", "ean", "ean_13"):
            bc_class = pybarcode.get_barcode_class("ean13")
        elif btype_lower in ("upca", "upc"):
            bc_class = pybarcode.get_barcode_class("upca")
        elif btype_lower in ("ean8", "ean_8"):
            bc_class = pybarcode.get_barcode_class("ean8")
        else:
            bc_class = pybarcode.get_barcode_class("code128")

        writer = SVGWriter()
        buf = io.BytesIO()
        bc_obj = bc_class(clean_barcode, writer=writer)
        bc_obj.write(buf)
        svg_content = buf.getvalue().decode("utf-8")
    except Exception as e:
        svg_content = f"<svg><text y='20' fill='red'>Preview error: {frappe.utils.escape_html(str(e))}</text></svg>"

    return {
        "barcode": clean_barcode,
        "barcode_type": barcode_type,
        "namespace": classification["namespace"],
        "symbology": classification["symbology"],
        "valid_check_digit": classification["valid_check_digit"],
        "svg": svg_content,
    }


# ---------------------------------------------------------------------------
# 6. One Typed Server-Side Scan Resolver (`resolve_scan`)
# ---------------------------------------------------------------------------
@frappe.whitelist(methods=["POST"])
def resolve_scan(
    scan_text: str,
    operation_context: str | None = None,
    warehouse: str | None = None,
    document_type: str | None = None,
    document_name: str | None = None,
    expected_item: str | None = None,
    expected_batch: str | None = None,
    expected_serial: str | None = None,
) -> dict[str, Any]:
    """Single typed server-side scan resolver for web and mobile clients.
    
    Accepts normalized scan text, resolves namespace and target entity,
    and executes contextual validation against workflow rules and user permissions.
    """
    check_rate_limit("resolve_scan", limit=120, window_seconds=60)
    user = get_current_user()
    scan = validate_string(scan_text, "Scan Text", max_len=140, required=True).strip()

    classification = classify_barcode_namespace(scan)
    namespace = classification["namespace"]

    # Reject invalid check digits on GS1 barcodes before query
    if namespace == NS_GS1_GTIN and classification["valid_check_digit"] is False:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": namespace,
            "entity_type": "unknown",
            "error_code": "INVALID_CHECK_DIGIT",
            "message": _("Scanned barcode '{0}' has an invalid GS1 Modulo 10 check digit.").format(scan),
            "feedback": {
                "status": "error",
                "message": _("Invalid check digit"),
                "audio": "beep_error",
                "color": "red",
            },
        }

    # Warehouse scoping check
    if warehouse and not is_warehouse_admin(user):
        allowed = assigned_warehouses(user)
        if warehouse not in allowed:
            return {
                "success": False,
                "scan_text": scan,
                "namespace": namespace,
                "entity_type": "unknown",
                "error_code": "UNAUTHORIZED_WAREHOUSE",
                "message": _("You do not have permission for warehouse '{0}'.").format(warehouse),
                "feedback": {
                    "status": "error",
                    "message": _("Warehouse permission denied"),
                    "audio": "beep_error",
                    "color": "red",
                },
            }

    # Entity Resolution:
    # ------------------
    # A. Serial No
    if namespace == NS_SERIAL_NO or frappe.db.exists("Serial No", scan):
        serial_doc = frappe.db.get_value(
            "Serial No",
            scan,
            ["name", "item_code", "batch_no", "warehouse", "status", "company"],
            as_dict=True,
        )
        if serial_doc:
            return _validate_serial_scan(
                serial_doc, scan, operation_context, warehouse, document_type,
                document_name, expected_item, expected_batch, expected_serial
            )

    # B. Batch No
    if namespace == NS_BATCH_NO or frappe.db.exists("Batch", scan):
        batch_doc = frappe.db.get_value(
            "Batch",
            scan,
            ["name", "item", "expiry_date", "batch_qty", "disabled"],
            as_dict=True,
        )
        if batch_doc:
            return _validate_batch_scan(
                batch_doc, scan, operation_context, warehouse, document_type,
                document_name, expected_item, expected_batch
            )

    # C. Item / SKU / Barcode
    item_code = None
    barcode_val = scan
    if namespace in (NS_INTERNAL_SKU, NS_ITEM_BARCODE, NS_GS1_GTIN) or True:
        # Check Item Barcode child table
        bc_row = frappe.db.sql(
            """
            SELECT parent as item_code, barcode, barcode_type
            FROM `tabItem Barcode`
            WHERE barcode = %s
            LIMIT 1
            """,
            (scan,),
            as_dict=True,
        )
        if bc_row:
            item_code = bc_row[0].item_code
            barcode_val = bc_row[0].barcode
        elif frappe.db.exists("Item", scan):
            item_code = scan
        elif scan.startswith("SKU-"):
            clean_code = scan[4:]
            if frappe.db.exists("Item", clean_code):
                item_code = clean_code

    if item_code and frappe.db.exists("Item", item_code):
        item_data = frappe.db.get_value(
            "Item",
            item_code,
            ["name", "item_name", "item_group", "stock_uom", "has_batch_no", "has_serial_no", "is_stock_item", "disabled"],
            as_dict=True,
        )
        if item_data:
            return _validate_item_scan(
                item_data, barcode_val, scan, namespace, operation_context,
                warehouse, document_type, document_name, expected_item
            )

    # D. Package Carton
    if namespace == NS_PACKAGE or frappe.db.exists("Packing Slip", {"custom_package_barcode": scan}):
        ps_doc = frappe.db.get_value(
            "Packing Slip",
            {"custom_package_barcode": scan},
            ["name", "delivery_note", "from_case_no", "to_case_no", "gross_weight_pkg", "net_weight_pkg"],
            as_dict=True,
        )
        if ps_doc:
            return {
                "success": True,
                "scan_text": scan,
                "namespace": NS_PACKAGE,
                "entity_type": "package",
                "entity_name": ps_doc.name,
                "details": {
                    "packing_slip": ps_doc.name,
                    "delivery_note": ps_doc.delivery_note,
                    "cases": f"{ps_doc.from_case_no} to {ps_doc.to_case_no}",
                    "gross_weight": flt(ps_doc.gross_weight_pkg),
                    "net_weight": flt(ps_doc.net_weight_pkg),
                },
                "context_valid": True,
                "error_code": None,
                "feedback": {
                    "status": "valid",
                    "message": _("Package verified: {0}").format(ps_doc.name),
                    "audio": "beep_success",
                    "color": "green",
                },
            }

    # E. Warehouse Location
    if namespace == NS_LOCATION or frappe.db.exists("Warehouse", scan):
        wh_name = scan
        if not frappe.db.exists("Warehouse", wh_name):
            if scan.upper().startswith("LOC-"):
                wh_name = scan[4:].strip()
            elif scan.upper().startswith("WH-"):
                wh_name = scan[3:].strip()

        if not frappe.db.exists("Warehouse", wh_name):
            wh_match = frappe.db.get_value("Warehouse", {"warehouse_name": wh_name}, "name")
            if wh_match:
                wh_name = wh_match

        if frappe.db.exists("Warehouse", wh_name):
            wh_doc = frappe.get_doc("Warehouse", wh_name)
            if not is_warehouse_admin(user):
                allowed = assigned_warehouses(user)
                if wh_doc.name not in allowed:
                    return {
                        "success": False,
                        "scan_text": scan,
                        "namespace": NS_LOCATION,
                        "entity_type": "location",
                        "error_code": "UNAUTHORIZED_WAREHOUSE",
                        "message": _("You do not have access to location '{0}'.").format(wh_doc.name),
                        "feedback": {
                            "status": "error",
                            "message": _("Unauthorized location"),
                            "audio": "beep_error",
                            "color": "red",
                        },
                    }
            return {
                "success": True,
                "scan_text": scan,
                "namespace": NS_LOCATION,
                "entity_type": "location",
                "entity_name": wh_doc.name,
                "details": {
                    "warehouse_name": wh_doc.warehouse_name,
                    "company": wh_doc.company,
                    "parent_warehouse": wh_doc.parent_warehouse,
                    "is_group": wh_doc.is_group,
                },
                "context_valid": True,
                "error_code": None,
                "feedback": {
                    "status": "valid",
                    "message": _("Location verified: {0}").format(wh_doc.name),
                    "audio": "beep_success",
                    "color": "green",
                },
            }

    # F. Pick List Document
    if namespace == NS_PICK_LIST or frappe.db.exists("Pick List", scan):
        pl_name = scan
        if not frappe.db.exists("Pick List", pl_name):
            if scan.upper().startswith("PICK-"):
                pl_name = scan[5:].strip()
            elif scan.upper().startswith("PL-"):
                pl_name = scan[3:].strip()
        if frappe.db.exists("Pick List", pl_name):
            doc = frappe.get_doc("Pick List", pl_name)
            doc.check_permission("read")
            return {
                "success": True,
                "scan_text": scan,
                "namespace": NS_PICK_LIST,
                "entity_type": "document",
                "entity_name": doc.name,
                "details": {
                    "doctype": "Pick List",
                    "status": doc.status,
                    "company": doc.company,
                    "total_items": len(doc.get("locations") or []),
                },
                "context_valid": True,
                "error_code": None,
                "feedback": {
                    "status": "valid",
                    "message": _("Pick List verified: {0}").format(doc.name),
                    "audio": "beep_success",
                    "color": "green",
                },
            }

    # G. Delivery Note Document
    if namespace == NS_DELIVERY_NOTE or frappe.db.exists("Delivery Note", scan):
        dn_name = scan
        if frappe.db.exists("Delivery Note", dn_name):
            doc = frappe.get_doc("Delivery Note", dn_name)
            doc.check_permission("read")
            return {
                "success": True,
                "scan_text": scan,
                "namespace": NS_DELIVERY_NOTE,
                "entity_type": "document",
                "entity_name": doc.name,
                "details": {
                    "doctype": "Delivery Note",
                    "customer": doc.customer,
                    "status": doc.status,
                    "company": doc.company,
                    "total_items": len(doc.get("items") or []),
                },
                "context_valid": True,
                "error_code": None,
                "feedback": {
                    "status": "valid",
                    "message": _("Delivery Note verified: {0}").format(doc.name),
                    "audio": "beep_success",
                    "color": "green",
                },
            }

    # H. Return Quarantine Document
    if namespace == NS_RETURN_QUARANTINE or frappe.db.exists("Return Quarantine", scan):
        rq_name = scan
        if not frappe.db.exists("Return Quarantine", rq_name):
            if scan.upper().startswith("RET-"):
                rq_name = scan[4:].strip()
            elif scan.upper().startswith("RQ-"):
                rq_name = scan[3:].strip()
        if frappe.db.exists("Return Quarantine", rq_name):
            doc = frappe.get_doc("Return Quarantine", rq_name)
            doc.check_permission("read")
            return {
                "success": True,
                "scan_text": scan,
                "namespace": NS_RETURN_QUARANTINE,
                "entity_type": "document",
                "entity_name": doc.name,
                "details": {
                    "doctype": "Return Quarantine",
                    "item_code": doc.item_code,
                    "quantity": flt(doc.quantity),
                    "inspection_status": doc.inspection_status,
                    "quarantine_warehouse": doc.quarantine_warehouse,
                },
                "context_valid": True,
                "error_code": None,
                "feedback": {
                    "status": "valid",
                    "message": _("Quarantine tag verified: {0}").format(doc.name),
                    "audio": "beep_success",
                    "color": "green",
                },
            }

    # H. Quality Cycle / Inspection
    if namespace in (NS_QUALITY_CYCLE, NS_QUALITY_INSPECTION) or frappe.db.exists("Production Quality Cycle", scan) or frappe.db.exists("Supplier Quality Inspection", scan):
        dt = "Production Quality Cycle" if (scan.startswith("PQC-") or frappe.db.exists("Production Quality Cycle", scan)) else "Supplier Quality Inspection"
        if frappe.db.exists(dt, scan):
            doc = frappe.get_doc(dt, scan)
            doc.check_permission("read")
            return {
                "success": True,
                "scan_text": scan,
                "namespace": NS_QUALITY_CYCLE if dt == "Production Quality Cycle" else NS_QUALITY_INSPECTION,
                "entity_type": "document",
                "entity_name": doc.name,
                "details": {
                    "doctype": dt,
                    "supplier": doc.supplier,
                    "item_code": doc.item_code,
                    "status": doc.status,
                },
                "context_valid": True,
                "error_code": None,
                "feedback": {
                    "status": "valid",
                    "message": _("Quality record verified: {0}").format(doc.name),
                    "audio": "beep_success",
                    "color": "green",
                },
            }

    # If unmatched
    return {
        "success": False,
        "scan_text": scan,
        "namespace": namespace,
        "entity_type": "unknown",
        "error_code": "UNRESOLVED_BARCODE",
        "message": _("Barcode '{0}' could not be resolved to any item, serial, batch, or document.").format(scan),
        "feedback": {
            "status": "error",
            "message": _("Unresolved barcode"),
            "audio": "beep_error",
            "color": "red",
        },
    }


# ---------------------------------------------------------------------------
# Internal Contextual Validation Helpers
# ---------------------------------------------------------------------------
def _validate_item_scan(
    item_data: dict,
    barcode_val: str,
    scan: str,
    namespace: str,
    operation_context: str | None,
    warehouse: str | None,
    document_type: str | None,
    document_name: str | None,
    expected_item: str | None,
) -> dict[str, Any]:
    item_code = item_data.name

    if item_data.disabled:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": namespace,
            "entity_type": "item",
            "entity_name": item_code,
            "error_code": "DISABLED_ITEM",
            "message": _("Item '{0}' is disabled.").format(item_code),
            "feedback": {"status": "error", "message": _("Item disabled"), "audio": "beep_error", "color": "red"},
        }

    # Wrong Item check
    if expected_item and expected_item != item_code:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": namespace,
            "entity_type": "item",
            "entity_name": item_code,
            "error_code": "WRONG_ITEM",
            "message": _("Scanned item '{0}' does not match expected item '{1}'.").format(item_code, expected_item),
            "feedback": {"status": "error", "message": _("Wrong item"), "audio": "beep_error", "color": "red"},
        }

    # Picking Context
    if operation_context == "picking" and document_type == "Pick List" and document_name:
        pl_rows = frappe.db.sql(
            """
            SELECT name, item_code, qty, picked_qty, warehouse
            FROM `tabPick List Item`
            WHERE parent = %s AND item_code = %s
            """,
            (document_name, item_code),
            as_dict=True,
        )
        if not pl_rows:
            return {
                "success": False,
                "scan_text": scan,
                "namespace": namespace,
                "entity_type": "item",
                "entity_name": item_code,
                "error_code": "WRONG_ITEM",
                "message": _("Item '{0}' is not in Pick List '{1}'.").format(item_code, document_name),
                "feedback": {"status": "error", "message": _("Not in Pick List"), "audio": "beep_error", "color": "red"},
            }

        total_req = sum(flt(r.qty) for r in pl_rows)
        total_picked = sum(flt(r.picked_qty) for r in pl_rows)
        if total_picked >= total_req:
            return {
                "success": False,
                "scan_text": scan,
                "namespace": namespace,
                "entity_type": "item",
                "entity_name": item_code,
                "error_code": "OVER_PICK",
                "message": _("Item '{0}' has already been fully picked ({1}/{2}).").format(item_code, total_picked, total_req),
                "feedback": {"status": "warning", "message": _("Already picked"), "audio": "beep_warning", "color": "amber"},
            }

    # Returns Context
    if operation_context == "returns" and document_type == "Delivery Note" and document_name:
        dn_rows = frappe.db.sql(
            """
            SELECT name, item_code, qty, returned_qty
            FROM `tabDelivery Note Item`
            WHERE parent = %s AND item_code = %s
            """,
            (document_name, item_code),
            as_dict=True,
        )
        if not dn_rows:
            return {
                "success": False,
                "scan_text": scan,
                "namespace": namespace,
                "entity_type": "item",
                "entity_name": item_code,
                "error_code": "WRONG_ITEM",
                "message": _("Item '{0}' was not delivered under Delivery Note '{1}'.").format(item_code, document_name),
                "feedback": {"status": "error", "message": _("Item not in delivery"), "audio": "beep_error", "color": "red"},
            }

        delivered_qty = sum(flt(r.qty) for r in dn_rows)
        returned_qty = sum(flt(r.returned_qty) for r in dn_rows)
        if returned_qty >= delivered_qty:
            return {
                "success": False,
                "scan_text": scan,
                "namespace": namespace,
                "entity_type": "item",
                "entity_name": item_code,
                "error_code": "OVER_RETURN",
                "message": _("All delivered units for item '{0}' have already been returned ({1}/{2}).").format(item_code, returned_qty, delivered_qty),
                "feedback": {"status": "error", "message": _("Over return"), "audio": "beep_error", "color": "red"},
            }

    return {
        "success": True,
        "scan_text": scan,
        "namespace": namespace,
        "entity_type": "item",
        "entity_name": item_code,
        "details": {
            "item_code": item_code,
            "item_name": item_data.item_name,
            "stock_uom": item_data.stock_uom,
            "has_batch_no": item_data.has_batch_no,
            "has_serial_no": item_data.has_serial_no,
            "barcode": barcode_val,
        },
        "context_valid": True,
        "error_code": None,
        "feedback": {
            "status": "valid",
            "message": _("Item verified: {0} ({1})").format(item_data.item_name, item_code),
            "audio": "beep_success",
            "color": "green",
        },
    }


def _validate_serial_scan(
    serial_doc: dict,
    scan: str,
    operation_context: str | None,
    warehouse: str | None,
    document_type: str | None,
    document_name: str | None,
    expected_item: str | None,
    expected_batch: str | None,
    expected_serial: str | None,
) -> dict[str, Any]:
    serial_no = serial_doc.name
    item_code = serial_doc.item_code

    if expected_serial and expected_serial != serial_no:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": NS_SERIAL_NO,
            "entity_type": "serial",
            "entity_name": serial_no,
            "error_code": "WRONG_SERIAL",
            "message": _("Scanned serial '{0}' does not match expected serial '{1}'.").format(serial_no, expected_serial),
            "feedback": {"status": "error", "message": _("Wrong serial"), "audio": "beep_error", "color": "red"},
        }

    if expected_item and expected_item != item_code:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": NS_SERIAL_NO,
            "entity_type": "serial",
            "entity_name": serial_no,
            "error_code": "WRONG_ITEM",
            "message": _("Serial '{0}' belongs to item '{1}', not expected item '{2}'.").format(serial_no, item_code, expected_item),
            "feedback": {"status": "error", "message": _("Wrong item for serial"), "audio": "beep_error", "color": "red"},
        }

    # Returns Context: verify serial was delivered on the original delivery note
    if operation_context == "returns" and document_type == "Delivery Note" and document_name:
        is_delivered_on_dn = frappe.db.sql(
            """
            SELECT name FROM `tabDelivery Note Item`
            WHERE parent = %s AND (serial_no LIKE %s OR serial_and_batch_bundle IN (
                SELECT parent FROM `tabSerial and Batch Entry` WHERE serial_no = %s
            ))
            LIMIT 1
            """,
            (document_name, f"%{serial_no}%", serial_no),
        )
        if not is_delivered_on_dn:
            return {
                "success": False,
                "scan_text": scan,
                "namespace": NS_SERIAL_NO,
                "entity_type": "serial",
                "entity_name": serial_no,
                "error_code": "WRONG_SERIAL",
                "message": _("Serial '{0}' was not delivered under Delivery Note '{1}'.").format(serial_no, document_name),
                "feedback": {"status": "error", "message": _("Serial not in delivery note"), "audio": "beep_error", "color": "red"},
            }

    return {
        "success": True,
        "scan_text": scan,
        "namespace": NS_SERIAL_NO,
        "entity_type": "serial",
        "entity_name": serial_no,
        "details": {
            "serial_no": serial_no,
            "item_code": item_code,
            "batch_no": serial_doc.batch_no,
            "warehouse": serial_doc.warehouse,
            "status": serial_doc.status,
            "company": serial_doc.company,
        },
        "context_valid": True,
        "error_code": None,
        "feedback": {
            "status": "valid",
            "message": _("Serial verified: {0} ({1})").format(serial_no, item_code),
            "audio": "beep_success",
            "color": "green",
        },
    }


def _validate_batch_scan(
    batch_doc: dict,
    scan: str,
    operation_context: str | None,
    warehouse: str | None,
    document_type: str | None,
    document_name: str | None,
    expected_item: str | None,
    expected_batch: str | None,
) -> dict[str, Any]:
    batch_no = batch_doc.name
    item_code = batch_doc.item

    if batch_doc.disabled:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": NS_BATCH_NO,
            "entity_type": "batch",
            "entity_name": batch_no,
            "error_code": "DISABLED_BATCH",
            "message": _("Batch '{0}' is disabled.").format(batch_no),
            "feedback": {"status": "error", "message": _("Batch disabled"), "audio": "beep_error", "color": "red"},
        }

    # Expiry Check
    if batch_doc.expiry_date and getdate(batch_doc.expiry_date) < getdate(nowdate()):
        return {
            "success": False,
            "scan_text": scan,
            "namespace": NS_BATCH_NO,
            "entity_type": "batch",
            "entity_name": batch_no,
            "error_code": "EXPIRED_BATCH",
            "message": _("Batch '{0}' expired on {1}.").format(batch_no, batch_doc.expiry_date),
            "feedback": {"status": "error", "message": _("Expired batch"), "audio": "beep_error", "color": "red"},
        }

    if expected_batch and expected_batch != batch_no:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": NS_BATCH_NO,
            "entity_type": "batch",
            "entity_name": batch_no,
            "error_code": "WRONG_BATCH",
            "message": _("Scanned batch '{0}' does not match expected batch '{1}'.").format(batch_no, expected_batch),
            "feedback": {"status": "error", "message": _("Wrong batch"), "audio": "beep_error", "color": "red"},
        }

    if expected_item and expected_item != item_code:
        return {
            "success": False,
            "scan_text": scan,
            "namespace": NS_BATCH_NO,
            "entity_type": "batch",
            "entity_name": batch_no,
            "error_code": "WRONG_ITEM",
            "message": _("Batch '{0}' belongs to item '{1}', not expected item '{2}'.").format(batch_no, item_code, expected_item),
            "feedback": {"status": "error", "message": _("Wrong item for batch"), "audio": "beep_error", "color": "red"},
        }

    return {
        "success": True,
        "scan_text": scan,
        "namespace": NS_BATCH_NO,
        "entity_type": "batch",
        "entity_name": batch_no,
        "details": {
            "batch_no": batch_no,
            "item_code": item_code,
            "expiry_date": str(batch_doc.expiry_date) if batch_doc.expiry_date else None,
            "batch_qty": flt(batch_doc.batch_qty),
        },
        "context_valid": True,
        "error_code": None,
        "feedback": {
            "status": "valid",
            "message": _("Batch verified: {0} ({1})").format(batch_no, item_code),
            "audio": "beep_success",
            "color": "green",
        },
    }
