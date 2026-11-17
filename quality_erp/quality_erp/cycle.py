# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Production Quality Cycle business logic, native links, and migration services.

Enforces:
- Unique business key per (Company, Supplier, PO/Season, Item/Style, Production Lot).
- Reviewed native links: Supplier, Purchase Order, Item/Style, Production Lot, Season,
  Purchase Receipt, native ERPNext Quality Inspection.
- Strict non-duplication of purchasing, payable, stock or Quality Inspection ledgers.
- Multi-company and supplier isolation on read and write operations.
- Safe, idempotent, rollbackable migration from existing Supplier Quality Inspection records.
"""

from __future__ import annotations

from typing import Any
import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from quality_erp.api_security import (
    check_rate_limit,
    record_security_audit_event,
    validate_string,
)
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)
from quality_erp.security import (
    get_current_user,
    is_quality_admin,
    is_quality_inspector,
    require_role,
)

CYCLE_ROLES = {ROLE_QUALITY_INSPECTOR, ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"}


def generate_cycle_key(
    company: str,
    supplier: str,
    item_code: str,
    purchase_order: str | None = None,
    production_lot: str | None = None,
    season: str | None = None,
) -> str:
    """Compute deterministic, unique business key for a Production Quality Cycle."""
    c = (company or "").strip()
    s = (supplier or "").strip()
    i = (item_code or "").strip()
    po_or_season = (purchase_order or "").strip() or (season or "").strip() or "DEV"
    lot = (production_lot or "").strip() or "01"

    if not c or not s or not i:
        frappe.throw(
            _("Company, Supplier, and Style/Item Code are required to generate the cycle business key."),
            frappe.ValidationError,
        )

    return f"{c}::{s}::{po_or_season}::{i}::{lot}"


def assert_cycle_access(doc_or_name: str | frappe.Document, ptype: str = "read", user: str | None = None) -> frappe.Document:
    """Assert server-side user role and company/supplier isolation for a Production Quality Cycle."""
    require_role(CYCLE_ROLES, user=user)
    user = get_current_user(user)

    if isinstance(doc_or_name, str):
        if not frappe.db.exists("Production Quality Cycle", doc_or_name):
            frappe.throw(_("Production Quality Cycle {0} does not exist.").format(doc_or_name), frappe.DoesNotExistError)
        doc = frappe.get_doc("Production Quality Cycle", doc_or_name)
    else:
        doc = doc_or_name

    if is_quality_admin(user):
        return doc

    # Company isolation
    allowed_companies = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Company"},
        pluck="for_value",
    )
    if allowed_companies and doc.company not in allowed_companies:
        frappe.throw(
            _("Access denied: You do not have permission for company {0}.").format(doc.company),
            frappe.PermissionError,
        )

    # Supplier isolation
    allowed_suppliers = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Supplier"},
        pluck="for_value",
    )
    if allowed_suppliers and doc.supplier not in allowed_suppliers:
        frappe.throw(
            _("Access denied: You do not have permission for supplier {0}.").format(doc.supplier),
            frappe.PermissionError,
        )

    doc.check_permission(ptype)
    return doc


@frappe.whitelist(methods=["POST"])
def get_or_create_cycle(
    company: str,
    supplier: str,
    item_code: str,
    purchase_order: str | None = None,
    production_lot: str | None = "01",
    season: str | None = None,
    items: list[dict] | None = None,
    notes: str | None = None,
) -> dict:
    """Idempotently retrieve existing cycle or create new Production Quality Cycle under unique key."""
    check_rate_limit("get_or_create_cycle", limit=60, window_seconds=60)
    require_role(CYCLE_ROLES)

    company = validate_string(company, "Company", max_len=140, required=True)
    supplier = validate_string(supplier, "Supplier", max_len=140, required=True)
    item_code = validate_string(item_code, "Style / Item Code", max_len=140, required=True)
    purchase_order = validate_string(purchase_order, "Purchase Order", max_len=140) if purchase_order else None
    production_lot = validate_string(production_lot, "Production Lot", max_len=140) if production_lot else "01"
    season = validate_string(season, "Season", max_len=140) if season else None

    # Validate master records exist
    if not frappe.db.exists("Company", company):
        frappe.throw(_("Company {0} does not exist.").format(company), frappe.DoesNotExistError)
    if not frappe.db.exists("Supplier", supplier):
        frappe.throw(_("Supplier {0} does not exist.").format(supplier), frappe.DoesNotExistError)
    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} does not exist.").format(item_code), frappe.DoesNotExistError)
    if purchase_order and not frappe.db.exists("Purchase Order", purchase_order):
        frappe.throw(_("Purchase Order {0} does not exist.").format(purchase_order), frappe.DoesNotExistError)

    cycle_key = generate_cycle_key(company, supplier, item_code, purchase_order, production_lot, season)

    existing_name = frappe.db.get_value("Production Quality Cycle", {"cycle_key": cycle_key}, "name")
    if existing_name:
        doc = assert_cycle_access(existing_name, ptype="read")
        return {
            "cycle_name": doc.name,
            "cycle_key": doc.cycle_key,
            "status": doc.status,
            "current_stage": doc.current_stage,
            "is_new": False,
        }

    # Verify user has creation rights for target company/supplier
    user = get_current_user()
    if not is_quality_admin(user):
        allowed_companies = frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": "Company"},
            pluck="for_value",
        )
        if allowed_companies and company not in allowed_companies:
            frappe.throw(_("You do not have permission to create cycles for company {0}.").format(company), frappe.PermissionError)

        allowed_suppliers = frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": "Supplier"},
            pluck="for_value",
        )
        if allowed_suppliers and supplier not in allowed_suppliers:
            frappe.throw(_("You do not have permission to create cycles for supplier {0}.").format(supplier), frappe.PermissionError)

    new_doc = frappe.get_doc({
        "doctype": "Production Quality Cycle",
        "company": company,
        "supplier": supplier,
        "item_code": item_code,
        "purchase_order": purchase_order,
        "production_lot": production_lot,
        "season": season,
        "cycle_key": cycle_key,
        "status": "Draft",
        "current_stage": "1. First Submission",
        "notes": notes,
    })

    if items and isinstance(items, (list, tuple)):
        for itm in items:
            if isinstance(itm, dict) and itm.get("item_code"):
                new_doc.append("items", {
                    "item_code": itm["item_code"],
                    "colourway": itm.get("colourway"),
                    "size": itm.get("size"),
                    "planned_qty": flt(itm.get("planned_qty")),
                    "sample_size": cint(itm.get("sample_size")),
                    "notes": itm.get("notes"),
                })

    new_doc.flags.ignore_links = True
    new_doc.insert()

    record_security_audit_event(
        "Production Quality Cycle Created",
        "Production Quality Cycle",
        new_doc.name,
        {
            "cycle_key": cycle_key,
            "company": company,
            "supplier": supplier,
            "item_code": item_code,
            "purchase_order": purchase_order,
            "production_lot": production_lot,
        },
    )

    return {
        "cycle_name": new_doc.name,
        "cycle_key": new_doc.cycle_key,
        "status": new_doc.status,
        "current_stage": new_doc.current_stage,
        "is_new": True,
    }


@frappe.whitelist(methods=["POST"])
def link_native_purchase_receipt(cycle_name: str, purchase_receipt: str) -> dict:
    """Link native ERPNext Purchase Receipt without duplicating stock or payable ledgers."""
    check_rate_limit("link_native_purchase_receipt", limit=30, window_seconds=60)
    cycle = assert_cycle_access(cycle_name, ptype="write")

    purchase_receipt = validate_string(purchase_receipt, "Purchase Receipt", max_len=140, required=True)
    if not frappe.db.exists("Purchase Receipt", purchase_receipt):
        frappe.throw(_("Purchase Receipt {0} does not exist.").format(purchase_receipt), frappe.DoesNotExistError)

    pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
    if pr.company != cycle.company:
        frappe.throw(
            _("Purchase Receipt company '{0}' does not match cycle company '{1}'.").format(pr.company, cycle.company),
            frappe.ValidationError,
        )
    if pr.supplier != cycle.supplier:
        frappe.throw(
            _("Purchase Receipt supplier '{0}' does not match cycle supplier '{1}'.").format(pr.supplier, cycle.supplier),
            frappe.ValidationError,
        )

    cycle.purchase_receipt = purchase_receipt
    cycle.flags.ignore_permissions = True
    cycle.save()

    record_security_audit_event(
        "Cycle Purchase Receipt Linked",
        "Production Quality Cycle",
        cycle.name,
        {"purchase_receipt": purchase_receipt},
    )

    return {
        "success": True,
        "cycle_name": cycle.name,
        "purchase_receipt": purchase_receipt,
    }


@frappe.whitelist(methods=["POST"])
def link_native_quality_inspection(cycle_name: str, quality_inspection: str) -> dict:
    """Link native ERPNext Quality Inspection without duplicating quality inspection ledgers."""
    check_rate_limit("link_native_quality_inspection", limit=30, window_seconds=60)
    cycle = assert_cycle_access(cycle_name, ptype="write")

    quality_inspection = validate_string(quality_inspection, "Quality Inspection", max_len=140, required=True)
    if not frappe.db.exists("Quality Inspection", quality_inspection):
        frappe.throw(_("Quality Inspection {0} does not exist.").format(quality_inspection), frappe.DoesNotExistError)

    cycle.quality_inspection = quality_inspection
    cycle.flags.ignore_permissions = True
    cycle.save()

    record_security_audit_event(
        "Cycle Quality Inspection Linked",
        "Production Quality Cycle",
        cycle.name,
        {"quality_inspection": quality_inspection},
    )

    return {
        "success": True,
        "cycle_name": cycle.name,
        "quality_inspection": quality_inspection,
    }


@frappe.whitelist(methods=["POST"])
def migrate_supplier_inspections_to_cycles(dry_run: bool = False, simulate_error: bool = False) -> dict:
    """Safely and idempotently migrate existing Supplier Quality Inspection records to Production Quality Cycles.

    Features:
    - Atomic execution under a savepoint; rolls back completely on error or dry-run.
    - Idempotent (migration-twice safe): records already linked are verified and never duplicated.
    - Auto-resolves company from Purchase Order or defaults.
    - Populates production_quality_cycle foreign key on tabSupplier Quality Inspection.
    - Updates cycle stage and progress statistics.
    """
    check_rate_limit("migrate_supplier_inspections_to_cycles", limit=10, window_seconds=60)
    require_role({ROLE_BUSINESS_ADMIN, "System Manager"})

    # Check if table tabProduction Quality Cycle exists in DB
    if not frappe.db.table_exists("Production Quality Cycle"):
        frappe.throw(_("Table tabProduction Quality Cycle does not exist. Please run migration first."), frappe.ValidationError)

    savepoint_name = "pqc_migration_sp"
    frappe.db.savepoint(savepoint_name)

    try:
        # Fetch all SQIs that need migration or verification
        sqis = frappe.db.sql(
            """
            SELECT name, supplier, item_code, purchase_order, stage, status,
                   inspection_date, company, production_lot, season, production_quality_cycle
            FROM `tabSupplier Quality Inspection`
            ORDER BY creation ASC
            """,
            as_dict=True,
        )

        if not sqis:
            return {
                "success": True,
                "total_inspections": 0,
                "cycles_created": 0,
                "inspections_linked": 0,
                "status": "No Inspections Found",
            }

        cycles_created = 0
        inspections_linked = 0
        cycle_cache: dict[str, str] = {}

        # Default company fallback
        default_company = frappe.defaults.get_user_default("Company") or "Default Company"

        for row in sqis:
            # Resolve company
            company = row.get("company")
            if not company and row.get("purchase_order"):
                company = frappe.db.get_value("Purchase Order", row["purchase_order"], "company")
            if not company:
                company = default_company

            supplier = row.get("supplier")
            item_code = row.get("item_code")
            po = row.get("purchase_order")
            lot = row.get("production_lot") or "01"
            season = row.get("season")

            if not supplier or not item_code:
                continue

            cycle_key = generate_cycle_key(company, supplier, item_code, po, lot, season)

            # Check if cycle already cached or exists
            cycle_name = cycle_cache.get(cycle_key)
            if not cycle_name:
                cycle_name = frappe.db.get_value("Production Quality Cycle", {"cycle_key": cycle_key}, "name")

            if not cycle_name:
                # Create cycle
                cycle_doc = frappe.get_doc({
                    "doctype": "Production Quality Cycle",
                    "company": company,
                    "supplier": supplier,
                    "item_code": item_code,
                    "purchase_order": po,
                    "production_lot": lot,
                    "season": season,
                    "cycle_key": cycle_key,
                    "status": "In Progress" if row.get("status") == "Approved" else "Draft",
                    "current_stage": row.get("stage") or "1. First Submission",
                })
                cycle_doc.flags.ignore_permissions = True
                cycle_doc.insert()
                cycle_name = cycle_doc.name
                cycle_cache[cycle_key] = cycle_name
                cycles_created += 1
            else:
                cycle_cache[cycle_key] = cycle_name

            # If SQI is not yet linked or company missing, link it
            if row.get("production_quality_cycle") != cycle_name or row.get("company") != company:
                frappe.db.set_value(
                    "Supplier Quality Inspection",
                    row["name"],
                    {
                        "production_quality_cycle": cycle_name,
                        "company": company,
                        "production_lot": lot,
                    },
                    update_modified=False,
                )
                inspections_linked += 1

        # Simulate error if requested for rollback testing
        if simulate_error:
            raise RuntimeError("Simulated migration failure for atomic rollback drill")

        # Sync stage progress for all touched cycles
        for ckey, cname in cycle_cache.items():
            cdoc = frappe.get_doc("Production Quality Cycle", cname)
            cdoc.flags.ignore_permissions = True
            cdoc.update_stage_progress()
            cdoc.save()

        if dry_run:
            frappe.db.rollback(save_point=savepoint_name)
            return {
                "success": True,
                "dry_run": True,
                "total_inspections": len(sqis),
                "cycles_created": cycles_created,
                "inspections_linked": inspections_linked,
                "status": "Dry Run Succeeded (Rolled Back)",
            }

        record_security_audit_event(
            "Production Quality Cycles Migrated",
            "Production Quality Cycle",
            "MIGRATION-BATCH",
            {
                "total_inspections": len(sqis),
                "cycles_created": cycles_created,
                "inspections_linked": inspections_linked,
            },
        )

        return {
            "success": True,
            "dry_run": False,
            "total_inspections": len(sqis),
            "cycles_created": cycles_created,
            "inspections_linked": inspections_linked,
            "status": "Migration Completed",
        }

    except Exception:
        frappe.db.rollback(save_point=savepoint_name)
        raise
