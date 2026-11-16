import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe

from clothing_erp import hooks, retailer_assignment
from clothing_erp.clothing_erp.doctype.retailer_application import retailer_application


class TestRetailerWorkflow(unittest.TestCase):
    def test_indian_retailer_addresses_require_state_server_side(self):
        application = retailer_application.RetailerApplication(
            {
                "doctype": "Retailer Application",
                "shop_name": "TEST Stateless Boutique",
                "contact_person": "TEST Contact",
                "phone": "+91 90000 11111",
                "country": "India",
                "billing_address_line1": "TEST Fictional Road",
                "billing_city": "TEST City",
            }
        )
        with (
            patch.object(
                retailer_application.RetailerApplication,
                "is_new",
                return_value=True,
            ),
            self.assertRaisesRegex(frappe.ValidationError, "Billing State"),
        ):
            application.validate()

    def test_asm_application_identity_and_territory_are_forced(self):
        application = retailer_application.RetailerApplication(
            {
                "doctype": "Retailer Application",
                "shop_name": " TEST Boutique ",
                "contact_person": " TEST Person ",
                "phone": "+91 90000 11111",
                "salesperson": "other@example.invalid",
                "customer_group": "Buy & Sell",
            }
        )
        with (
            patch.object(
                retailer_application,
                "get_user_roles",
                return_value={"Clothing Area Sales Manager"},
            ),
            patch.object(retailer_application, "is_sales_manager", return_value=False),
            patch.object(
                retailer_application,
                "get_current_user",
                return_value="sales@example.com",
            ),
            patch.object(
                retailer_application,
                "_salesperson_application_territory",
                return_value="Default Territory",
            ),
            patch.object(
                retailer_application.RetailerApplication,
                "is_new",
                return_value=True,
            ),
            patch.object(retailer_application, "_validate_salesperson"),
            patch.object(retailer_application, "_validate_salesperson_territory"),
            patch.object(retailer_application, "find_duplicates", return_value=[]),
        ):
            application.validate()
        self.assertEqual(application.salesperson, "sales@example.com")
        self.assertEqual(application.territory, "Default Territory")
        self.assertEqual(application.customer_group, "Buy & Sell")

    def test_asm_cannot_override_territory_but_selects_retailer_type(self):
        application = retailer_application.RetailerApplication(
            {
                "doctype": "Retailer Application",
                "shop_name": " TEST Boutique ",
                "contact_person": " TEST Person ",
                "phone": "+91 90000 11111",
                "salesperson": "sales@example.com",
                "territory": "Valid Territory",
                "customer_group": "SIS (Shop-in-Shop)",
            }
        )
        with (
            patch.object(
                retailer_application,
                "get_user_roles",
                return_value={"Clothing Area Sales Manager"},
            ),
            patch.object(retailer_application, "is_sales_manager", return_value=False),
            patch.object(
                retailer_application,
                "get_current_user",
                return_value="sales@example.com",
            ),
            patch.object(
                retailer_application,
                "_salesperson_application_territory",
                return_value="Default Territory",
            ),
            patch.object(
                retailer_application.RetailerApplication,
                "is_new",
                return_value=True,
            ),
            patch.object(retailer_application, "_validate_salesperson"),
            patch.object(retailer_application, "_validate_salesperson_territory"),
            patch.object(retailer_application, "find_duplicates", return_value=[]),
        ):
            application.validate()
        self.assertEqual(application.salesperson, "sales@example.com")
        self.assertEqual(application.territory, "Default Territory")
        self.assertEqual(application.customer_group, "SIS (Shop-in-Shop)")

    def test_legacy_reassignment_page_redirects_to_territory_assignments(self):
        app_root = Path(__file__).parents[1]
        page_root = app_root / "clothing_erp/page/retailer_assignments"
        page = json.loads((page_root / "retailer_assignments.json").read_text())
        script = (page_root / "retailer_assignments.js").read_text()
        self.assertNotIn("Customer", hooks.doctype_js)
        self.assertFalse((app_root / "public/js/customer_assignment.js").exists())
        self.assertFalse((app_root / "public/js/customer_list.js").exists())
        self.assertEqual(
            {row["role"] for row in page["roles"]},
            {
                "Clothing Regional Sales Manager",
                "Clothing Business Administrator",
                "System Manager",
            },
        )
        self.assertEqual(page["title"], "Sales Territory Assignments")
        self.assertIn('frappe.set_route("List", "ASM Supervision")', script)
        self.assertNotIn("reassign_retailer", script)

    def test_sales_manager_cannot_manage_another_territory(self):
        with (
            patch.object(
                retailer_assignment,
                "_manager_territories",
                return_value=["TEST North"],
            ),
            patch.object(frappe, "throw", side_effect=frappe.PermissionError),
            self.assertRaises(frappe.PermissionError),
        ):
            retailer_assignment._assert_customer_scope(
                "TEST South Retailer", territory="TEST South"
            )

    def test_legacy_reassignment_directory_is_retired(self):
        with (
            patch.object(retailer_assignment, "require_role"),
            patch.object(frappe, "get_list") as get_list,
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_assignment.get_reassignment_directory()
        get_list.assert_not_called()

    def test_legacy_reassignment_mutation_is_retired_before_database_access(self):
        with (
            patch.object(retailer_assignment, "require_role"),
            patch.object(retailer_assignment, "_lock_customer") as lock_customer,
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_assignment.reassign_retailer(
                "TEST Boutique", "asm@example.invalid", "obsolete assignment"
            )
        lock_customer.assert_not_called()

    def test_reassignment_requires_manager_before_reading_assignment_state(self):
        with (
            patch.object(
                retailer_assignment, "require_role", side_effect=frappe.PermissionError
            ),
            patch.object(
                retailer_assignment, "_validate_salesperson"
            ) as validate_salesperson,
            self.assertRaises(frappe.PermissionError),
        ):
            retailer_assignment.reassign_retailer(
                "TEST Retailer",
                "test-new-salesperson@example.invalid",
                "TEST territory change",
            )
        validate_salesperson.assert_not_called()

    def test_multiple_native_assignments_are_rejected_as_ambiguous(self):
        assignments = [
            frappe._dict(name="UP-1", user="test-one@example.invalid"),
            frappe._dict(name="UP-2", user="test-two@example.invalid"),
        ]
        with (
            patch.object(retailer_assignment, "_assignments", return_value=assignments),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_assignment._single_assignment("TEST Retailer")

    def test_bulk_reassignment_is_bounded_before_database_access(self):
        customers = [f"TEST Retailer {index}" for index in range(101)]
        with (
            patch.object(retailer_assignment, "require_role"),
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            patch.object(
                retailer_assignment, "_validate_salesperson"
            ) as validate_salesperson,
            patch.object(
                retailer_assignment,
                "_lock_customer",
                return_value=frappe._dict(territory="TEST Territory"),
            ) as lock_customer,
            patch.object(retailer_assignment, "_assert_salesperson_scope"),
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_assignment.bulk_reassign_retailers(
                customers,
                "test-new-salesperson@example.invalid",
                "TEST territory redistribution",
            )
        validate_salesperson.assert_not_called()
        lock_customer.assert_not_called()

    def test_legacy_bulk_reassignment_is_retired(self):
        with (
            patch.object(retailer_assignment, "require_role"),
            patch.object(retailer_assignment, "_lock_customer") as lock_customer,
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_assignment.bulk_reassign_retailers(
                ["TEST B", "TEST A", "TEST B"],
                "test-new@example.invalid",
                "TEST territory redistribution",
            )
        lock_customer.assert_not_called()

    def test_responsible_asm_must_share_the_retailer_territory(self):
        with (
            patch.object(
                retailer_assignment,
                "assigned_documents",
                return_value=["TEST North"],
            ),
            patch.object(frappe, "throw", side_effect=frappe.PermissionError),
            self.assertRaises(frappe.PermissionError),
        ):
            retailer_assignment._assert_salesperson_scope(
                "asm@example.invalid", "TEST South"
            )

    def test_duplicate_detection_normalizes_phone_email_and_gstin(self):
        application = frappe._dict(
            shop_name="TEST New Shop",
            phone="+91 98765-43210",
            email="TEST@EXAMPLE.INVALID",
            gstin="testgstin",
        )
        customer = frappe._dict(
            name="TEST Existing",
            customer_name="Different",
            mobile_no="9876543210",
            email_id="test@example.invalid",
            tax_id="TESTGSTIN",
        )
        with patch.object(frappe, "get_all", side_effect=[[customer], []]):
            matches = retailer_application.find_duplicates(application)
        self.assertEqual(set(matches[0]["reasons"]), {"phone", "email", "GSTIN"})

    def test_approval_requires_manager_role(self):
        with (
            patch.object(
                retailer_application, "require_role", side_effect=frappe.PermissionError
            ),
            patch.object(frappe, "get_doc") as get_doc,
        ):
            with self.assertRaises(frappe.PermissionError):
                retailer_application.approve("RET-APP-TEST")
            get_doc.assert_not_called()

    def test_salesperson_must_be_an_enabled_clothing_system_user(self):
        with (
            patch.object(
                frappe.db,
                "get_value",
                return_value=frappe._dict(enabled=0, user_type="System User"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_application._validate_salesperson("disabled@example.invalid")

    def test_rsm_approval_requires_supervision_of_asm(self):
        fake_app = frappe._dict(
            name="RET-APP-TEST-001",
            status="Pending",
            salesperson="asm@example.invalid",
            territory="TEST North",
            check_permission=MagicMock(),
        )
        with (
            patch.object(retailer_application, "require_role"),
            patch.object(retailer_application, "_lock_application", return_value=fake_app),
            patch.object(retailer_application, "is_clothing_admin", return_value=False),
            patch.object(retailer_application, "get_current_user", return_value="rsm@example.invalid"),
            patch.object(
                retailer_application,
                "assert_rsm_supervises_asm",
                side_effect=frappe.PermissionError("You do not supervise Area Sales Manager asm@example.invalid."),
            ),
        ):
            with self.assertRaisesRegex(frappe.PermissionError, "do not supervise"):
                retailer_application.approve("RET-APP-TEST-001")

    def test_rsm_rejection_requires_supervision_of_asm(self):
        fake_app = frappe._dict(
            name="RET-APP-TEST-002",
            status="Pending",
            salesperson="asm@example.invalid",
            territory="TEST North",
            check_permission=MagicMock(),
        )
        with (
            patch.object(retailer_application, "require_role"),
            patch.object(retailer_application, "_lock_application", return_value=fake_app),
            patch.object(retailer_application, "is_clothing_admin", return_value=False),
            patch.object(retailer_application, "get_current_user", return_value="rsm@example.invalid"),
            patch.object(
                retailer_application,
                "assert_rsm_supervises_asm",
                side_effect=frappe.PermissionError("You do not supervise Area Sales Manager asm@example.invalid."),
            ),
        ):
            with self.assertRaisesRegex(frappe.PermissionError, "do not supervise"):
                retailer_application.reject("RET-APP-TEST-002", "TEST Reason")

    def test_rsm_retailer_reassignment_restricted_to_supervised_asms(self):
        with (
            patch.object(retailer_assignment, "assigned_documents", return_value=["TEST North"]),
            patch.object(retailer_assignment, "_is_assignment_admin", return_value=False),
            patch.object(retailer_assignment, "get_current_user", return_value="rsm@example.invalid"),
            patch.object(retailer_assignment, "is_active_supervisor", return_value=False),
        ):
            with self.assertRaisesRegex(frappe.PermissionError, "only assign retailers to Area Sales Managers you supervise"):
                retailer_assignment._assert_salesperson_scope("unsupervised_asm@example.invalid", "TEST North")

        with (
            patch.object(retailer_assignment, "assigned_documents", return_value=["TEST North"]),
            patch.object(retailer_assignment, "_is_assignment_admin", return_value=False),
            patch.object(retailer_assignment, "get_current_user", return_value="rsm@example.invalid"),
            patch.object(retailer_assignment, "is_active_supervisor", return_value=True),
        ):
            # Supervising RSM can assign
            retailer_assignment._assert_salesperson_scope("supervised_asm@example.invalid", "TEST North")
