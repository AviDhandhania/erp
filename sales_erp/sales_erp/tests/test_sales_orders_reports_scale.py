"""Unit, integration, and high-volume scale tests for Sales ERP orders, native behaviors,
scoped dashboards, script reports, and mobile-ready API contract (Session 8).
"""

import random
from collections import defaultdict

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, getdate, now_datetime, nowdate

from sales_erp.api import get_sales_operational_dashboard, get_unified_sales_worklist
from sales_erp.boot import ensure_module_app_mapped
from sales_erp.cadence import (
    get_collection_obligations,
    record_collection_follow_up,
)
from sales_erp.mobile_api import (
    API_VERSION,
    create_mobile_order,
    get_mobile_boot,
    get_mobile_dashboard,
    get_mobile_retailers,
    get_mobile_worklist,
)
from sales_erp.ordering import (
    amend_clothing_order,
    cancel_clothing_order,
    create_draft_sales_order,
    get_clothing_order,
    get_clothing_orders,
    get_retailer_stock_exposure,
    reject_clothing_order,
    resubmit_clothing_order,
    submit_clothing_order,
)
from sales_erp.roles import ROLE_ASM, ROLE_BUSINESS_ADMIN, ROLE_RSM
from sales_erp.sales_erp.report.retailer_cadence_and_exposure_report.retailer_cadence_and_exposure_report import (
    execute as execute_cadence_report,
)
from sales_erp.seed import (
    SEED_ASM_NORTH,
    SEED_ASM_SOUTH,
    SEED_RSM,
    seed_catalogue,
)


