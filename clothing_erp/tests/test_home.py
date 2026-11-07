"""Root and login use Frappe's own launcher instead of a simulated Desk."""
import unittest
from unittest.mock import patch
import frappe
from clothing_erp.www import clothing
from clothing_erp import hooks


class TestLauncher(unittest.TestCase):
    def test_guest_redirects_to_login_with_launcher_destination(self):
        with patch.object(clothing, "frappe") as framework:
            framework.session.user = "Guest"
            framework.Redirect = frappe.Redirect
            framework.local.flags = frappe._dict()
            with self.assertRaises(frappe.Redirect):
                clothing.get_context({})
            self.assertEqual(framework.local.flags.redirect_location, "/login?redirect-to=%2Fdesk%2Fdesktop")

    def test_authenticated_visitor_opens_native_apps_screen(self):
        with patch.object(clothing, "frappe") as framework:
            framework.session.user = "test@example.invalid"
            framework.Redirect = frappe.Redirect
            framework.local.flags = frappe._dict()
            with self.assertRaises(frappe.Redirect):
                clothing.get_context({})
            self.assertEqual(framework.local.flags.redirect_location, "/desk/desktop")

    def test_app_registers_real_workspace_and_logo(self):
        app = hooks.add_to_apps_screen[0]
        self.assertEqual(app["route"], "/desk/clothing-erp")
        self.assertEqual(app["title"], "Clothing ERP")
        self.assertEqual(app["has_permission"], "clothing_erp.security.has_app_access")
        self.assertTrue(app["logo"].endswith("clothing_erp_logo.svg"))
