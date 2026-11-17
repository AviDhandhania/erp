"""Development seed safety tests."""

import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from sales_erp import seed


class TestSeedSafety(unittest.TestCase):
    def test_seed_refuses_non_developer_site(self):
        with patch.object(seed, "frappe") as framework:
            framework.conf.developer_mode = 0
            framework.flags.in_test = False
            framework.throw.side_effect = frappe.PermissionError
            framework._.side_effect = lambda value: value
            with self.assertRaises(frappe.PermissionError):
                seed._require_development_site()

    def test_all_seed_records_are_clearly_fictional(self):
        self.assertTrue(seed.SEED_RETAILER.startswith("TEST "))
        for product in seed.PRODUCTS:
            self.assertTrue(product["code"].startswith("TEST-"))
            self.assertTrue(product["name"].startswith("TEST "))
            self.assertTrue(product["brand"].startswith("TEST "))
            self.assertTrue(product["colour"])
            self.assertRegex(product["hsn_code"], r"^[0-9]{8}$")
            self.assertTrue(
                all(value.startswith("TEST ") for value in product["sizes"])
            )

    def test_seed_images_are_local_packaged_assets(self):
        public_root = Path(__file__).parents[1] / "public"
        for product in seed.PRODUCTS:
            self.assertTrue(
                product["image"].startswith("/assets/sales_erp/images/seed/")
            )
            relative = product["image"].removeprefix("/assets/sales_erp/")
            image = public_root / relative
            self.assertTrue(image.is_file(), image)
            self.assertGreater(image.stat().st_size, 20_000)

    def test_seed_accounts_and_territories_are_clearly_test_only(self):
        accounts = (
            seed.SEED_RSM,
            seed.SEED_ASM_NORTH,
            seed.SEED_ASM_SOUTH,
            seed.SEED_BUSINESS_ADMIN,
            seed.SEED_WAREHOUSE_MANAGER,
        )
        self.assertTrue(all(email.startswith("test-") for email in accounts))
        self.assertTrue(all(email.endswith("@example.invalid") for email in accounts))
        self.assertTrue(
            all(territory.startswith("TEST ") for territory, _asm in seed.SEED_TERRITORIES)
        )
