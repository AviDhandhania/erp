# Copyright (c) 2026, Clothing ERP Contributors
# License: MIT. See LICENSE

"""Integration tests for Session 3 API Security: Rate Limiting, Idempotency, Input Validation, and Audit Logging."""

import frappe
from frappe.tests.utils import FrappeTestCase

from sales_erp.api_security import (
    check_rate_limit,
    clear_idempotency,
    record_security_audit_event,
    save_idempotency_result,
    validate_bounded_list,
    validate_dict_keys,
    validate_float,
    validate_idempotency,
    validate_int,
    validate_string,
)
from sales_erp.ordering import create_draft_sales_order


class TestAPISecurity(FrappeTestCase):
    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        frappe.local.request_cache.clear()

    def tearDown(self):
        frappe.flags.pop("test_rate_limits", None)
        super().tearDown()

    def test_idempotency_binding_replay_and_mismatch(self):
        """Idempotency keys bind user, operation, and payload. Replays succeed; mismatches fail."""
        op = "test_checkout"
        key = "idem-test-key-001"
        user = "test_user@example.invalid"
        payload_1 = {"items": ["SKU-1"], "qty": 10}
        payload_2 = {"items": ["SKU-2"], "qty": 20}

        # Clear any prior state
        clear_idempotency(op, key, user)

        # First request: not a replay
        cached, is_replay = validate_idempotency(op, key, payload_1, user)
        self.assertFalse(is_replay)
        self.assertIsNone(cached)

        # Save result
        result_data = {"order_id": "ORD-12345", "status": "Draft"}
        save_idempotency_result(op, key, result_data, payload_1, user)

        # Replay with same payload: must return cached result with idempotent_replay=True
        cached, is_replay = validate_idempotency(op, key, payload_1, user)
        self.assertTrue(is_replay)
        self.assertEqual(cached.get("order_id"), "ORD-12345")
        self.assertTrue(cached.get("idempotent_replay"))

        # Replay with mismatched payload: must throw DuplicateEntryError
        with self.assertRaises(frappe.DuplicateEntryError):
            validate_idempotency(op, key, payload_2, user)

        # Cleanup
        clear_idempotency(op, key, user)

    def test_idempotency_key_length_validation(self):
        """Keys exceeding 140 chars must be rejected."""
        oversized = "x" * 141
        with self.assertRaises(frappe.ValidationError):
            validate_idempotency("test_op", oversized, {"test": 1})

    def test_rate_limiting_enforcement(self):
        """Exceeding configured rate limit raises TooManyRequestsError (429)."""
        frappe.flags.test_rate_limits = True
        op = "test_rate_limited_api"
        test_user = "rate_limit_victim@example.invalid"
        frappe.cache.delete_value(f"clothing_rl:{op}:{test_user}")

        # Limit = 3 requests per 60 seconds
        for _ in range(3):
            allowed = check_rate_limit(op, limit=3, window_seconds=60, user=test_user)
            self.assertTrue(allowed)

        # 4th request must be blocked with TooManyRequestsError
        with self.assertRaises(frappe.TooManyRequestsError):
            check_rate_limit(op, limit=3, window_seconds=60, user=test_user)

        frappe.cache.delete_value(f"clothing_rl:{op}:{test_user}")

    def test_input_bounds_and_type_validations(self):
        """Strict input validation: bounds, types, enums, null bytes, and list limits."""
        # String validation
        self.assertEqual(validate_string("  valid_text  ", "Field"), "valid_text")
        with self.assertRaises(frappe.ValidationError):
            validate_string("null\x00byte", "Field")
        with self.assertRaises(frappe.ValidationError):
            validate_string("toolong", "Field", max_len=5)
        with self.assertRaises(frappe.ValidationError):
            validate_string("InvalidEnum", "Field", allowed_values={"Draft", "Approved"})

        # Integer bounds
        self.assertEqual(validate_int("42", "IntField", min_val=1, max_val=100), 42)
        with self.assertRaises(frappe.ValidationError):
            validate_int("0", "IntField", min_val=1)
        with self.assertRaises(frappe.ValidationError):
            validate_int("101", "IntField", max_val=100)
        with self.assertRaises(frappe.ValidationError):
            validate_int("not_a_number", "IntField")

        # Float bounds
        self.assertEqual(validate_float("19.99", "FloatField", min_val=0, max_val=50), 19.99)
        with self.assertRaises(frappe.ValidationError):
            validate_float("-1.0", "FloatField", min_val=0)

        # Bounded list
        self.assertEqual(validate_bounded_list(["a", "b"], "ListField", max_len=5), ["a", "b"])
        with self.assertRaises(frappe.ValidationError):
            validate_bounded_list([], "ListField", min_len=1)
        with self.assertRaises(frappe.ValidationError):
            validate_bounded_list(["a", "b", "c"], "ListField", max_len=2)

        # Dict keys validation
        valid_dict = validate_dict_keys({"key1": "val1", "key2": "val2"}, "DictField", {"key1", "key2", "key3"})
        self.assertIn("key1", valid_dict)
        with self.assertRaises(frappe.ValidationError):
            validate_dict_keys({"key1": "val", "malicious_key": 1}, "DictField", {"key1"})

    def test_security_audit_events_in_activity_log(self):
        """Critical security events are durably recorded in Frappe's Activity Log."""
        ref_doc = "TEST-REF-DOC-001"
        record_security_audit_event(
            event_type="Test Security Transition",
            reference_doctype="Customer",
            reference_name=ref_doc,
            details={"action": "authorized", "scope": "sales_territory"},
            user="test-admin@example.invalid",
        )

        logs = frappe.get_all(
            "Activity Log",
            filters={
                "operation": "Test Security Transition",
                "reference_doctype": "Customer",
                "reference_name": ref_doc,
            },
            fields=["name", "operation", "reference_name", "content"],
        )
        self.assertGreaterEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log.operation, "Test Security Transition")
        self.assertEqual(log.reference_name, ref_doc)
        self.assertIn("authorized", log.content)

    def test_sales_order_idempotent_creation_and_replay(self):
        """Draft sales order creation verifies idempotency key and returns replay on duplicate request."""
        customer = "TEST 1-4 EBOC (Exclusive Brand Outlet) Store"
        if not frappe.db.exists("Customer", customer):
            customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
        if not customer:
            self.skipTest("No test customer found.")

        # Find any saleable item
        item = frappe.db.get_value("Item", {"is_sales_item": 1, "disabled": 0, "has_variants": 0}, "name")
        if not item:
            item = "TEST-SKU-1"

        req_id = "idem-test-order-req-000000000000001"  # 35 chars
        items = [{"item_code": item, "qty": 1}]

        # First request creates draft order
        res1 = create_draft_sales_order(customer, items, req_id)
        self.assertTrue(res1.get("name"))
        self.assertFalse(res1.get("idempotent_replay", False))

        # Second request with same req_id must replay cleanly without creating new order
        res2 = create_draft_sales_order(customer, items, req_id)
        self.assertEqual(res2.get("name"), res1.get("name"))
        self.assertTrue(res2.get("idempotent_replay"))
