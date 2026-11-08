import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from clothing_erp import retailer_assignment
from clothing_erp.clothing_erp.doctype.retailer_application import retailer_application


class TestRetailerWorkflow(unittest.TestCase):
    def test_salesperson_application_identity_and_master_defaults_are_forced(self):
        application = retailer_application.RetailerApplication(
            {
                "doctype": "Retailer Application",
                "shop_name": " TEST Boutique ",
                "contact_person": " TEST Person ",
                "phone": "+91 90000 11111",
                "salesperson": "other@example.invalid",
                "territory": "Other Territory",
                "customer_group": "Other Group",
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

    def test_reassignment_controls_are_directly_visible(self):
        app_root = Path(__file__).parents[1]
        form_script = (app_root / "public/js/customer_assignment.js").read_text()
        list_script = (app_root / "public/js/customer_list.js").read_text()
        self.assertIn('frm.add_custom_button(__("Reassign Salesperson")', form_script)
        self.assertNotIn('}, __("Clothing ERP"));', form_script)
        self.assertIn('add_inner_button(__("Reassign Salesperson")', list_script)
        self.assertNotIn("add_actions_menu_item", list_script)

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