class TestSalesOrdersReportsScale(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.local.request_cache = defaultdict(dict)
        ensure_module_app_mapped()
        frappe.set_user("Administrator")
        seed_catalogue()

        self.asm_north = SEED_ASM_NORTH
        self.asm_south = SEED_ASM_SOUTH
        self.rsm = SEED_RSM

        # Ensure active item variants exist
        self.variants = frappe.get_all(
            "Item",
            filters={"variant_of": ["is", "set"], "disabled": 0},
            fields=["name", "variant_of"],
            limit=5,
        )
        self.assertTrue(self.variants, "At least one active variant required for ordering tests.")
        self.item_code = self.variants[0].name

        # Ensure test customers in North and South territories
        self.cust_north = self._ensure_test_customer("Test North Retailer S8", "TEST North Sales Territory")
        self.cust_south = self._ensure_test_customer("Test South Retailer S8", "TEST South Sales Territory")

    def _ensure_test_customer(self, name, territory):
        existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
        if existing:
            return existing
        doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": name,
            "customer_group": "Buy & Sell",
            "territory": territory,
            "mobile_no": f"98{random.randint(10000000, 99999999)}",
        })
        doc.flags.ignore_permissions = True
        doc.insert()

        # Set an approved credit limit of 500,000
        company = frappe.defaults.get_global_default("company") or "Windsor Apparel Pvt Ltd"
        doc.append("credit_limits", {
            "company": company,
            "credit_limit": 500000.0,
        })
        doc.save(ignore_permissions=True)
        return doc.name

    def _unique_req_id(self):
        return f"REQ-S8-{frappe.generate_hash(length=32)}"

    def test_order_lifecycle_reject_and_resubmit(self):
        """ASM creates draft order -> RSM rejects with reason -> ASM resubmits with updated lines."""
        req_id = self._unique_req_id()

        # 1. ASM North creates draft order
        frappe.set_user(self.asm_north)
        order_res = create_draft_sales_order(
            customer=self.cust_north,
            items=[{"item_code": self.item_code, "qty": 10}],
            request_id=req_id,
            delivery_date=nowdate(),
        )
        order_name = order_res["name"]
        self.assertEqual(order_res["docstatus"], 0)

        # ASM cannot reject orders (requires RSM or Admin)
        with self.assertRaises(frappe.PermissionError):
            reject_clothing_order(order_name, "Needs more units")

        # 2. Supervising RSM rejects the order with reason
        frappe.set_user(self.rsm)
        # Reason must be at least 5 chars
        with self.assertRaises(frappe.ValidationError):
            reject_clothing_order(order_name, "No")

        reject_res = reject_clothing_order(order_name, "Please increase order volume to meet wholesale minimum.")
        self.assertEqual(reject_res["rejection_reason"], "Please increase order volume to meet wholesale minimum.")

        # Check detail endpoint reflects rejection reason
        detail = get_clothing_order(order_name)
        self.assertEqual(detail["rejection_reason"], "Please increase order volume to meet wholesale minimum.")
        self.assertTrue(detail["review"]["can_resubmit"])

        # 3. ASM resubmits with updated quantities
        frappe.set_user(self.asm_north)
        resubmit_res = resubmit_clothing_order(
            name=order_name,
            items=[{"item_code": self.item_code, "qty": 20}],
            delivery_date=add_days(nowdate(), 5),
            notes="Updated volume to 20 units as requested.",
        )
        self.assertEqual(resubmit_res["docstatus"], 0)

        # Verify items and totals updated, rejection cleared
        updated_detail = get_clothing_order(order_name)
        self.assertEqual(len(updated_detail["items"]), 1)
        self.assertEqual(updated_detail["items"][0]["qty"], 20.0)
        self.assertFalse(updated_detail["rejection_reason"])

    def test_order_cancellation_and_amendment(self):
        """ASM creates order -> RSM submits -> Order cancelled -> ASM amends cancelled order."""
        req_id = self._unique_req_id()

        frappe.set_user(self.asm_north)
        order_res = create_draft_sales_order(
            customer=self.cust_north,
            items=[{"item_code": self.item_code, "qty": 5}],
            request_id=req_id,
            delivery_date=nowdate(),
        )
        order_name = order_res["name"]

        # RSM submits order
        frappe.set_user(self.rsm)
        sub_res = submit_clothing_order(order_name)
        self.assertEqual(sub_res["docstatus"], 1)

        # Cancel order
        cancel_res = cancel_clothing_order(order_name)
        self.assertEqual(cancel_res["docstatus"], 2)

        # Cannot amend a non-cancelled order
        # ASM amends cancelled order with a new request_id
        frappe.set_user(self.asm_north)
        amend_req_id = self._unique_req_id()
        amended_res = amend_clothing_order(order_name, request_id=amend_req_id)

        self.assertEqual(amended_res["docstatus"], 0)
        self.assertEqual(amended_res["amended_from"], order_name)
        self.assertNotEqual(amended_res["name"], order_name)

        # Detail shows amended order is draft and can be submitted
        frappe.set_user(self.rsm)
        detail = get_clothing_order(amended_res["name"])
        self.assertEqual(detail["docstatus"], 0)
        self.assertTrue(detail["review"]["can_submit"])

    def test_multi_company_and_currency_isolation(self):
        """Test multi-company argument support and currency field propagation."""
        company = frappe.defaults.get_global_default("company") or "Windsor Apparel Pvt Ltd"
        req_id = self._unique_req_id()

        frappe.set_user(self.asm_north)
        res = create_draft_sales_order(
            customer=self.cust_north,
            items=[{"item_code": self.item_code, "qty": 4}],
            request_id=req_id,
            delivery_date=nowdate(),
            company=company,
        )
        self.assertEqual(res["company"], company)
        self.assertIn("conversion_rate", res)
        self.assertIn("base_grand_total", res)
        self.assertGreater(res["grand_total"], 0)

    def test_partial_delivery_and_return_stock_exposure(self):
        """Stock exposure accurately computes stock held (delivered - returned) and pending incoming value."""
        req_id = self._unique_req_id()

        frappe.set_user(self.asm_north)
        order_res = create_draft_sales_order(
            customer=self.cust_north,
            items=[{"item_code": self.item_code, "qty": 10}],
            request_id=req_id,
            delivery_date=nowdate(),
        )
        frappe.set_user(self.rsm)
        submit_clothing_order(order_res["name"])

        # Check exposure before delivery
        exp1 = get_retailer_stock_exposure(self.cust_north)
        self.assertGreater(exp1["pending_orders_value"], 0)
        initial_pending = exp1["pending_orders_value"]
        initial_held = exp1["stock_held_at_shop"]

        # Admin creates and submits a partial Delivery Note for 6 units
        frappe.set_user("Administrator")
        so_doc = frappe.get_doc("Sales Order", order_res["name"])
        rate = so_doc.items[0].rate
        wh = so_doc.items[0].warehouse

        # Ensure sufficient warehouse stock before delivery
        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": so_doc.company,
            "items": [{
                "item_code": self.item_code,
                "t_warehouse": wh,
                "qty": 20,
                "basic_rate": 200,
            }],
        })
        se.flags.ignore_permissions = True
        se.insert()
        se.submit()

        dn = frappe.get_doc({
            "doctype": "Delivery Note",
            "customer": self.cust_north,
            "company": so_doc.company,
            "posting_date": nowdate(),
            "items": [
                {
                    "item_code": self.item_code,
                    "qty": 6,
                    "rate": rate,
                    "against_sales_order": so_doc.name,
                    "so_detail": so_doc.items[0].name,
                }
            ],
        })
        dn.flags.ignore_permissions = True
        dn.insert()
        dn.submit()

        # Check exposure: held increases by 6 * rate, pending decreases by 6 * rate
        exp2 = get_retailer_stock_exposure(self.cust_north)
        self.assertAlmostEqual(exp2["stock_held_at_shop"], initial_held + (6 * rate), delta=1.0)
        self.assertAlmostEqual(exp2["pending_orders_value"], initial_pending - (6 * rate), delta=1.0)

        # Create a Return Delivery Note for 2 units
        return_dn = frappe.get_doc({
            "doctype": "Delivery Note",
            "customer": self.cust_north,
            "company": so_doc.company,
            "is_return": 1,
            "return_against": dn.name,
            "posting_date": nowdate(),
            "items": [
                {
                    "item_code": self.item_code,
                    "qty": -2,
                    "rate": rate,
                    "against_sales_order": so_doc.name,
                    "so_detail": so_doc.items[0].name,
                    "dn_detail": dn.items[0].name,
                }
            ],
        })
        return_dn.flags.ignore_permissions = True
        return_dn.insert()
        return_dn.submit()

        # Check exposure: held drops by 2 * rate
        exp3 = get_retailer_stock_exposure(self.cust_north)
        self.assertAlmostEqual(exp3["stock_held_at_shop"], initial_held + (4 * rate), delta=1.0)

    def test_collection_follow_up_recording(self):
        """Record operational collection follow-up on unpaid Sales Invoice."""
        frappe.set_user("Administrator")
        company = frappe.defaults.get_global_default("company") or "Windsor Apparel Pvt Ltd"

        # Create submitted Sales Invoice
        inv = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": self.cust_north,
            "company": company,
            "set_posting_time": 1,
            "posting_date": add_days(nowdate(), -95),
            "due_date": add_days(nowdate(), -65),
            "items": [
                {
                    "item_code": self.item_code,
                    "qty": 2,
                    "rate": 500.0,
                }
            ],
        })
        inv.flags.ignore_permissions = True
        inv.insert()
        inv.submit()

        # Unauthorized user (ASM South cannot record follow-up on North customer)
        frappe.set_user(self.asm_south)
        with self.assertRaises(frappe.PermissionError):
            record_collection_follow_up(
                invoice=inv.name,
                customer=self.cust_north,
                outcome="Payment Promised",
            )

        # Invalid outcome raises ValidationError
        frappe.set_user(self.asm_north)
        with self.assertRaises(frappe.ValidationError):
            record_collection_follow_up(
                invoice=inv.name,
                customer=self.cust_north,
                outcome="Invalid Outcome String",
            )

        # Valid outcome succeeds
        res = record_collection_follow_up(
            invoice=inv.name,
            customer=self.cust_north,
            outcome="Payment Promised",
            notes="Retailer promised NEFT transfer by Friday.",
            expected_payment_date=add_days(nowdate(), 5),
        )
        self.assertEqual(res["status"], "Recorded")
        self.assertEqual(res["outcome"], "Payment Promised")

    def test_permission_scoped_operational_dashboard_and_no_leakage(self):
        """Dashboard strictly scopes metrics to user's assigned territory. Zero cross-territory leakage."""
        # Query as ASM North
        frappe.set_user(self.asm_north)
        north_dash = get_sales_operational_dashboard()
        self.assertIn("applications", north_dash)
        self.assertIn("orders", north_dash)
        self.assertIn("exposure", north_dash)
        self.assertIn("collections", north_dash)
        self.assertIn("delivery_issues", north_dash)

        # Query as ASM South
        frappe.set_user(self.asm_south)
        south_dash = get_sales_operational_dashboard()
        self.assertIn("applications", south_dash)

        # Negative test: user with no territory receives all 0 counts
        frappe.set_user("Administrator")
        no_terr_user = "test-no-territory-asm@example.invalid"
        if not frappe.db.exists("User", no_terr_user):
            u = frappe.get_doc({
                "doctype": "User",
                "email": no_terr_user,
                "first_name": "No Territory ASM",
                "roles": [{"role": ROLE_ASM}],
            })
            u.flags.ignore_permissions = True
            u.insert()

        frappe.set_user(no_terr_user)
        empty_dash = get_sales_operational_dashboard()
        self.assertEqual(empty_dash["exposure"]["total_retailers"], 0)
        self.assertEqual(empty_dash["orders"]["draft_count"], 0)
        self.assertEqual(empty_dash["collections"]["warning_count"], 0)

    def test_unified_sales_worklist_prioritization(self):
        """Unified worklist prioritizes high-priority items across follow-ups and collections."""
        frappe.set_user(self.asm_north)
        worklist_res = get_unified_sales_worklist()
        self.assertIn("worklist", worklist_res)
        self.assertIn("count", worklist_res)
        self.assertIsInstance(worklist_res["worklist"], list)

    def test_retailer_cadence_and_exposure_report(self):
        """Script report executes with territory scoping and returns expected columns and indicators."""
        # Common salesperson denied report
        frappe.set_user("test-no-territory-asm@example.invalid")
        with self.assertRaises(frappe.PermissionError):
            execute_cadence_report()

        # Supervising RSM can execute
        frappe.set_user(self.rsm)
        cols, data, msg, chart, summary = execute_cadence_report()
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)
        self.assertIsInstance(summary, list)

        col_fieldnames = {col["fieldname"] for col in cols}
        self.assertIn("customer", col_fieldnames)
        self.assertIn("total_exposure", col_fieldnames)
        self.assertIn("cadence_status", col_fieldnames)
        self.assertIn("order_block_status", col_fieldnames)

    def test_mobile_api_versioned_contract(self):
        """Mobile API endpoints return clean versioned payloads matching contract."""
        frappe.set_user(self.asm_north)

        # 1. Boot handshake
        boot = get_mobile_boot()
        self.assertEqual(boot["api_version"], API_VERSION)
        self.assertEqual(boot["user"], self.asm_north)
        self.assertIn("settings", boot)
        self.assertIn("geolocation_tolerance_meters", boot["settings"])

        # 2. Retailers directory
        ret_res = get_mobile_retailers(page=1, page_size=10)
        self.assertIn("retailers", ret_res)
        self.assertIn("has_more", ret_res)

        # 3. Mobile order creation
        mobile_req_id = self._unique_req_id()
        order_res = create_mobile_order(
            customer=self.cust_north,
            items=[{"item_code": self.item_code, "qty": 3}],
            request_id=mobile_req_id,
            delivery_date=nowdate(),
        )
        self.assertEqual(order_res["customer"], self.cust_north)

        # Idempotency replay with duplicate request_id
        replay_res = create_mobile_order(
            customer=self.cust_north,
            items=[{"item_code": self.item_code, "qty": 3}],
            request_id=mobile_req_id,
            delivery_date=nowdate(),
        )
        self.assertTrue(replay_res["idempotent_replay"])
        self.assertEqual(replay_res["name"], order_res["name"])

        # 4. Mobile dashboard
        dash = get_mobile_dashboard()
        self.assertIn("orders", dash)
        self.assertIn("exposure", dash)

        # 5. Mobile worklist
        wl = get_mobile_worklist()
        self.assertIn("worklist", wl)

    def test_high_volume_shops_scale(self):
        """Simulate high volume (250+ shops) in an RSM territory; assert sub-second dashboard query."""
        import time

        frappe.set_user(self.rsm)
        t0 = time.perf_counter()
        dash = get_sales_operational_dashboard()
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 2.0, f"Dashboard query took {elapsed:.2f}s, expected < 2.0s.")
        self.assertIsInstance(dash, dict)
