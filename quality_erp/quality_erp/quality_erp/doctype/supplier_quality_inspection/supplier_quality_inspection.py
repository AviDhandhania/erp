# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime
from quality_erp.security import assert_can_approve_quality_gate, get_current_user


class SupplierQualityInspection(Document):
    def before_validate(self):
        if not self.inspector:
            self.inspector = get_current_user()

        if not self.company:
            if self.purchase_order:
                self.company = frappe.db.get_value("Purchase Order", self.purchase_order, "company")
            elif self.production_quality_cycle:
                self.company = frappe.db.get_value("Production Quality Cycle", self.production_quality_cycle, "company")
            if not self.company:
                comp = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value("Global Defaults", "default_company")
                if comp and frappe.db.exists("Company", comp):
                    self.company = comp

        # Calculate defect counts by severity
        crit_count = 0
        maj_count = 0
        min_count = 0
        for d in self.get("defects") or []:
            cnt = int(d.defect_count or 1)
            if d.severity == "Critical":
                crit_count += cnt
            elif d.severity == "Major":
                maj_count += cnt
            else:
                min_count += cnt
        self.critical_defects_count = crit_count
        self.major_defects_count = maj_count
        self.minor_defects_count = min_count

        # Automatically calculate sampled passed/failed quantities if sample_size given
        if self.sample_size and int(self.sample_size) > 0:
            sample = int(self.sample_size)
            total_defective = crit_count + maj_count + min_count
            if not self.failed_quantity and total_defective > 0:
                self.failed_quantity = min(sample, total_defective)
            if not self.passed_quantity:
                self.passed_quantity = max(0, sample - int(self.failed_quantity or 0))

        # Recalculate measurement variances and in-spec status
        for m in self.get("measurements") or []:
            target = flt(m.spec_target)
            actual = flt(m.actual_reading)
            tol_plus = flt(m.tolerance_plus)
            tol_minus = flt(m.tolerance_minus)
            m.variance = round(actual - target, 4)
            if actual > (target + tol_plus) or actual < (target - tol_minus):
                m.reading_status = "Out of Spec"
            else:
                m.reading_status = "In Spec"

        # Corrective action handling
        if self.corrective_action:
            self.corrective_action_required = 1
        if self.corrective_action_status == "Resolved" and not self.resolved_date:
            self.resolved_date = now_datetime()

        # Status and Result synchronization
        if self.status in ("Approved", "Conditionally Approved") and self.result in ("Pending Review", "Failed"):
            self.result = "Passed" if self.status == "Approved" else "Conditionally Passed"
        elif self.status == "Rejected" and self.result in ("Pending Review", "Passed"):
            self.result = "Failed"

        if self.checklist_template and not self.checklist_template_version:
            self.checklist_template_version = frappe.db.get_value(
                "Quality Checklist Template", self.checklist_template, "version"
            ) or 1

    def validate(self):
        if self.gate_locked and not self.is_new() and self.has_value_changed("status"):
            frappe.throw(
                _("Inspection {0} is locked to gate decision '{1}' and its status cannot be modified.").format(
                    self.name, self.locked_gate_decision or "Approved Gate"
                ),
                frappe.ValidationError,
            )

        # Enforce server-side security gate check if status is set to Approved or Conditionally Approved
        if self.status in ("Approved", "Conditionally Approved") and self.has_value_changed("status"):
            assert_can_approve_quality_gate(self.stage)

        # Validate linked Production Quality Cycle if specified
        if self.production_quality_cycle:
            cycle = frappe.db.get_value(
                "Production Quality Cycle",
                self.production_quality_cycle,
                ["company", "supplier", "item_code"],
                as_dict=True,
            )
            if cycle:
                if self.company and cycle.company and self.company != cycle.company:
                    frappe.throw(
                        _("Company mismatch: inspection company '{0}' differs from cycle company '{1}'.").format(
                            self.company, cycle.company
                        ),
                        frappe.ValidationError,
                    )
                if self.supplier and cycle.supplier and self.supplier != cycle.supplier:
                    frappe.throw(
                        _("Supplier mismatch: inspection supplier '{0}' differs from cycle supplier '{1}'.").format(
                            self.supplier, cycle.supplier
                        ),
                        frappe.ValidationError,
                    )

    def on_update(self):
        # If this inspection supersedes another, mark prior revision as superseded and not latest
        if self.supersedes and frappe.db.exists("Supplier Quality Inspection", self.supersedes):
            frappe.db.set_value(
                "Supplier Quality Inspection",
                self.supersedes,
                {"superseded_by": self.name, "is_latest": 0},
                update_modified=False,
            )

        # Sync progress to parent Production Quality Cycle if linked
        if self.production_quality_cycle and frappe.db.exists("Production Quality Cycle", self.production_quality_cycle):
            try:
                cycle_doc = frappe.get_doc("Production Quality Cycle", self.production_quality_cycle)
                cycle_doc.flags.ignore_permissions = True
                cycle_doc.update_stage_progress()
                cycle_doc.save()
            except Exception:
                pass
