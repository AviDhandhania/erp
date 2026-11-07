import unittest
from unittest.mock import patch

import frappe

from clothing_erp.clothing_erp.doctype.retailer_application import retailer_application


class TestRetailerWorkflow(unittest.TestCase):
    def test_duplicate_detection_normalizes_phone_email_and_gstin(self):
        application = frappe._dict(shop_name="TEST New Shop", phone="+91 98765-43210", email="TEST@EXAMPLE.INVALID", gstin="testgstin")
        customer = frappe._dict(name="TEST Existing", customer_name="Different", mobile_no="9876543210", email_id="test@example.invalid", tax_id="TESTGSTIN")
        with patch.object(frappe, "get_all", side_effect=[[customer], []]):
            matches = retailer_application.find_duplicates(application)
        self.assertEqual(set(matches[0]["reasons"]), {"phone", "email", "GSTIN"})

    def test_approval_requires_manager_role(self):
        with patch.object(retailer_application, "require_role", side_effect=frappe.PermissionError), patch.object(frappe, "get_doc") as get_doc:
            with self.assertRaises(frappe.PermissionError):
                retailer_application.approve("RET-APP-TEST")
            get_doc.assert_not_called()
