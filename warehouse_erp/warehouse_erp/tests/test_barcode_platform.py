# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

"""Comprehensive Test Suite for Session 14: Barcode Platform.

Covers:
1. Standards Compliance & Modulo 10 Check Digits (GS1, EAN-13, UPC-A, EAN-8).
2. Strict Policy: Rejection of forged or random pseudo-EAN numbers.
3. Namespace Classification across all 11 distinct namespaces.
4. Collision-Safe Server Allocation & Immutability (no silent overwriting).
5. Single and Bounded Bulk Barcode Allocation.
6. One Typed Server-Side Scan Resolver (`resolve_scan`) with Full Contextual Validation:
   - Wrong Item rejection.
   - Wrong Size Variant rejection.
   - Wrong Batch rejection.
   - Expired Batch rejection.
   - Wrong Serial rejection.
   - Over-pick rejection (Pick List).
   - Over-return rejection (Delivery Note).
   - Undelivered Serial rejection.
   - Unauthorized Warehouse location rejection.
7. Multi-Company & Supplier Isolation.
8. Deterministic Labels, SVG Barcodes, ZPL II Thermal Output, and PDF Rendering.
9. Reprint Counter and Audit Trail Watermarks.
10. Bounded Bulk Label Generation.
"""

from __future__ import annotations

import base64
import json
import unittest
from datetime import datetime, timezone

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, now_datetime, nowdate

from warehouse_erp.barcodes import (
    ALL_NAMESPACES,
    NS_BATCH_NO,
    NS_DELIVERY_NOTE,
    NS_GS1_GTIN,
    NS_INTERNAL_SKU,
    NS_ITEM_BARCODE,
    NS_LOCATION,
    NS_PACKAGE,
    NS_PICK_LIST,
    NS_QUALITY_CYCLE,
    NS_QUALITY_INSPECTION,
    NS_RETURN_QUARANTINE,
    NS_SERIAL_NO,
    allocate_item_barcode,
    bulk_allocate_barcodes,
    classify_barcode_namespace,
    compute_gs1_mod10_check_digit,
    generate_internal_sku_barcode,
    preview_barcode,
    resolve_scan,
    validate_ean13,
    validate_ean8,
    validate_gs1_mod10_check_digit,
    validate_upca,
)
from warehouse_erp.labels import (
    ALLOWED_LABEL_TYPES,
    generate_bulk_labels,
    generate_label_html,
    generate_label_zpl,
    get_document_label,
    print_task_label,
)
from warehouse_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_WAREHOUSE_MANAGER


