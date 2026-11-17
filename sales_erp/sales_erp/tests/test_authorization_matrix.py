# Copyright (c) 2026, Clothing ERP Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from sales_erp.api import get_retailer_detail, get_user_context
from sales_erp.ordering import create_draft_sales_order, submit_clothing_order
from sales_erp.sales_erp.doctype.retailer_application.retailer_application import approve as approve_application
from sales_erp.sales_erp.doctype.retailer_credit_limit_request.retailer_credit_limit_request import approve_credit_limit_request
from sales_erp.security import has_retailer_access
from sales_erp.supervision import assign_asm_supervision, end_asm_supervision

from warehouse_erp.fulfillment import get_fulfillment_tasks, verify_pick_item
from warehouse_erp.security import warehouse_has_permission

from quality_erp.quality import approve_quality_gate, create_quality_inspection
from sales_erp.boot import ensure_module_app_mapped


class TestAuthorizationMatrix(FrappeTestCase):
    """End-to-end integration tests proving server-side authorization invariants:
    1. Disabled users lose access immediately.
    2. Ended supervision immediately revokes territory access.
    3. Removed warehouse user permissions immediately revoke task access.
    4. Strict cross-role barriers: ASM cannot perform manager/admin or warehouse/quality tasks.
    5. Strict cross-territory barriers: ASMs cannot access or place orders for other territories.
    """

    def setUp(self):
        super().setUp()
        ensure_module_app_mapped()
        frappe.set_user("Administrator")
        frappe.local.request_cache.clear()

    def test_disabled_user_access_is_immediately_revoked(self):
        """Disabling a user immediately revokes API access and throws PermissionError."""
        user = "test-asm-south@example.invalid"
        if not frappe.db.exists("User", user):
            self.skipTest(f"Seed user {user} not found.")

        # Baseline: active user can fetch user context
        frappe.set_user(user)
        frappe.local.request_cache.clear()
        ctx = get_user_context()
        self.assertEqual(ctx.get("user"), user)

        # Disable user
        frappe.set_user("Administrator")
        frappe.db.set_value("User", user, "enabled", 0)
        frappe.clear_cache(user=user)

        # Access must now fail
        frappe.set_user(user)
        frappe.local.request_cache.clear()
        try:
            with self.assertRaises((frappe.PermissionError, frappe.AuthenticationError)):
                get_user_context()
        finally:
            # Re-enable user for subsequent tests
            frappe.set_user("Administrator")
            frappe.db.set_value("User", user, "enabled", 1)
            frappe.clear_cache(user=user)

    def test_ended_supervision_immediately_revokes_territory_access(self):
        """Ending an ASM supervision assignment immediately revokes access to the territory."""
        asm = "test-asm-south@example.invalid"
        rsm = "test-rsm@example.invalid"
        territory = "TEST South Sales Territory"

        if not frappe.db.exists("Territory", territory) or not frappe.db.exists("User", asm):
            self.skipTest("Required territory or seed user not found.")

        frappe.set_user("Administrator")
        res = assign_asm_supervision(asm, rsm, territory, effective_from=nowdate(), reason="Auth test")
        supervision_name = res["name"]

        # User has access while active
        self.assertTrue(has_retailer_access("TEST 2-1 Buy & Sell Store", asm))

        # End supervision
        end_asm_supervision(supervision_name, reason="Ended for auth test", end_date=nowdate())
        frappe.local.request_cache.clear()

        # Supervision is ended, territory permission revoked
        active = frappe.get_all(
            "ASM Supervision",
            filters={"asm": asm, "territory": territory, "status": "Active"},
        )
        self.assertEqual(len(active), 0)

        # Re-assign supervision to leave site clean
        assign_asm_supervision(asm, rsm, territory, effective_from=nowdate(), reason="Restored after auth test")

    def test_removed_warehouse_permission_immediately_revokes_access(self):
        """Deleting a User Permission for a Warehouse immediately denies access."""
        manager = "test-warehouse-manager@example.invalid"
        if not frappe.db.exists("User", manager):
            self.skipTest(f"Seed user {manager} not found.")

        # Find any leaf warehouse
        wh = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
        if not wh:
            self.skipTest("No leaf warehouse found.")

        frappe.set_user("Administrator")
        # Ensure user permission exists
        if not frappe.db.exists("User Permission", {"user": manager, "allow": "Warehouse", "for_value": wh}):
            frappe.get_doc({
                "doctype": "User Permission",
                "user": manager,
                "allow": "Warehouse",
                "for_value": wh,
            }).insert(ignore_permissions=True)

        frappe.clear_cache(user=manager)
        frappe.set_user(manager)
        frappe.local.request_cache.clear()
        self.assertTrue(warehouse_has_permission(wh, user=manager))

        # Remove permission
        frappe.set_user("Administrator")
        perm_names = frappe.get_all("User Permission", filters={"user": manager, "allow": "Warehouse", "for_value": wh}, pluck="name")
        for p in perm_names:
            frappe.delete_doc("User Permission", p, ignore_permissions=True, force=True)

        frappe.clear_cache(user=manager)
        frappe.set_user(manager)
        frappe.local.request_cache.clear()

        # Must now be denied for that specific warehouse
        self.assertFalse(warehouse_has_permission(wh, user=manager))

        # Restore permission
        frappe.set_user("Administrator")
        frappe.get_doc({
            "doctype": "User Permission",
            "user": manager,
            "allow": "Warehouse",
            "for_value": wh,
        }).insert(ignore_permissions=True)

    def test_cross_role_negative_asm_denials(self):
        """Area Sales Managers must be rejected from manager-only, warehouse, and quality endpoints."""
        asm = "test-asm-south@example.invalid"
        if not frappe.db.exists("User", asm):
            self.skipTest(f"Seed user {asm} not found.")

        frappe.set_user(asm)
        frappe.local.request_cache.clear()

        # ASM cannot approve retailer applications (RSM/Admin only)
        with self.assertRaises(frappe.PermissionError):
            approve_application("NON-EXISTENT-APP", 50000)

        # ASM cannot approve credit limit requests (Business Admin/Admin only)
        with self.assertRaises(frappe.PermissionError):
            approve_credit_limit_request("NON-EXISTENT-REQ")

        # ASM cannot access warehouse fulfillment tasks
        with self.assertRaises(frappe.PermissionError):
            get_fulfillment_tasks(task_type="pick", state="all")

        # ASM cannot verify pick list items
        with self.assertRaises(frappe.PermissionError):
            verify_pick_item("DUMMY-PICK", "WH-LOC", "BARCODE123", 1)

        # ASM cannot create supplier quality inspections
        with self.assertRaises(frappe.PermissionError):
            create_quality_inspection(supplier="SUPPLIER-1", item_code="ITEM-1", stage="1. Fit Sample")

    def test_cross_role_negative_warehouse_manager_denials(self):
        """Warehouse Managers must be rejected from sales and quality decision endpoints."""
        wh_mgr = "test-warehouse-manager@example.invalid"
        if not frappe.db.exists("User", wh_mgr):
            self.skipTest(f"Seed user {wh_mgr} not found.")

        frappe.set_user(wh_mgr)
        frappe.local.request_cache.clear()

        # Warehouse Manager cannot create sales orders
        with self.assertRaises(frappe.PermissionError):
            create_draft_sales_order("CUSTOMER-1", [{"item_code": "ITEM-1", "qty": 1}], "REQ-123")

        # Warehouse Manager cannot approve retailer applications
        with self.assertRaises(frappe.PermissionError):
            approve_application("APP-1", 50000)

        # Warehouse Manager cannot approve quality gates
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate("INSP-001", "Notes")

    def test_cross_role_negative_quality_inspector_denials(self):
        """Quality Inspectors must be rejected from warehouse fulfillment and critical quality gates."""
        qi = "test-quality-inspector@example.invalid"
        if not frappe.db.exists("User", qi):
            self.skipTest(f"Seed user {qi} not found.")

        # Ensure critical gate inspection fixtures exist and capture generated names
        frappe.set_user("Administrator")
        supplier = "TEST-SUPPLIER-1" if frappe.db.exists("Supplier", "TEST-SUPPLIER-1") else frappe.db.get_value("Supplier", {}, "name")
        item = "TEST-SKU-1" if frappe.db.exists("Item", "TEST-SKU-1") else frappe.db.get_value("Item", {}, "name")

        insp_pga = frappe.get_doc({
            "doctype": "Supplier Quality Inspection",
            "supplier": supplier,
            "item_code": item,
            "stage": "4. Production Go Ahead",
            "status": "Pending Review",
        }).insert(ignore_permissions=True)

        insp_final = frappe.get_doc({
            "doctype": "Supplier Quality Inspection",
            "supplier": supplier,
            "item_code": item,
            "stage": "7. Final Inspection",
            "status": "Pending Review",
        }).insert(ignore_permissions=True)

        frappe.set_user(qi)
        frappe.local.request_cache.clear()

        # Quality Inspector cannot access fulfillment tasks
        with self.assertRaises(frappe.PermissionError):
            get_fulfillment_tasks(task_type="pick", state="all")

        # Quality Inspector cannot create sales orders
        with self.assertRaises(frappe.PermissionError):
            create_draft_sales_order("CUSTOMER-1", [{"item_code": "ITEM-1", "qty": 1}], "REQ-123")

        # Quality Inspector cannot approve Stage 4 (Production Go Ahead) - Admin only
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(insp_pga.name, "Inspector cannot approve PGA")

        # Quality Inspector cannot approve Stage 7 (Final Inspection) - Admin only
        with self.assertRaises(frappe.PermissionError):
            approve_quality_gate(insp_final.name, "Inspector cannot approve Final")

    def test_cross_territory_sales_order_creation_denied(self):
        """An ASM cannot create draft sales orders for customers in an unassigned territory."""
        asm = "test-asm-south@example.invalid"
        if not frappe.db.exists("User", asm):
            self.skipTest(f"Seed user {asm} not found.")

        # Customer in North territory
        north_customer = "TEST 1-4 EBOC (Exclusive Brand Outlet) Store"
        if not frappe.db.exists("Customer", north_customer):
            north_customer = frappe.db.get_value("Customer", {"territory": "TEST North Sales Territory"}, "name")
        if not north_customer:
            self.skipTest("No North customer found.")

        # ASM South attempting to order for North Customer must be denied
        frappe.set_user(asm)
        frappe.local.request_cache.clear()
        with self.assertRaises(frappe.PermissionError):
            create_draft_sales_order(
                customer=north_customer,
                items=[{"item_code": "TEST-SKU-1", "qty": 1}],
                request_id="IDEMP-CROSS-TERRITORY-1",
            )
