"""Unit tests for the explicit RSM-to-ASM supervision model."""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import add_days, getdate, nowdate

from clothing_erp import security, supervision
from clothing_erp.clothing_erp.doctype.asm_supervision import asm_supervision
from clothing_erp.roles import ROLE_ASM, ROLE_BUSINESS_ADMIN, ROLE_RSM


class TestSupervision(unittest.TestCase):
    def test_asm_validation_requires_enabled_system_user_with_asm_role(self):
        with patch.object(frappe.db, "get_value", return_value=frappe._dict(enabled=0, user_type="System User")):
            with self.assertRaisesRegex(frappe.ValidationError, "enabled System User"):
                supervision.validate_asm_user("disabled_asm@example.invalid")

        with (
            patch.object(frappe.db, "get_value", return_value=frappe._dict(enabled=1, user_type="System User")),
            patch.object(frappe, "get_roles", return_value=["Some Other Role"]),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "Clothing Area Sales Manager role"):
                supervision.validate_asm_user("wrong_role@example.invalid")

        with (
            patch.object(frappe.db, "get_value", return_value=frappe._dict(enabled=1, user_type="System User")),
            patch.object(frappe, "get_roles", return_value=[ROLE_ASM]),
        ):
            supervision.validate_asm_user("valid_asm@example.invalid")

    def test_rsm_validation_requires_enabled_system_user_with_rsm_role(self):
        with patch.object(frappe.db, "get_value", return_value=frappe._dict(enabled=0, user_type="System User")):
            with self.assertRaisesRegex(frappe.ValidationError, "enabled System User"):
                supervision.validate_rsm_user("disabled_rsm@example.invalid")

        with (
            patch.object(frappe.db, "get_value", return_value=frappe._dict(enabled=1, user_type="System User")),
            patch.object(frappe, "get_roles", return_value=["Some Other Role"]),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "Clothing Regional Sales Manager role"):
                supervision.validate_rsm_user("wrong_role@example.invalid")

        with (
            patch.object(frappe.db, "get_value", return_value=frappe._dict(enabled=1, user_type="System User")),
            patch.object(frappe, "get_roles", return_value=[ROLE_RSM]),
        ):
            supervision.validate_rsm_user("valid_rsm@example.invalid")

    def test_asm_cannot_supervise_themselves(self):
        doc = asm_supervision.ASMSupervision(
            {
                "doctype": "ASM Supervision",
                "asm": "same_user@example.invalid",
                "rsm": "same_user@example.invalid",
                "effective_from": nowdate(),
            }
        )
        with (
            patch.object(supervision, "assert_supervision_admin"),
            patch.object(supervision, "validate_asm_user"),
            patch.object(supervision, "validate_rsm_user"),
            self.assertRaisesRegex(frappe.ValidationError, "cannot supervise themselves"),
        ):
            doc.validate()

    def test_assignment_requires_an_existing_leaf_territory(self):
        with patch.object(frappe.db, "exists", return_value=False):
            with self.assertRaisesRegex(frappe.ValidationError, "existing Sales Territory"):
                supervision.validate_assignment_territory(
                    "asm@example.invalid", "rsm@example.invalid", "Missing"
                )

        with (
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe.db, "get_value", return_value=1),
            self.assertRaisesRegex(frappe.ValidationError, "leaf Sales Territory"),
        ):
            supervision.validate_assignment_territory(
                "asm@example.invalid", "rsm@example.invalid", "Group"
            )

        with (
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe.db, "get_value", return_value=0),
        ):
            supervision.validate_assignment_territory(
                "asm@example.invalid", "rsm@example.invalid", "TEST North"
            )

    def test_date_validation_effective_to_cannot_precede_effective_from(self):
        doc = asm_supervision.ASMSupervision(
            {
                "doctype": "ASM Supervision",
                "asm": "asm@example.invalid",
                "rsm": "rsm@example.invalid",
                "territory": "TEST North",
                "status": "Active",
                "effective_from": "2026-11-20",
                "effective_to": "2026-11-10",
            }
        )
        with (
            patch.object(supervision, "assert_supervision_admin"),
            patch.object(supervision, "validate_asm_user"),
            patch.object(supervision, "validate_rsm_user"),
            patch.object(supervision, "validate_assignment_territory"),
            self.assertRaisesRegex(frappe.ValidationError, "cannot be earlier than"),
        ):
            doc.validate()

    def test_asm_can_have_only_one_active_supervising_rsm_at_overlapping_dates(self):
        existing_active = [
            frappe._dict(
                name="ASM-SUP-2026-00001",
                rsm="rsm1@example.invalid",
                effective_from=getdate("2026-11-01"),
                effective_to=None,
            )
        ]
        doc = asm_supervision.ASMSupervision(
            {
                "doctype": "ASM Supervision",
                "name": "ASM-SUP-2026-00002",
                "asm": "asm@example.invalid",
                "rsm": "rsm2@example.invalid",
                "territory": "TEST North",
                "status": "Active",
                "effective_from": "2026-11-15",
                "effective_to": None,
            }
        )
        with (
            patch.object(supervision, "assert_supervision_admin"),
            patch.object(supervision, "validate_asm_user"),
            patch.object(supervision, "validate_rsm_user"),
            patch.object(supervision, "validate_assignment_territory"),
            patch(
                "clothing_erp.clothing_erp.doctype.asm_supervision.asm_supervision.nowdate",
                return_value="2026-11-15",
            ),
            patch.object(frappe.db, "sql"),
            patch.object(frappe, "get_all", return_value=existing_active),
            patch.object(frappe.db, "get_value", return_value=None),
            self.assertRaisesRegex(frappe.ValidationError, "already has an active supervising RSM"),
        ):
            doc.validate()

    def test_rsm_can_supervise_multiple_asms(self):
        # RSM1 can supervise ASM1 and ASM2 without conflict
        doc1 = asm_supervision.ASMSupervision(
            {
                "doctype": "ASM Supervision",
                "name": "ASM-SUP-2026-00001",
                "asm": "asm1@example.invalid",
                "rsm": "rsm1@example.invalid",
                "territory": "TEST North",
                "status": "Active",
                "effective_from": "2026-11-01",
            }
        )
        doc2 = asm_supervision.ASMSupervision(
            {
                "doctype": "ASM Supervision",
                "name": "ASM-SUP-2026-00002",
                "asm": "asm2@example.invalid",
                "rsm": "rsm1@example.invalid",
                "territory": "TEST South",
                "status": "Active",
                "effective_from": "2026-11-01",
            }
        )
        with (
            patch.object(supervision, "assert_supervision_admin"),
            patch.object(supervision, "validate_asm_user"),
            patch.object(supervision, "validate_rsm_user"),
            patch.object(supervision, "validate_assignment_territory"),
            patch.object(frappe.db, "sql"),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe, "get_all", return_value=[]),
        ):
            doc1.validate()
            doc2.validate()

    def test_non_admin_cannot_save_asm_supervision(self):
        doc = asm_supervision.ASMSupervision(
            {
                "doctype": "ASM Supervision",
                "asm": "asm@example.invalid",
                "rsm": "rsm@example.invalid",
                "effective_from": nowdate(),
            }
        )
        with (
            patch.object(supervision, "is_supervision_admin", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            doc.validate()

    def test_admin_can_reassign_asm_supervision_safely_preserving_history(self):
        old_doc = MagicMock()
        old_doc.name = "ASM-SUP-2026-00001"
        old_doc.rsm = "old_rsm@example.invalid"
        old_doc.effective_from = getdate("2026-11-01")

        created_doc = MagicMock()
        created_doc.name = "ASM-SUP-2026-00002"

        real_get_doc = frappe.get_doc
        real_sql = frappe.db.sql

        def mock_get_doc(*args, **kwargs):
            if args:
                first = args[0]
                if first == "ASM Supervision" or (isinstance(first, dict) and first.get("doctype") == "ASM Supervision"):
                    if isinstance(first, str) and len(args) > 1 and args[1] == "ASM-SUP-2026-00001":
                        return old_doc
                    return created_doc
                if first == "Retailer Assignment History" or (isinstance(first, dict) and first.get("doctype") == "Retailer Assignment History"):
                    mock_hist = MagicMock()
                    mock_hist.name = "RET-ASG-001"
                    return mock_hist
            return real_get_doc(*args, **kwargs)

        def mock_sql(query, *args, **kwargs):
            if "FOR UPDATE" in str(query):
                return []
            return real_sql(query, *args, **kwargs)

        with (
            patch.object(supervision, "assert_supervision_admin"),
            patch.object(supervision, "validate_asm_user"),
            patch.object(supervision, "validate_rsm_user"),
            patch.object(supervision, "validate_assignment_territory"),
            patch.object(frappe.db, "sql", side_effect=mock_sql),
            patch.object(
                frappe,
                "get_all",
                return_value=[
                    frappe._dict(
                        name="ASM-SUP-2026-00001",
                        rsm="old_rsm@example.invalid",
                        territory="TEST North",
                        effective_from=getdate("2026-11-01"),
                        effective_to=None,
                    )
                ],
            ),
            patch.object(frappe, "get_doc", side_effect=mock_get_doc),
            patch.object(frappe, "clear_cache"),
        ):
            result = supervision.assign_asm_supervision(
                asm="asm@example.invalid",
                rsm="new_rsm@example.invalid",
                territory="TEST North",
                effective_from="2026-11-15",
                reason="Territory realignment",
            )
            self.assertEqual(result["unchanged"], False)
            self.assertEqual(result["superseded"], ["ASM-SUP-2026-00001"])
            self.assertEqual(old_doc.status, "Superseded")
            self.assertEqual(old_doc.effective_to, getdate("2026-11-14"))
            old_doc.save.assert_called_once()
            created_doc.insert.assert_called_once()

    def test_end_asm_supervision(self):
        active_doc = MagicMock()
        active_doc.name = "ASM-SUP-2026-00001"
        active_doc.status = "Active"
        active_doc.effective_from = "2026-11-01"
        active_doc.asm = "asm@example.invalid"
        active_doc.rsm = "rsm@example.invalid"
        active_doc.reason = "Initial"

        with (
            patch.object(supervision, "assert_supervision_admin"),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe.db, "sql"),
            patch.object(frappe, "get_doc", return_value=active_doc),
            patch.object(frappe, "clear_cache"),
        ):
            result = supervision.end_asm_supervision(
                "ASM-SUP-2026-00001",
                reason="ASM leave of absence",
                end_date="2026-11-20",
            )
            self.assertEqual(result["status"], "Cancelled")
            self.assertEqual(active_doc.status, "Cancelled")
            self.assertEqual(str(active_doc.effective_to), "2026-11-20")
            self.assertIn("ASM leave of absence", active_doc.reason)
            active_doc.save.assert_called_once()

    def test_get_active_supervising_rsm_and_get_supervised_asms(self):
        with patch.object(
            frappe.db,
            "sql",
            return_value=[frappe._dict(rsm="active_rsm@example.invalid")],
        ):
            rsm = supervision.get_active_supervising_rsm("asm@example.invalid", "2026-11-16")
            self.assertEqual(rsm, "active_rsm@example.invalid")

        with (
            patch.object(
                frappe.db,
                "sql",
                return_value=[
                    frappe._dict(asm="asm1@example.invalid"),
                    frappe._dict(asm="asm2@example.invalid"),
                ],
            ),
        ):
            supervised = supervision.get_supervised_asms("rsm@example.invalid", "2026-11-16")
            self.assertEqual(supervised, ["asm1@example.invalid", "asm2@example.invalid"])

    def test_is_active_supervisor_checks_supervision_and_territory(self):
        with (
            patch.object(
                supervision,
                "get_active_supervising_rsm",
                return_value="rsm1@example.invalid",
            ),
        ):
            self.assertTrue(supervision.is_active_supervisor("rsm1@example.invalid", "asm1@example.invalid"))
            # Different supervisor -> False
            self.assertFalse(supervision.is_active_supervisor("other_rsm@example.invalid", "asm1@example.invalid"))

    def test_assert_rsm_supervises_asm_checks_supervisor_and_territory(self):
        with patch.object(supervision, "get_active_supervising_rsm", return_value=None):
            with self.assertRaisesRegex(frappe.PermissionError, "has no active supervising"):
                supervision.assert_rsm_supervises_asm("rsm@example.invalid", "asm@example.invalid")

        with patch.object(supervision, "get_active_supervising_rsm", return_value="other_rsm@example.invalid"):
            with self.assertRaisesRegex(frappe.PermissionError, "You do not supervise"):
                supervision.assert_rsm_supervises_asm("rsm@example.invalid", "asm@example.invalid")

        with (
            patch.object(supervision, "get_active_supervising_rsm", return_value="rsm@example.invalid"),
            patch.object(frappe.db, "get_value", return_value="TEST North"),
        ):
            # Outside territory -> PermissionError
            with self.assertRaisesRegex(frappe.PermissionError, "not authorized to manage actions in territory"):
                supervision.assert_rsm_supervises_asm(
                    "rsm@example.invalid", "asm@example.invalid", territory="TEST South"
                )
            # Valid territory -> succeeds without error
            supervision.assert_rsm_supervises_asm(
                "rsm@example.invalid", "asm@example.invalid", territory="TEST North"
            )

    def test_asm_supervision_query_conditions(self):
        with patch.object(security, "is_clothing_admin", return_value=True):
            self.assertEqual(security.asm_supervision_conditions("admin@example.invalid"), "")

        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_RSM}),
            patch.object(security, "get_current_user", return_value="rsm@example.invalid"),
        ):
            condition = security.asm_supervision_conditions("rsm@example.invalid")
            self.assertEqual(condition, "`tabASM Supervision`.`rsm` = 'rsm@example.invalid'")

        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_ASM}),
            patch.object(security, "get_current_user", return_value="asm@example.invalid"),
        ):
            condition = security.asm_supervision_conditions("asm@example.invalid")
            self.assertEqual(condition, "`tabASM Supervision`.`asm` = 'asm@example.invalid'")

        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={"Guest"}),
            patch.object(security, "get_current_user", return_value="Guest"),
        ):
            self.assertEqual(security.asm_supervision_conditions("Guest"), "1=0")

    def test_asm_supervision_has_permission(self):
        doc = frappe._dict(doctype="ASM Supervision", asm="asm@example.invalid", rsm="rsm@example.invalid")

        with patch.object(security, "is_clothing_admin", return_value=True):
            self.assertTrue(security.asm_supervision_has_permission(doc, "admin@example.invalid", "write"))

        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_RSM}),
            patch.object(security, "get_current_user", return_value="rsm@example.invalid"),
        ):
            # Mutation rejected for RSM
            self.assertFalse(security.asm_supervision_has_permission(doc, "rsm@example.invalid", "write"))

            self.assertTrue(security.asm_supervision_has_permission(doc, "rsm@example.invalid", "read"))

        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_ASM}),
            patch.object(security, "get_current_user", return_value="asm@example.invalid"),
        ):
            # ASM can read own doc
            self.assertTrue(security.asm_supervision_has_permission(doc, "asm@example.invalid", "read"))
            # ASM cannot write own doc
            self.assertFalse(security.asm_supervision_has_permission(doc, "asm@example.invalid", "write"))
            # Different ASM cannot read doc
            other_doc = frappe._dict(doctype="ASM Supervision", asm="other_asm@example.invalid", rsm="rsm@example.invalid")
            self.assertFalse(security.asm_supervision_has_permission(other_doc, "asm@example.invalid", "read"))

    def test_sales_role_user_query_filters_by_specific_role(self):
        with (
            patch.object(security, "has_any_role", return_value=True),
            patch.object(frappe.db, "sql", return_value=[["test-asm@example.invalid", "Test ASM"]]) as mock_sql,
        ):
            res = supervision.sales_role_user_query(
                "User", "test", "name", 0, 20, {"role": ROLE_ASM}
            )
            self.assertEqual(len(res), 1)
            query_calls = [c for c in mock_sql.call_args_list if len(c[0]) > 0 and "tabHas Role" in str(c[0][0])]
            self.assertEqual(len(query_calls), 1)
            args = query_calls[0][0][1]
            self.assertEqual(args["role"], ROLE_ASM)
            self.assertEqual(args["txt"], "%test%")

        with patch.object(security, "has_any_role", return_value=True):
            empty_res = supervision.sales_role_user_query("User", "test", "name", 0, 20, {})
            self.assertEqual(empty_res, [])

    def test_record_assignment_history_creates_immutable_log(self):
        with (
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(supervision, "get_current_user", return_value="admin@example.invalid"),
            patch.object(frappe, "get_doc") as mock_get_doc,
        ):
            mock_doc = MagicMock()
            mock_doc.name = "RET-ASG-001"
            mock_get_doc.return_value = mock_doc

            res = supervision.record_assignment_history(
                territory="TEST Territory",
                new_asm="new_asm@example.invalid",
                previous_asm="prev_asm@example.invalid",
                new_rsm="new_rsm@example.invalid",
                previous_rsm="prev_rsm@example.invalid",
                reason="Reassigned territory",
            )
            self.assertEqual(res, "RET-ASG-001")
            mock_get_doc.assert_called_once()
            doc_data = mock_get_doc.call_args[0][0]
            self.assertEqual(doc_data["territory"], "TEST Territory")
            self.assertEqual(doc_data["new_asm"], "new_asm@example.invalid")
            self.assertEqual(doc_data["previous_asm"], "prev_asm@example.invalid")
            self.assertEqual(doc_data["new_rsm"], "new_rsm@example.invalid")
            self.assertEqual(doc_data["previous_rsm"], "prev_rsm@example.invalid")
            self.assertEqual(doc_data["reason"], "Reassigned territory")
            self.assertTrue(mock_doc.flags.clothing_assignment_event)
            mock_doc.insert.assert_called_once_with(ignore_permissions=True)

    def test_retailer_assignment_history_permissions_and_conditions(self):
        doc = frappe._dict(
            doctype="Retailer Assignment History",
            territory="TEST Territory",
            new_asm="asm@example.invalid",
            new_rsm="rsm@example.invalid",
        )

        with patch.object(security, "is_clothing_admin", return_value=True):
            self.assertTrue(security.retailer_assignment_history_has_permission(doc, "admin@example.invalid", "read"))
            self.assertEqual(security.retailer_assignment_history_conditions("admin@example.invalid"), "")

        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_RSM}),
            patch.object(security, "get_current_user", return_value="rsm@example.invalid"),
            patch.object(security, "assigned_sales_territories", return_value=["TEST Territory"]),
        ):
            self.assertTrue(security.retailer_assignment_history_has_permission(doc, "rsm@example.invalid", "read"))
            cond = security.retailer_assignment_history_conditions("rsm@example.invalid")
            self.assertIn("new_rsm", cond)

        with (
            patch.object(security, "is_clothing_admin", return_value=False),
            patch.object(security, "get_user_roles", return_value={ROLE_ASM}),
            patch.object(security, "get_current_user", return_value="asm@example.invalid"),
            patch.object(security, "assigned_sales_territories", return_value=["TEST Territory"]),
        ):
            self.assertTrue(security.retailer_assignment_history_has_permission(doc, "asm@example.invalid", "read"))
            cond = security.retailer_assignment_history_conditions("asm@example.invalid")
            self.assertIn("new_asm", cond)
