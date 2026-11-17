# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

import io
import unittest
from unittest.mock import Mock, patch
from PIL import Image

import frappe
from sales_erp.file_security import (
    EICAR_SIGNATURE,
    export_records_to_csv,
    has_file_permission,
    redact_sensitive_data,
    reference_safe_delete_file,
    sanitize_spreadsheet_injection,
    save_secure_file,
    validate_file_content,
)


class TestFilePrivacy(unittest.TestCase):
    def setUp(self):
        # Generate valid 10x10 PNG bytes
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        self.valid_png_bytes = buf.getvalue()

        # Generate valid 10x10 JPEG bytes
        buf_jpg = io.BytesIO()
        img.save(buf_jpg, format="JPEG")
        self.valid_jpg_bytes = buf_jpg.getvalue()

    def test_valid_image_upload_passes(self):
        clean = validate_file_content(self.valid_png_bytes, filename="test.png")
        self.assertTrue(len(clean) > 0)
        self.assertTrue(clean.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_extension_mismatch_fails_validation(self):
        # JPEG content with .png extension
        with self.assertRaises(frappe.ValidationError) as cm:
            validate_file_content(self.valid_jpg_bytes, filename="fake.png")
        self.assertIn("does not match detected file format", str(cm.exception))

    def test_unsupported_extension_fails_validation(self):
        with self.assertRaises(frappe.ValidationError) as cm:
            validate_file_content(self.valid_png_bytes, filename="malicious.exe")
        self.assertIn("not permitted", str(cm.exception))

    def test_embedded_script_polyglot_rejected(self):
        # Image bytes with embedded PHP tag
        polyglot = self.valid_png_bytes + b"<?php echo 'pwned'; ?>"
        with self.assertRaises(frappe.ValidationError) as cm:
            validate_file_content(polyglot, filename="avatar.png")
        self.assertIn("Malicious embedded script or executable polyglot", str(cm.exception))

    def test_malware_eicar_signature_quarantined_and_rejected(self):
        malware = self.valid_png_bytes + EICAR_SIGNATURE
        with self.assertRaises(frappe.ValidationError) as cm:
            validate_file_content(malware, filename="test_malware.png")
        self.assertIn("Malware signature detected", str(cm.exception))

    def test_save_secure_file_is_private_by_default(self):
        saved = save_secure_file(
            self.valid_png_bytes,
            filename="receipt.png",
            attached_to_doctype="Retailer Visit",
            attached_to_name="RET-VIS-2026-00001",
        )
        self.assertTrue(saved["is_private"])
        self.assertTrue(saved["file_url"].startswith("/private/files/"))

        # Clean up created file
        frappe.delete_doc("File", saved["name"], ignore_permissions=True)

    def test_parent_document_permission_required_for_private_file(self):
        file_doc = frappe._dict(
            doctype="File",
            name="FILE-TEST-001",
            is_private=1,
            owner="asm_user@example.invalid",
            attached_to_doctype="Retailer Visit",
            attached_to_name="RET-VIS-2026-99999",
        )

        with patch.object(frappe.db, "get_value", return_value=1), \
             patch.object(frappe.db, "exists", return_value=True):
            # When parent document permission check returns False
            with patch.object(frappe, "has_permission", return_value=False):
                # Even though user is the owner, permission must be DENIED
                allowed = has_file_permission(file_doc, ptype="read", user="asm_user@example.invalid")
                self.assertFalse(allowed)

            # When parent document permission check returns True
            with patch.object(frappe, "has_permission", return_value=True):
                allowed = has_file_permission(file_doc, ptype="read", user="asm_user@example.invalid")
                self.assertTrue(allowed)

    def test_disabled_user_cannot_access_private_file(self):
        file_doc = frappe._dict(
            doctype="File",
            is_private=1,
            attached_to_doctype="Retailer Visit",
            attached_to_name="RET-VIS-2026-00001",
        )
        with patch.object(frappe.db, "get_value", return_value=0):  # enabled=0
            self.assertFalse(has_file_permission(file_doc, ptype="read", user="disabled_user@example.invalid"))

    def test_reference_safe_deletion_blocks_active_references(self):
        with patch.object(frappe.db, "exists", side_effect=lambda dt, flt: dt == "Item"):
            with self.assertRaises(frappe.ValidationError) as cm:
                reference_safe_delete_file("/private/files/in_use.jpg")
            self.assertIn("referenced as primary image on Item", str(cm.exception))

    def test_reference_safe_deletion_never_deletes_packaged_assets(self):
        result = reference_safe_delete_file("/assets/sales_erp/logo.png")
        self.assertFalse(result)

    def test_spreadsheet_injection_sanitization(self):
        self.assertEqual(sanitize_spreadsheet_injection("=cmd|'/C calc'!A0"), "'=cmd|'/C calc'!A0")
        self.assertEqual(sanitize_spreadsheet_injection("+1234"), "'+1234")
        self.assertEqual(sanitize_spreadsheet_injection("-100"), "'-100")
        self.assertEqual(sanitize_spreadsheet_injection("@SUM(A1:A10)"), "'@SUM(A1:A10)")
        self.assertEqual(sanitize_spreadsheet_injection("\talert(1)"), "'\talert(1)")
        self.assertEqual(sanitize_spreadsheet_injection("Normal Text"), "Normal Text")

    def test_sensitive_data_redaction(self):
        raw = {
            "password": "SuperSecretPassword123",
            "api_secret": "my_api_key_secret",
            "gstin": "27AAPFU0939F1ZV",
            "phone": "+919876543210",
            "customer_name": "Test Boutique",
            "items": [{"token": "jwt_session_token", "price": 1000}],
        }
        redacted = redact_sensitive_data(raw)
        self.assertEqual(redacted["password"], "******")
        self.assertEqual(redacted["api_secret"], "******")
        # Middle 10 chars of GSTIN masked
        self.assertEqual(redacted["gstin"], "27**********1ZV")
        # Middle digits of phone masked
        self.assertTrue(redacted["phone"].startswith("+9") and redacted["phone"].endswith("10"))
        self.assertIn("****", redacted["phone"])
        self.assertEqual(redacted["customer_name"], "Test Boutique")
        self.assertEqual(redacted["items"][0]["token"], "******")
