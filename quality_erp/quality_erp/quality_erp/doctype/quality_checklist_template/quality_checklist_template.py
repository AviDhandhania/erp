# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from quality_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_QUALITY_MANAGER
from quality_erp.security import get_current_user, require_role


class QualityChecklistTemplate(Document):
    def validate(self):
        if not self.template_name:
            frappe.throw(_("Template Name is required."), frappe.ValidationError)

        self.version = int(self.version or 1)

        # Enforce uniqueness of (template_name, version)
        existing = frappe.db.get_value(
            "Quality Checklist Template",
            {
                "template_name": self.template_name,
                "version": self.version,
                "name": ["!=", self.name],
            },
            "name",
        )
        if existing:
            frappe.throw(
                _("Checklist template '{0}' with version {1} already exists ({2}).").format(
                    self.template_name, self.version, existing
                ),
                frappe.DuplicateEntryError,
            )

        # Enforce role checks for creating/modifying templates
        require_role({ROLE_QUALITY_MANAGER, ROLE_BUSINESS_ADMIN, "System Manager"})
