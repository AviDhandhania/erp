# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

from warehouse_erp.api_security import record_security_audit_event
from warehouse_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_WAREHOUSE_MANAGER
from warehouse_erp.security import (
    assigned_warehouses,
    get_current_user,
    is_warehouse_admin,
    require_role,
)


class DeliveryHandoff(Document):
    def before_insert(self):
        if not self.handed_over_by:
            self.handed_over_by = get_current_user()
        if not self.handed_over_on:
            self.handed_over_on = now_datetime()

    def validate(self):
        require_role({ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN})
        self._validate_delivery_note()
        self._validate_immutability()
        self._validate_packages_and_handler()

    def _validate_delivery_note(self):
        if not self.delivery_note:
            frappe.throw(_("Delivery Note is required for delivery handoff."), frappe.ValidationError)

        dn = frappe.db.get_value(
            "Delivery Note",
            self.delivery_note,
            ["name", "docstatus", "customer", "customer_name", "company"],
            as_dict=True,
        )
        if not dn:
            frappe.throw(_("Delivery Note {0} does not exist.").format(self.delivery_note), frappe.DoesNotExistError)

        if dn.docstatus != 1:
            frappe.throw(
                _("Delivery Note {0} must be submitted before recording delivery handoff.").format(self.delivery_note),
                frappe.ValidationError,
            )

        # Scoping: user must have permission on the warehouses of this Delivery Note
        user = get_current_user()
        if not is_warehouse_admin(user):
            allowed_warehouses = set(assigned_warehouses(user))
            dn_warehouses = set(
                frappe.get_all(
                    "Delivery Note Item",
                    filters={"parent": self.delivery_note},
                    pluck="warehouse",
                )
            )
            if not allowed_warehouses or not (dn_warehouses <= allowed_warehouses):
                frappe.throw(
                    _("You do not have permission to hand over deliveries for the warehouses in {0}.").format(
                        self.delivery_note
                    ),
                    frappe.PermissionError,
                )

        if not self.customer:
            self.customer = dn.customer
        if not self.customer_name:
            self.customer_name = dn.customer_name
        if not self.company:
            self.company = dn.company

    def _validate_immutability(self):
        if not self.is_new():
            # Delivery Handoff is an immutable physical audit event
            db_doc = frappe.db.get_value(
                "Delivery Handoff",
                self.name,
                ["delivery_note", "transporter_name", "accepted_by_handler", "handed_over_by"],
                as_dict=True,
            )
            if db_doc:
                for field in ("delivery_note", "transporter_name", "accepted_by_handler", "handed_over_by"):
                    if getattr(self, field) != db_doc.get(field):
                        frappe.throw(
                            _("Delivery Handoff records are immutable. Field '{0}' cannot be changed.").format(field),
                            frappe.PermissionError,
                        )

    def _validate_packages_and_handler(self):
        if cint(self.packages_count) < 1:
            frappe.throw(_("Package count must be at least 1."), frappe.ValidationError)

        if not self.transporter_name or len(self.transporter_name.strip()) < 2:
            frappe.throw(_("Transporter Name must be specified."), frappe.ValidationError)

        if not self.accepted_by_handler or len(self.accepted_by_handler.strip()) < 2:
            frappe.throw(
                _("Accepted By (Carrier Handler / Driver) must be specified with at least 2 characters."),
                frappe.ValidationError,
            )

    def after_insert(self):
        # Update link on Delivery Note if custom field exists
        if frappe.db.has_column("Delivery Note", "custom_delivery_handoff"):
            frappe.db.set_value(
                "Delivery Note",
                self.delivery_note,
                "custom_delivery_handoff",
                self.name,
                update_modified=False,
            )

        record_security_audit_event(
            "Delivery Handed Over",
            "Delivery Handoff",
            self.name,
            {
                "delivery_note": self.delivery_note,
                "customer": self.customer,
                "transporter_name": self.transporter_name,
                "accepted_by_handler": self.accepted_by_handler,
                "packages_count": cint(self.packages_count),
                "handed_over_by": self.handed_over_by,
            },
        )
