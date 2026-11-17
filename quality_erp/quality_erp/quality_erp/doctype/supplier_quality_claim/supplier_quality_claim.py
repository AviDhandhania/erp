# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from quality_erp.roles import ROLE_BUSINESS_ADMIN
from quality_erp.security import get_current_user, is_quality_admin


class SupplierQualityClaim(Document):
    def validate(self):
        self.claim_quantity = flt(self.claim_quantity)
        self.claim_amount = flt(self.claim_amount)
        self.settled_amount = flt(self.settled_amount)

        if self.claim_quantity <= 0:
            frappe.throw(_("Claim Quantity must be greater than zero."), frappe.ValidationError)
        if self.claim_amount < 0:
            frappe.throw(_("Claim Amount cannot be negative."), frappe.ValidationError)

        # Enforce business admin requirement for approval
        if self.status in ("Approved by Business", "Settled"):
            user = get_current_user()
            if not is_quality_admin(user):
                frappe.throw(
                    _("Only Clothing Business Administrators can approve or settle supplier claims."),
                    frappe.PermissionError,
                )
            if not self.approved_by:
                self.approved_by = user
            if not self.approval_date:
                self.approval_date = now_datetime()

        if not self.claim_key:
            token = self.name or frappe.generate_hash(length=8)
            self.claim_key = f"{self.company}::{self.supplier}::{self.item_code}::{token}"
