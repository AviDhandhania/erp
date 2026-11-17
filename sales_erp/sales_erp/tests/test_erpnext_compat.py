"""ERPNext-owned setup artifacts are repaired without duplicating their definitions."""

import unittest
from unittest.mock import patch

from sales_erp import erpnext_compat


class TestERPNextCompatibility(unittest.TestCase):
    def test_complete_schema_does_not_rerun_erpnext_installer(self):
        with (
            patch.object(erpnext_compat.frappe.db, "has_column", return_value=True),
            patch(
                "erpnext.setup.install.create_address_and_contact_custom_fields"
            ) as repair,
        ):
            self.assertFalse(erpnext_compat.ensure_erpnext_contact_fields())
        repair.assert_not_called()

    def test_missing_schema_uses_erpnext_owned_installer(self):
        with (
            patch.object(erpnext_compat.frappe.db, "has_column", return_value=False),
            patch(
                "erpnext.setup.install.create_address_and_contact_custom_fields"
            ) as repair,
        ):
            self.assertTrue(erpnext_compat.ensure_erpnext_contact_fields())
        repair.assert_called_once_with()
