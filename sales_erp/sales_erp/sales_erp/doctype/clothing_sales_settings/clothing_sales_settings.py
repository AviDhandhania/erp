"""Single DocType managing global Sales ERP policies, cadence intervals, and capacity thresholds."""

import frappe
from frappe import _
from frappe.model.document import Document

from sales_erp.api_security import record_security_audit_event
from sales_erp.security import get_current_user, is_clothing_admin


class ClothingSalesSettings(Document):
    def validate(self):
        user = get_current_user()
        if not is_clothing_admin(user):
            frappe.throw(
                _("Only administrators can modify Clothing Sales Settings."),
                frappe.PermissionError,
            )

        # 1. RSM Cadence Validations
        if self.rsm_warning_days >= self.rsm_cycle_days:
            frappe.throw(_("RSM Advance Warning Days must be less than RSM Visit Cycle Days."))
        if self.rsm_escalation_days < self.rsm_cycle_days:
            frappe.throw(_("RSM Escalation Days must be greater than or equal to RSM Visit Cycle Days."))
        if self.rsm_grace_days < 0:
            frappe.throw(_("RSM Grace Days cannot be negative."))

        # 2. SIS Cadence Validations
        if self.sis_stock_review_warning_days >= self.sis_stock_review_cycle_days:
            frappe.throw(_("SIS Stock Review Warning Days must be less than Cycle Days."))
        if self.sis_general_visit_warning_days >= self.sis_general_visit_cycle_days:
            frappe.throw(_("SIS General Visit Warning Days must be less than Cycle Days."))

        # 3. Buy & Sell and Collections Validations
        if self.buy_sell_visit_warning_days >= self.buy_sell_visit_cycle_days:
            frappe.throw(_("Buy & Sell Visit Warning Days must be less than Cycle Days."))
        if self.collection_window_escalation_days < self.collection_window_start_days:
            frappe.throw(_("Collection Escalation Days must be greater than or equal to Start Days."))

        # 4. Capacity & Guidance Validations
        if self.rsm_max_supervised_asms < 1:
            frappe.throw(_("Max ASMs per RSM must be at least 1."))
        if self.rsm_max_retailer_capacity < 1:
            frappe.throw(_("Max Retailers per RSM must be at least 1."))

        # 5. Seasonal Calendar Validations
        if not (1 <= self.spring_summer_start_month <= 12):
            frappe.throw(_("Spring/Summer start month must be between 1 and 12."))
        if not (1 <= self.autumn_winter_start_month <= 12):
            frappe.throw(_("Autumn/Winter start month must be between 1 and 12."))
        if self.spring_summer_start_month == self.autumn_winter_start_month:
            frappe.throw(_("Spring/Summer and Autumn/Winter start months must be distinct."))

        # 6. Check-in Validations
        if self.geolocation_tolerance_meters < 10:
            frappe.throw(_("Geolocation tolerance radius must be at least 10 meters."))

    def on_update(self):
        record_security_audit_event(
            "Sales Settings Updated",
            "Clothing Sales Settings",
            "Clothing Sales Settings",
            {
                "rsm_cycle_days": self.rsm_cycle_days,
                "collection_window_escalation_days": self.collection_window_escalation_days,
                "capacity_warning_mode": self.capacity_warning_mode,
            },
        )
