import frappe
from frappe import _
from frappe.model.document import Document
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

    def validate(self):
        # Enforce server-side security gate check if status is set to Approved
        if self.status == "Approved" and self.has_value_changed("status"):
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
        # Sync progress to parent Production Quality Cycle if linked
        if self.production_quality_cycle and frappe.db.exists("Production Quality Cycle", self.production_quality_cycle):
            try:
                cycle_doc = frappe.get_doc("Production Quality Cycle", self.production_quality_cycle)
                cycle_doc.flags.ignore_permissions = True
                cycle_doc.update_stage_progress()
                cycle_doc.save()
            except Exception:
                pass
