"""Root and login use Frappe's own launcher instead of a simulated Desk."""

import unittest
from unittest.mock import patch

import frappe

from clothing_erp import boot, hooks
from clothing_erp.www import clothing


class TestLauncher(unittest.TestCase):
    def test_guest_redirects_to_login_with_launcher_destination(self):
        with patch.object(clothing, "frappe") as framework:
            framework.session.user = "Guest"
            framework.Redirect = frappe.Redirect
            framework.local.flags = frappe._dict()
            with self.assertRaises(frappe.Redirect):
                clothing.get_context({})
            self.assertEqual(
                framework.local.flags.redirect_location,
                "/login?redirect-to=%2Fdesk%2Fdesktop",
            )

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

    def test_erpnext_tile_is_hidden_for_operational_clothing_users(self):
        restricted_roles = (
            "Clothing Salesperson",
            "Clothing Sales Manager",
            "Clothing Warehouse Operator",
            "Clothing Warehouse Manager",
        )
        for role in restricted_roles:
            with self.subTest(role=role):
                bootinfo = frappe._dict(
                    app_data=[
                        frappe._dict(
                            app_name="erpnext", on_apps_screen=True, dock=["Sales"]
                        ),
                        frappe._dict(
                            app_name="insights", on_apps_screen=True, dock=["Insights"]
                        ),
                        frappe._dict(
                            app_name="india_compliance",
                            on_apps_screen=True,
                            dock=["India Compliance"],
                        ),
                        frappe._dict(
                            app_name="clothing_erp",
                            on_apps_screen=True,
                            dock=["Clothing ERP"],
                        ),
                    ]
                )
                with (
                    patch.object(
                        boot, "get_current_user", return_value="user@example.com"
                    ),
                    patch.object(boot, "get_user_roles", return_value={role}),
                ):
                    boot.restrict_erpnext_app_visibility(bootinfo)
                self.assertFalse(bootinfo.app_data[0].on_apps_screen)
                self.assertEqual(bootinfo.app_data[0].dock, [])
                self.assertFalse(bootinfo.app_data[1].on_apps_screen)
                self.assertEqual(bootinfo.app_data[1].dock, [])
                self.assertFalse(bootinfo.app_data[2].on_apps_screen)
                self.assertEqual(bootinfo.app_data[2].dock, [])
                self.assertTrue(bootinfo.app_data[3].on_apps_screen)

    def test_erpnext_tile_remains_for_clothing_business_admin(self):
        bootinfo = frappe._dict(
            app_data=[
                frappe._dict(app_name="erpnext", on_apps_screen=True, dock=["Sales"]),
                frappe._dict(app_name="insights", on_apps_screen=True, dock=["Insights"]),
                frappe._dict(
                    app_name="india_compliance",
                    on_apps_screen=True,
                    dock=["India Compliance"],
                ),
                frappe._dict(
                    app_name="clothing_erp",
                    on_apps_screen=True,
                    dock=["Clothing ERP"],
                ),
            ]
        )
        with (
            patch.object(boot, "get_current_user", return_value="admin@example.com"),
            patch.object(
                boot,
                "get_user_roles",
                return_value={"Clothing Business Administrator"},
            ),
        ):
            boot.restrict_erpnext_app_visibility(bootinfo)
        self.assertTrue(bootinfo.app_data[0].on_apps_screen)
        self.assertTrue(bootinfo.app_data[1].on_apps_screen)
        self.assertTrue(bootinfo.app_data[2].on_apps_screen)
        self.assertTrue(bootinfo.app_data[3].on_apps_screen)

    def test_insights_tile_hidden_from_non_admin_insights_user(self):
        bootinfo = frappe._dict(
            app_data=[
                frappe._dict(app_name="insights", on_apps_screen=True, dock=["Insights"]),
                frappe._dict(app_name="frappe", on_apps_screen=True, dock=["Desk"]),
            ]
        )
        with (
            patch.object(boot, "get_current_user", return_value="analyst@example.com"),
            patch.object(
                boot,
                "get_user_roles",
                return_value={"Insights User"},
            ),
        ):
            boot.restrict_erpnext_app_visibility(bootinfo)
        self.assertFalse(bootinfo.app_data[0].on_apps_screen)
        self.assertEqual(bootinfo.app_data[0].dock, [])
        self.assertEqual(bootinfo.app_data[0].app_route, "")
        self.assertTrue(bootinfo.app_data[1].on_apps_screen)

    def test_insights_tile_remains_for_system_manager_and_insights_admin(self):
        for role in ("System Manager", "Insights Admin"):
            with self.subTest(role=role):
                bootinfo = frappe._dict(
                    app_data=[
                        frappe._dict(app_name="insights", on_apps_screen=True, dock=["Insights"]),
                    ]
                )
                with (
                    patch.object(boot, "get_current_user", return_value="admin@example.com"),
                    patch.object(boot, "get_user_roles", return_value={role}),
                ):
                    boot.restrict_erpnext_app_visibility(bootinfo)
                self.assertTrue(bootinfo.app_data[0].on_apps_screen)

