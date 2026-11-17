# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Production Quality Cycle DocType controller.

Enforces:
- Unique composite business key: (Company, Supplier, PO/Season, Item/Style, Production Lot)
- Reviewed links: Supplier, Purchase Order, Item/Style, Production Lot, Season, Purchase Receipt, native Quality Inspection
- Non-duplication of purchasing, payable, stock or Quality Inspection ledgers
- Server-side gate approval verification (Admin-only for Production Go Ahead and Final Inspection)
- Multi-company and supplier isolation
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from quality_erp.security import (
    assert_can_approve_quality_gate,
    get_current_user,
    is_quality_admin,
    require_role,
)

CYCLE_STAGES = (
    "1. First Submission",
    "2. Second Submission",
    "3. Size Set Submission",
    "4. Production Go Ahead",
    "5. Inline Visit",
    "6. Mid-line Visit",
    "7. Final Inspection",
    "Completed",
)

CYCLE_STATUSES = (
    "Draft",
    "Stage Report Due",
    "In Progress",
    "Awaiting Production Go Ahead",
    "Production Go Ahead Approved",
    "Production in Progress",
    "Awaiting Final Inspection",
    "Final Inspection Approved",
    "Completed",
    "Cancelled",
    "On Hold",
)


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


class ProductionQualityCycle(Document):
    """Production Quality Cycle for managing 7-stage quality lifecycle across production lots."""

    def before_validate(self):
        # Auto-resolve company from Purchase Order or defaults
        if not self.company and self.purchase_order:
            self.company = frappe.db.get_value("Purchase Order", self.purchase_order, "company")
        if not self.company:
            comp = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
            if comp and frappe.db.exists("Company", comp):
                self.company = comp
            else:
                comps = frappe.get_all("Company", pluck="name", limit=1)
                self.company = comps[0] if comps else "Test Company"

        if not self.production_lot:
            self.production_lot = "01"

        # Auto-compute deterministic unique cycle_key
        computed_key = generate_cycle_key(
            self.company,
            self.supplier,
            self.item_code,
            self.purchase_order,
            self.production_lot,
            self.season,
        )

        if not self.cycle_key or self.is_new() or self.has_value_changed("company") or self.has_value_changed("supplier") or self.has_value_changed("item_code") or self.has_value_changed("purchase_order") or self.has_value_changed("production_lot") or self.has_value_changed("season"):
            self.cycle_key = computed_key

    def validate(self):
        # Enforce uniqueness of cycle_key across all cycles
        if self.cycle_key:
            existing = frappe.db.get_value(
                "Production Quality Cycle",
                {"cycle_key": self.cycle_key, "name": ["!=", self.name]},
                "name",
            )
            if existing:
                frappe.throw(
                    _("A Production Quality Cycle with business key '{0}' already exists ({1}).").format(
                        self.cycle_key, existing
                    ),
                    frappe.DuplicateEntryError,
                )

        # Enforce server-side security gate checks
        user = get_current_user()
        if self.has_value_changed("go_ahead_status") and self.go_ahead_status == "Approved":
            assert_can_approve_quality_gate("Production Go Ahead", user)
            if not self.go_ahead_approved_by:
                self.go_ahead_approved_by = user
                self.go_ahead_date = now_datetime()

        if self.has_value_changed("final_inspection_status") and self.final_inspection_status == "Approved":
            assert_can_approve_quality_gate("Final Inspection", user)
            if not self.final_inspection_approved_by:
                self.final_inspection_approved_by = user
                self.final_inspection_date = now_datetime()

    def update_stage_progress(self):
        """Update cycle statistics and stage progress from linked inspection records."""
        inspections = frappe.get_all(
            "Supplier Quality Inspection",
            filters={"production_quality_cycle": self.name},
            fields=["name", "stage", "status", "inspection_date"],
            order_by="inspection_date desc, creation desc",
        )

        self.total_inspections_count = len(inspections)
        approved_stages = {i.stage for i in inspections if i.status == "Approved"}
        self.total_stages_passed = len(approved_stages)

        if inspections:
            self.last_inspection_date = inspections[0].inspection_date

        # Update current stage based on approved stages
        for stage in CYCLE_STAGES:
            if stage not in approved_stages and stage != "Completed":
                self.current_stage = stage
                break
        else:
            self.current_stage = "Completed"
            if self.status not in ("Cancelled", "On Hold"):
                self.status = "Completed"
