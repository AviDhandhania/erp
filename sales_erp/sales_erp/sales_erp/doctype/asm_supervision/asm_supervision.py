"""DocType controller for ASM Supervision."""

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, nowdate

from sales_erp import supervision


class ASMSupervision(Document):
    def before_insert(self):
        if not self.flags.ignore_permissions:
            supervision.assert_supervision_admin()
        if not self.assigned_by:
            self.assigned_by = frappe.session.user
        if not self.assigned_on:
            self.assigned_on = now_datetime()
        if not self.effective_from:
            self.effective_from = nowdate()

    def validate(self):
        if not self.flags.ignore_permissions:
            supervision.assert_supervision_admin()

        self.asm = (self.asm or "").strip()
        self.rsm = (self.rsm or "").strip()
        self.territory = (self.territory or "").strip()

        supervision.validate_asm_user(self.asm)
        supervision.validate_rsm_user(self.rsm)

        if self.asm == self.rsm:
            frappe.throw(
                frappe._("An Area Sales Manager cannot supervise themselves."),
                frappe.ValidationError,
            )

        supervision.validate_assignment_territory(self.asm, self.rsm, self.territory)

        if not self.effective_from:
            self.effective_from = nowdate()

        from_date = getdate(self.effective_from)
        to_date = getdate(self.effective_to) if self.effective_to else None

        if to_date and to_date < from_date:
            frappe.throw(
                frappe._("Effective To date cannot be earlier than Effective From date."),
                frappe.ValidationError,
            )

        # Enforce that an ASM can only have one active supervising RSM across overlapping dates
        if self.status == "Active":
            today = getdate(nowdate())
            if from_date > today or (to_date and to_date < today):
                frappe.throw(
                    frappe._("An active territory assignment must include today's date."),
                    frappe.ValidationError,
                )
            # Row lock existing active records for this ASM
            frappe.db.sql(
                """
                SELECT name FROM `tabASM Supervision`
                WHERE asm = %s AND status = 'Active' AND name != %s
                FOR UPDATE
                """,
                (self.asm, self.name or ""),
            )

            existing_active = frappe.get_all(
                "ASM Supervision",
                filters={
                    "asm": self.asm,
                    "status": "Active",
                    "name": ["!=", self.name or ""],
                },
                fields=["name", "rsm", "effective_from", "effective_to"],
            )

            for other in existing_active:
                other_from = getdate(other.effective_from)
                other_to = getdate(other.effective_to) if other.effective_to else None
                # Two ranges [A, B] and [C, D] overlap if (B is None or B >= C) and (D is None or D >= A)
                overlaps = (to_date is None or to_date >= other_from) and (
                    other_to is None or other_to >= from_date
                )
                if overlaps:
                    frappe.throw(
                        frappe._(
                            "Area Sales Manager {0} already has an active supervising RSM ({1}) "
                            "with overlapping effective dates. End or supersede the existing assignment first."
                        ).format(self.asm, other.rsm),
                        frappe.ValidationError,
                    )

            territory_conflict = frappe.db.get_value(
                "ASM Supervision",
                {
                    "territory": self.territory,
                    "status": "Active",
                    "name": ["!=", self.name or ""],
                },
                ["name", "asm"],
                as_dict=True,
            )
            if territory_conflict:
                frappe.throw(
                    frappe._(
                        "Territory {0} is already assigned to Area Sales Manager {1}."
                    ).format(self.territory, territory_conflict.asm),
                    frappe.ValidationError,
                )

    def on_update(self):
        previous = self.get_doc_before_save()
        if previous and (
            previous.status == "Active"
            and (
                self.status != "Active"
                or previous.asm != self.asm
                or previous.rsm != self.rsm
                or previous.territory != self.territory
            )
        ):
            supervision.remove_assignment_permissions(previous)
        if self.status == "Active":
            supervision.sync_assignment_permissions(self)

    def after_insert(self):
        if self.status == "Active":
            supervision.sync_assignment_permissions(self)

    def on_trash(self):
        if not self.flags.ignore_permissions:
            supervision.assert_supervision_admin()
        supervision.remove_assignment_permissions(self)