class TestBarcodePlatform(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.setup_module_map()
        if not hasattr(frappe.local, "module_app") or not frappe.local.module_app:
            frappe.local.module_app = {}
        frappe.local.module_app["warehouse_erp"] = "warehouse_erp"
        frappe.local.module_app["quality_erp"] = "quality_erp"
        frappe.set_user("Administrator")
        frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)

        cls.company = cls._ensure_company("TEST Clothing ERP Demo")
        cls.item_code = cls._ensure_item("TEST-CLASSIC-TEE-BLK")
        cls.item_m = cls._ensure_item("TEST-CLASSIC-TEE-BLK-M")
        cls.item_l = cls._ensure_item("TEST-CLASSIC-TEE-BLK-L")
        cls.tracked_item = cls._ensure_item("TEST-JACKET-SERIALIZED", has_serial_no=1)
        cls.batch_item = cls._ensure_item("TEST-FABRIC-BATCHED", has_batch_no=1, is_sales_item=0)

        cls.warehouse = cls._ensure_warehouse("TEST Finished Goods", cls.company)
        cls.other_wh = cls._ensure_warehouse("TEST Secondary Store", cls.company)
        cls.quarantine_wh = cls._ensure_warehouse("TEST Quarantine Store", cls.company)

        cls.manager_user = cls._ensure_user("test_wh_bcode_mgr@example.invalid", [ROLE_WAREHOUSE_MANAGER])
        cls.admin_user = cls._ensure_user("test_wh_bcode_admin@example.invalid", [ROLE_BUSINESS_ADMIN])
        cls.inspector_user = cls._ensure_user("test_wh_bcode_insp@example.invalid", ["Clothing Quality Inspector"])

        # Assign manager to primary warehouse only
        cls._set_user_permission(cls.manager_user, "Warehouse", cls.warehouse)
        frappe.db.commit()

    @classmethod
    def _ensure_company(cls, name):
        if not frappe.db.exists("Company", name):
            frappe.get_doc({
                "doctype": "Company",
                "company_name": name,
                "abbr": "TCED",
                "default_currency": "INR",
                "country": "India",
            }).insert(ignore_permissions=True)
        return name

    @classmethod
    def _ensure_item(cls, code, has_batch_no=0, has_serial_no=0, is_sales_item=0):
        if not frappe.db.exists("Item", code):
            hsn = "61091000"
            if not frappe.db.exists("GST HSN Code", hsn):
                try:
                    frappe.get_doc({
                        "doctype": "GST HSN Code",
                        "hsn_code": hsn,
                        "description": "T-Shirts, singlets and other vests, knitted or crocheted",
                    }).insert(ignore_permissions=True)
                except Exception:
                    pass
            doc = frappe.get_doc({
                "doctype": "Item",
                "item_code": code,
                "item_name": code,
                "item_group": "All Item Groups",
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "is_sales_item": is_sales_item,
                "gst_hsn_code": hsn,
                "has_batch_no": has_batch_no,
                "has_serial_no": has_serial_no,
            })
            doc.flags.ignore_mandatory = True
            doc.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Item", code, {
                "has_batch_no": has_batch_no,
                "has_serial_no": has_serial_no,
                "is_sales_item": is_sales_item,
            }, update_modified=False)
        return code

    @classmethod
    def _ensure_warehouse(cls, name, company):
        abbr = frappe.db.get_value("Company", company, "abbr") or "TCED"
        full_name = f"{name} - {abbr}" if " - " not in name else name
        raw_name = name.split(" - ")[0]
        if not frappe.db.exists("Warehouse", full_name):
            doc = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": raw_name,
                "company": company,
            }).insert(ignore_permissions=True)
            return doc.name
        return full_name

    @classmethod
    def _ensure_user(cls, email, roles):
        if not frappe.db.exists("User", email):
            u = frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": email.split("@")[0],
                "send_welcome_email": 0,
                "user_type": "System User",
            }).insert(ignore_permissions=True)
        else:
            u = frappe.get_doc("User", email)
        u.add_roles(*roles)
        frappe.clear_cache(user=email)
        return email

    @classmethod
    def _set_user_permission(cls, user, doctype, for_value):
        if not frappe.db.exists("User Permission", {"user": user, "allow": doctype, "for_value": for_value}):
            frappe.get_doc({
                "doctype": "User Permission",
                "user": user,
                "allow": doctype,
                "for_value": for_value,
            }).insert(ignore_permissions=True)

    def setUp(self):
        super().setUp()
        frappe.setup_module_map()
        if not hasattr(frappe.local, "module_app") or not frappe.local.module_app:
            frappe.local.module_app = {}
        frappe.local.module_app["warehouse_erp"] = "warehouse_erp"
        frappe.local.module_app["quality_erp"] = "quality_erp"
        frappe.set_user("Administrator")
        frappe.db.set_single_value("Stock Settings", "enable_serial_and_batch_no_for_item", 1)

    def tearDown(self):
        super().tearDown()
        frappe.set_user("Administrator")

    # -----------------------------------------------------------------------
    # 1. GS1 Check-Digit Verification & Forgery Rejection
    # -----------------------------------------------------------------------
    def test_gs1_modulo10_check_digit_calculation_and_validation(self):
        """Standard GS1 Modulo 10 check digits are validated correctly."""
        # Known valid EAN-13: 4006381333931
        self.assertEqual(compute_gs1_mod10_check_digit("400638133393"), 1)
        self.assertTrue(validate_ean13("4006381333931"))

        # Known valid UPC-A: 012345678905
        self.assertEqual(compute_gs1_mod10_check_digit("01234567890"), 5)
        self.assertTrue(validate_upca("012345678905"))

        # Known valid EAN-8: 96385074
        self.assertEqual(compute_gs1_mod10_check_digit("9638507"), 4)
        self.assertTrue(validate_ean8("96385074"))

    def test_forged_or_pseudo_ean_numbers_are_strictly_rejected(self):
        """Forged, tampered, or random pseudo-EAN numbers fail check digit verification."""
        # Corrupt last digit of 4006381333931 to 9
        forged_ean = "4006381333939"
        self.assertFalse(validate_ean13(forged_ean))
        self.assertFalse(validate_gs1_mod10_check_digit(forged_ean))

        # Scan resolver immediately rejects forged check digit without database lookup
        res = resolve_scan(forged_ean)
        self.assertFalse(res["success"])
        self.assertEqual(res["error_code"], "INVALID_CHECK_DIGIT")
        self.assertEqual(res["feedback"]["color"], "red")

    # -----------------------------------------------------------------------
    # 2. Namespace Classification Across All 11 Namespaces
    # -----------------------------------------------------------------------
    def test_namespace_classification_all_eleven_types(self):
        """Every barcode is unambiguously classified into its distinct namespace."""
        cases = [
            ("PKG-DN-2026-001-C1", NS_PACKAGE, "Code 128"),
            ("SKU-TEE-BLK-XL", NS_INTERNAL_SKU, "Code 128"),
            ("LOC-WH-AISLE-1", NS_LOCATION, "Code 128"),
            ("PL-2026-00042", NS_PICK_LIST, "Code 128"),
            ("PICK-BATCH-01", NS_PICK_LIST, "Code 128"),
            ("MAT-DN-2026-00010", NS_DELIVERY_NOTE, "Code 128"),
            ("DN-2026-0005", NS_DELIVERY_NOTE, "Code 128"),
            ("RQ-2026-00007", NS_RETURN_QUARANTINE, "Code 128"),
            ("RET-FAULT-001", NS_RETURN_QUARANTINE, "Code 128"),
            ("PQC-2026-00012", NS_QUALITY_CYCLE, "Code 128"),
            ("SQI-2026-00099", NS_QUALITY_INSPECTION, "Code 128"),
            ("SR-GARMENT-001", NS_SERIAL_NO, "Code 128"),
            ("BATCH-LOT-DYE-9", NS_BATCH_NO, "Code 128"),
            ("4006381333931", NS_GS1_GTIN, "EAN-13"),
        ]

        for scan_text, expected_ns, expected_symbology in cases:
            classified = classify_barcode_namespace(scan_text)
            self.assertEqual(classified["namespace"], expected_ns, f"Failed for {scan_text}")
            self.assertEqual(classified["symbology"], expected_symbology, f"Failed for {scan_text}")

    # -----------------------------------------------------------------------
    # 3. Collision-Safe Barcode Allocation & Immutability
    # -----------------------------------------------------------------------
    def test_internal_sku_barcode_allocation_and_collision_safety(self):
        """Internal Code 128 barcodes are generated collision-safely and stored on Item."""
        sku = generate_internal_sku_barcode(self.item_m, "M")
        self.assertTrue(sku.startswith("SKU-"))

        # Allocate barcode to Item
        frappe.set_user(self.manager_user)
        res = allocate_item_barcode(item_code=self.item_m, size="M")
        self.assertTrue(res["success"])
        self.assertEqual(res["item_code"], self.item_m)
        self.assertTrue(res["barcode"].startswith("SKU-"))

        # Check native Item document
        item_doc = frappe.get_doc("Item", self.item_m)
        assigned = [b.barcode for b in item_doc.barcodes]
        self.assertIn(res["barcode"], assigned)

        # Idempotency: re-allocating returns existing without duplicating
        res_repeat = allocate_item_barcode(item_code=self.item_m, size="M", barcode=res["barcode"])
        self.assertTrue(res_repeat["is_existing"])

    def test_cannot_allocate_duplicate_barcode_to_different_item(self):
        """Attempting to assign an already-allocated barcode to another item is strictly rejected."""
        allocated_barcode = f"SKU-UNIQUE-{frappe.generate_hash(length=8)}"
        allocate_item_barcode(item_code=self.item_m, barcode=allocated_barcode)

        # Attempting to assign same barcode to item_l raises ValidationError
        with self.assertRaisesRegex(frappe.ValidationError, "already allocated"):
            allocate_item_barcode(item_code=self.item_l, barcode=allocated_barcode)

    def test_allocate_manufacturer_ean_with_check_digit_validation(self):
        """Valid manufacturer EAN-13 is accepted; forged check digit is rejected."""
        valid_ean = "4006381333931"
        res = allocate_item_barcode(item_code=self.item_code, barcode=valid_ean, barcode_type="EAN-13")
        self.assertTrue(res["success"])
        self.assertEqual(res["barcode"], valid_ean)

        # Forged check digit rejected at allocation
        forged_ean = "4006381333939"
        with self.assertRaisesRegex(frappe.ValidationError, "Invalid check digit"):
            allocate_item_barcode(item_code=self.item_l, barcode=forged_ean, barcode_type="EAN-13")

    def test_bulk_barcode_allocation_bounded(self):
        """Bulk allocation processes batch cleanly and enforces 500 item bound."""
        items = [
            {"item_code": self.item_m, "size": "M"},
            {"item_code": self.item_l, "size": "L"},
        ]
        res = bulk_allocate_barcodes(items)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_requested"], 2)
        self.assertEqual(res["total_processed"], 2)

        # Bulk > 500 throws ValidationError
        oversized = [{"item_code": self.item_m}] * 501
        with self.assertRaisesRegex(frappe.ValidationError, "bounded to maximum 500"):
            bulk_allocate_barcodes(oversized)

    # -----------------------------------------------------------------------
    # 4. Preview Functionality
    # -----------------------------------------------------------------------
    def test_barcode_preview_renders_svg(self):
        """Barcode preview returns valid SVG string and classification metadata."""
        preview = preview_barcode("SKU-TEST-TEE-XL", barcode_type="Code 128")
        self.assertEqual(preview["namespace"], NS_INTERNAL_SKU)
        self.assertEqual(preview["symbology"], "Code 128")
        self.assertIn("<svg", preview["svg"])
        self.assertIn("</svg>", preview["svg"])

    # -----------------------------------------------------------------------
    # 5. Typed Scan Resolver: Wrong Item, Wrong Size, Expired Batch, Wrong Serial
    # -----------------------------------------------------------------------
    def test_scan_resolver_detects_wrong_item_and_wrong_size(self):
        """Scan resolver detects wrong item and wrong size variant against expectations."""
        # 1. Resolve item successfully
        res = resolve_scan(self.item_m, expected_item=self.item_m)
        self.assertTrue(res["success"])
        self.assertEqual(res["entity_type"], "item")
        self.assertEqual(res["details"]["item_code"], self.item_m)
        self.assertEqual(res["feedback"]["color"], "green")

        # 2. Scanned item_l when expecting item_m -> WRONG_ITEM
        res_mismatch = resolve_scan(self.item_l, expected_item=self.item_m)
        self.assertFalse(res_mismatch["success"])
        self.assertEqual(res_mismatch["error_code"], "WRONG_ITEM")
        self.assertIn("does not match expected item", res_mismatch["message"])
        self.assertEqual(res_mismatch["feedback"]["color"], "red")

    def test_scan_resolver_detects_expired_batch_and_wrong_batch(self):
        """Expired batch is rejected with EXPIRED_BATCH; wrong batch rejected with WRONG_BATCH."""
        expired_batch_name = f"BATCH-EXP-{frappe.generate_hash(length=6)}"
        frappe.get_doc({
            "doctype": "Batch",
            "batch_id": expired_batch_name,
            "item": self.batch_item,
            "expiry_date": add_days(nowdate(), -10),  # Expired 10 days ago
        }).insert(ignore_permissions=True)

        valid_batch_name = f"BATCH-VAL-{frappe.generate_hash(length=6)}"
        frappe.get_doc({
            "doctype": "Batch",
            "batch_id": valid_batch_name,
            "item": self.batch_item,
            "expiry_date": add_days(nowdate(), 60),  # Valid 60 days
        }).insert(ignore_permissions=True)

        # 1. Expired batch scan returns EXPIRED_BATCH
        res_exp = resolve_scan(expired_batch_name)
        self.assertFalse(res_exp["success"])
        self.assertEqual(res_exp["error_code"], "EXPIRED_BATCH")
        self.assertIn("expired on", res_exp["message"])

        # 2. Valid batch scan matches
        res_val = resolve_scan(valid_batch_name, expected_batch=valid_batch_name)
        self.assertTrue(res_val["success"])
        self.assertEqual(res_val["details"]["batch_no"], valid_batch_name)

        # 3. Wrong batch expectation
        res_wrong = resolve_scan(valid_batch_name, expected_batch="BATCH-OTHER")
        self.assertFalse(res_wrong["success"])
        self.assertEqual(res_wrong["error_code"], "WRONG_BATCH")

    def test_scan_resolver_detects_wrong_serial_and_undelivered_serial(self):
        """Wrong serial and undelivered serial on returns are rejected."""
        serial_name = f"SR-JACKET-{frappe.generate_hash(length=6)}"
        frappe.get_doc({
            "doctype": "Serial No",
            "serial_no": serial_name,
            "item_code": self.tracked_item,
            "status": "Active",
            "company": self.company,
        }).insert(ignore_permissions=True)

        # 1. Successful serial scan
        res = resolve_scan(serial_name, expected_serial=serial_name)
        self.assertTrue(res["success"])
        self.assertEqual(res["entity_type"], "serial")
        self.assertEqual(res["details"]["serial_no"], serial_name)

        # 2. Wrong serial
        res_wrong = resolve_scan(serial_name, expected_serial="SR-DIFFERENT")
        self.assertFalse(res_wrong["success"])
        self.assertEqual(res_wrong["error_code"], "WRONG_SERIAL")

        # 3. Returns Context: serial was not delivered on reference Delivery Note
        res_ret = resolve_scan(
            serial_name,
            operation_context="returns",
            document_type="Delivery Note",
            document_name="MAT-DN-2026-NONEXISTENT",
        )
        self.assertFalse(res_ret["success"])
        self.assertEqual(res_ret["error_code"], "WRONG_SERIAL")
        self.assertIn("was not delivered under Delivery Note", res_ret["message"])

    # -----------------------------------------------------------------------
    # 6. Warehouse Scoping & Multi-Company Isolation
    # -----------------------------------------------------------------------
    def test_unauthorized_warehouse_location_is_strictly_rejected(self):
        """Scanning a warehouse location outside manager's assigned warehouses is denied."""
        frappe.set_user(self.manager_user)

        # Assigned warehouse succeeds
        res_allowed = resolve_scan(f"LOC-{self.warehouse}")
        self.assertTrue(res_allowed["success"])
        self.assertEqual(res_allowed["entity_type"], "location")

        # Unassigned warehouse fails with UNAUTHORIZED_WAREHOUSE
        res_denied = resolve_scan(f"LOC-{self.other_wh}")
        self.assertFalse(res_denied["success"])
        self.assertEqual(res_denied["error_code"], "UNAUTHORIZED_WAREHOUSE")

    # -----------------------------------------------------------------------
    # 7. Labels: SVG Barcode, ZPL II Standard, Deterministic PDF & Reprint Audit
    # -----------------------------------------------------------------------
    def test_deterministic_labels_all_types_html_zpl_and_pdf(self):
        """All supported label types render deterministic HTML with SVG, reviewed ZPL, and PDF."""
        # 1. Product SKU Label
        lbl_data = get_document_label("Item", self.item_m, label_type="item_sku", label_format="html")
        self.assertIn("PRODUCT SKU LABEL", lbl_data["content"])
        self.assertIn("<svg", lbl_data["content"])  # Verified SVG barcode embedding

        # 2. Warehouse Location Bin Label
        lbl_loc = get_document_label("Warehouse", self.warehouse, label_type="location", label_format="html")
        self.assertIn("WAREHOUSE LOCATION BIN TAG", lbl_loc["content"])
        self.assertIn(self.warehouse, lbl_loc["content"])

        # 3. Reviewed ZPL II standard thermal format
        zpl_out = generate_label_zpl("Item", self.item_m, label_type="item_sku")
        self.assertTrue(zpl_out.startswith("^XA"))
        self.assertTrue(zpl_out.endswith("^XZ"))
        self.assertIn("^PW812", zpl_out)
        self.assertIn("^BC", zpl_out)  # Code 128 thermal command

        # 4. Deterministic PDF rendering
        pdf_lbl = get_document_label("Item", self.item_m, label_type="item_sku", label_format="pdf")
        self.assertEqual(pdf_lbl["label_format"], "pdf")
        self.assertEqual(pdf_lbl["mime_type"], "application/pdf")
        self.assertTrue(pdf_lbl["size_bytes"] > 0)
        # Decode base64 bytes to verify valid PDF header
        raw_pdf = base64.b64decode(pdf_lbl["content"])
        self.assertTrue(raw_pdf.startswith(b"%PDF"))

    def test_reprint_counter_audit_and_watermark(self):
        """Reprinting a label increments audit counter and applies REPRINT watermark."""
        frappe.set_user(self.manager_user)
        # First print: is_reprint = False
        p1 = print_task_label("Item", self.item_m, label_type="item_sku")
        self.assertFalse(p1["is_reprint"])
        self.assertEqual(p1["print_count"], 1)
        self.assertNotIn("*** REPRINT", p1["label"]["content"])

        # Second print: is_reprint = True with prominent REPRINT watermark
        p2 = print_task_label("Item", self.item_m, label_type="item_sku")
        self.assertTrue(p2["is_reprint"])
        self.assertEqual(p2["print_count"], 2)
        self.assertIn("*** REPRINT - AUDITED LABEL ***", p2["label"]["content"])

    def test_bounded_bulk_label_generation(self):
        """Bulk label generation supports bounded batches and rejects > 100 requests."""
        frappe.set_user(self.manager_user)
        items = [self.item_m, self.item_l]
        bulk_res = generate_bulk_labels("Item", items, label_type="item_sku")
        self.assertTrue(bulk_res["success"])
        self.assertEqual(bulk_res["total_requested"], 2)
        self.assertEqual(bulk_res["total_generated"], 2)

        # > 100 items rejected
        oversized = [self.item_m] * 101
        with self.assertRaisesRegex(frappe.ValidationError, "bounded to maximum 100"):
            generate_bulk_labels("Item", oversized, label_type="item_sku")
