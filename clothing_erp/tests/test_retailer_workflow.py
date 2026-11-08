import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from clothing_erp import hooks, retailer_assignment, retailer_defaults
from clothing_erp.clothing_erp.doctype.retailer_application import retailer_application


class TestRetailerWorkflow(unittest.TestCase):
    def test_get_retailer_defaults_is_whitelisted(self):
        # Whitelist verification (Added by Gemini)
        self.assertTrue(
            getattr(retailer_defaults.get_retailer_defaults, "_whitelisted", False)
            or "clothing_erp.retailer_defaults.get_retailer_defaults" in frappe.whitelisted
            or hasattr(retailer_defaults.get_retailer_defaults, "__wrapped__")
        )

    def test_salesperson_application_identity_and_master_defaults_are_forced(self):
        application = retailer_application.RetailerApplication(
            {
                "doctype": "Retailer Application",
                "shop_name": " TEST Boutique ",
                "contact_person": " TEST Person ",
                "phone": "+91 90000 11111",
                "salesperson": "other@example.invalid",
            }
        )
        defaults = frappe._dict(
            territory="Default Territory", customer_group="Default Group"
        )
        with (
            patch.object(
                retailer_application,
                "get_user_roles",
                return_value={"Clothing Salesperson"},
            ),
            patch.object(retailer_application, "is_sales_manager", return_value=False),
            patch.object(
                retailer_application,
                "get_current_user",
                return_value="sales@example.com",
            ),
            patch.object(
                retailer_application,
                "_salesperson_application_defaults",
                return_value=defaults,
            ),
            patch.object(
                retailer_application.RetailerApplication,
                "is_new",
                return_value=True,
            ),
            patch.object(retailer_application, "_validate_salesperson"),
            patch.object(retailer_application, "find_duplicates", return_value=[]),
        ):
            application.validate()
        self.assertEqual(application.salesperson, "sales@example.com")
        self.assertEqual(application.territory, "Default Territory")
        self.assertEqual(application.customer_group, "Default Group")

    def test_salesperson_application_preserves_valid_territory_and_customer_group(self):
        application = retailer_application.RetailerApplication(
            {
                "doctype": "Retailer Application",
                "shop_name": " TEST Boutique ",
                "contact_person": " TEST Person ",
                "phone": "+91 90000 11111",
                "salesperson": "sales@example.com",
                "territory": "Valid Territory",
                "customer_group": "Valid Customer Group",
            }
        )
        with (
            patch.object(
                retailer_application,
                "get_user_roles",
                return_value={"Clothing Salesperson"},
            ),
            patch.object(retailer_application, "is_sales_manager", return_value=False),
            patch.object(
                retailer_application,
                "get_current_user",
                return_value="sales@example.com",
            ),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(
                retailer_application.RetailerApplication,
                "is_new",
                return_value=True,
            ),
            patch.object(retailer_application, "_validate_salesperson"),
            patch.object(retailer_application, "find_duplicates", return_value=[]),
        ):
            application.validate()
        self.assertEqual(application.salesperson, "sales@example.com")
        self.assertEqual(application.territory, "Valid Territory")
        self.assertEqual(application.customer_group, "Valid Customer Group")

    def test_reassignment_controls_live_only_in_clothing_erp(self):
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
                "Clothing Sales Manager",
                "Clothing Business Administrator",
                "System Manager",
            },
        )
        self.assertIn("get_reassignment_directory", script)
        self.assertIn("reassign_retailer", script)

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

    def test_manager_without_territory_gets_no_reassignment_directory(self):
        with (
            patch.object(retailer_assignment, "require_role"),
            patch.object(retailer_assignment, "_manager_territories", return_value=[]),
            patch.object(retailer_assignment, "_active_salespeople", return_value=[]),
            patch.object(frappe, "get_list") as get_list,
        ):
            result = retailer_assignment.get_reassignment_directory()
        self.assertTrue(result["scope_required"])
        self.assertEqual(result["retailers"], [])
        get_list.assert_not_called()

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
            patch.object(retailer_assignment, "_lock_customer") as lock_customer,
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_assignment.bulk_reassign_retailers(
                customers,
                "test-new-salesperson@example.invalid",
                "TEST territory redistribution",
            )
        validate_salesperson.assert_not_called()
        lock_customer.assert_not_called()

    def test_bulk_reassignment_locks_sorted_unique_customers_before_changes(self):
        assignments = {
            "TEST A": frappe._dict(name="UP-A", user="test-old@example.invalid"),
            "TEST B": None,
        }
        with (
            patch.object(retailer_assignment, "require_role"),
            patch.object(retailer_assignment, "_validate_salesperson"),
            patch.object(retailer_assignment, "_lock_customer") as lock_customer,
            patch.object(
                retailer_assignment,
                "_single_assignment",
                side_effect=lambda customer: assignments[customer],
            ),
            patch.object(
                retailer_assignment,
                "_replace_assignment",
                side_effect=lambda customer, new, reason, assignment: {
                    "customer": customer,
                    "unchanged": False,
                },
            ) as replace_assignment,
        ):
            result = retailer_assignment.bulk_reassign_retailers(
                ["TEST B", "TEST A", "TEST B"],
                "test-new@example.invalid",
                "TEST territory redistribution",
            )
        self.assertEqual(
            [call.args[0] for call in lock_customer.call_args_list],
            ["TEST A", "TEST B"],
        )
        self.assertEqual(
            [call.args[0] for call in replace_assignment.call_args_list],
            ["TEST A", "TEST B"],
        )
        self.assertEqual(result["changed"], 2)

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
