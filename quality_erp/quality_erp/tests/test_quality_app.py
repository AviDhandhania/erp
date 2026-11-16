"""Unit and integration tests for Quality ERP."""

import unittest
import frappe
from frappe.tests.utils import FrappeTestCase

from quality_erp.boot import restrict_quality_app_visibility
from quality_erp.quality import (
    approve_quality_gate,
    create_quality_inspection,
    record_return_quarantine,
    reject_quality_gate,
)
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)
from quality_erp.seed import (
    SEED_QUALITY_INSPECTOR,
    SEED_QUALITY_MANAGER,
    seed_quality_data,
)


class TestQualityERP(FrappeTestCase):
    def setUp(self):
        super().setUp()
        from collections import defaultdict
        frappe.local.request_cache = defaultdict(dict)
        frappe.set_user("Administrator")
        seed_quality_data()
        self.inspector = SEED_QUALITY_INSPECTOR
        self.manager = SEED_QUALITY_MANAGER
        self.supplier = "TEST Fabric & Stitch Mills"

        if not frappe.db.exists("Supplier", self.supplier):
            frappe.get_doc(
                {
                    "doctype": "Supplier",
                    "supplier_name": self.supplier,
                    "supplier_group": "All Supplier Groups",
                }
            ).insert(ignore_permissions=True)

        if not frappe.db.exists("Customer", "TEST Quality Customer"):
            frappe.get_doc(
                {
                    "doctype": "Customer",
                    "customer_name": "TEST Quality Customer",
                    "customer_group": "Commercial",
                    "territory": "All Territories",
                }
            ).insert(ignore_permissions=True)

    def test_quality_user_app_isolation(self):
        """Quality inspector must only see Quality ERP on the apps screen."""
        frappe.set_user(self.inspector)
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                    {"app_name": "insights", "on_apps_screen": True},
                    {"app_name": "india_compliance", "on_apps_screen": True},
                ]
            }
        )
        restrict_quality_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertEqual(visible, ["quality_erp"])

    def test_admin_sees_all_apps(self):
        """Administrator must retain access to all apps."""
        frappe.set_user("Administrator")
        bootinfo = frappe._dict(
            {
                "app_data": [
                    {"app_name": "quality_erp", "on_apps_screen": True},
                    {"app_name": "sales_erp", "on_apps_screen": True},
                    {"app_name": "warehouse_erp", "on_apps_screen": True},
                    {"app_name": "erpnext", "on_apps_screen": True},
                ]
            }
        )
        restrict_quality_app_visibility(bootinfo)

        visible = [a["app_name"] for a in bootinfo.app_data if a.get("on_apps_screen")]
        self.assertIn("quality_erp", visible)
        self.assertIn("sales_erp", visible)
        self.assertIn("warehouse_erp", visible)
        self.assertIn("erpnext", visible)

    def test_quality_inspection_creation_and_rejection(self):
        """Inspector can create quality inspections and reject with reason."""
        frappe.set_user(self.inspector)
        doc = create_quality_inspection(
            supplier=self.supplier,
            item_code="TEST-CLASSIC-TEE-BLK",
            stage="1. First Submission",
            spec_notes="Chest 38cm, Length 68cm",
        )
        self.assertEqual(doc["status"], "Pending Review")

        # Rejection requires reason
        with self.assertRaises(frappe.ValidationError):
            reject_quality_gate(doc["name"], reason="")

        rejected = reject_quality_gate(doc["name"], reason="Sleeve length out of spec")
        self.assertEqual(rejected["status"], "Rejected")
        self.assertIn("Sleeve length out of spec", rejected["comments"])

    def test_critical_gates_require_administrator(self):
        """Critical gates (Production Go Ahead & Final Inspection) require Administrator."""
        frappe.set_user(self.inspector)
        doc = create_quality_inspection(
            supplier=self.supplier,
            item_code="TEST-CLASSIC-TEE-BLK",
            stage="4. Production Go Ahead",
            spec_notes="Pre-production approval request",
        )

        # Inspector cannot approve critical gate
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(doc["name"])

        # Manager also cannot approve critical release gate
        frappe.set_user(self.manager)
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(doc["name"])

        # Administrator can approve critical gate
        frappe.set_user("Administrator")
        approved = approve_quality_gate(doc["name"], notes="Administrator sign-off approved")
        self.assertEqual(approved["status"], "Approved")
        self.assertEqual(approved["approved_by"], "Administrator")

    def test_final_inspection_critical_gate(self):
        """Final Inspection gate 7 also strictly requires Administrator."""
        frappe.set_user(self.inspector)
        doc = create_quality_inspection(
            supplier=self.supplier,
            item_code="TEST-CLASSIC-TEE-BLK",
            stage="7. Final Inspection",
            spec_notes="Final bulk inspection 100 units",
        )

        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(doc["name"])

        frappe.set_user("Administrator")
        approved = approve_quality_gate(doc["name"], notes="Final release approved")
        self.assertEqual(approved["status"], "Approved")

    def test_return_quarantine_intake(self):
        """Inspector can intake goods into return quarantine."""
        frappe.set_user(self.inspector)
        doc = record_return_quarantine(
            retailer="TEST Quality Customer",
            delivery_note=None,
            item_code="TEST-CLASSIC-TEE-BLK",
            quantity=5,
            return_reason="Defective Stitching",
        )
        self.assertEqual(doc["inspection_status"], "Quarantined")
        self.assertEqual(doc["quantity"], 5.0)
        self.assertEqual(doc["inspected_by"], self.inspector)

    def test_quality_runtime_scoping(self):
        """Quality users only see quality_erp and Quality ERP workspace."""
        from frappe.apps import get_apps
        from frappe.desk.desktop import get_workspaces

        for user in [self.inspector, self.manager]:
            frappe.set_user(user)
            frappe.local.request_cache.clear()
            apps = [a["name"] for a in get_apps()]
            self.assertEqual(apps, ["quality_erp"])

            ws_pages = [w["name"] for w in get_workspaces()["pages"]]
            self.assertEqual(ws_pages, ["Quality ERP"])

    def test_cross_app_quality_access_denied(self):
        """Users outside quality roles cannot create quality inspections or record quarantine."""
        for user in ["test-asm-south@example.invalid", "test-warehouse-operator@example.invalid"]:
            frappe.set_user(user)
            frappe.local.request_cache.clear()
            with self.assertRaises(frappe.PermissionError):
                create_quality_inspection(
                    supplier=self.supplier,
                    item_code="TEST-CLASSIC-TEE-BLK",
                    stage="1. First Submission",
                )

            with self.assertRaises(frappe.PermissionError):
                record_return_quarantine(
                    retailer="TEST Quality Customer",
                    delivery_note=None,
                    item_code="TEST-CLASSIC-TEE-BLK",
                    quantity=1,
                    return_reason="Defective Stitching",
                )
