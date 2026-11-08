"""Tests for Frappe Insights compatibility and demo data resilience."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from clothing_erp import insights_compat


class TestInsightsCompat(unittest.TestCase):
    def test_safe_download_uses_bundled_duckdb(self):
        insights_compat.patch_demo_data_factory()
        from insights.setup.demo import DemoDataFactory

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_db = Path(temp_dir) / "insights_demo_data.duckdb"
            fake_factory = MagicMock()
            fake_factory.db_filename = "insights_demo_data.duckdb"
            fake_factory.db_file_path = str(temp_db)
            fake_factory.db_url = "https://invalid.example.com/not_exist.duckdb"

            with patch.object(frappe, "get_app_path") as get_app_path:
                # Point to a real dummy bundled file
                bundled_dummy = Path(temp_dir) / "bundled.duckdb"
                bundled_dummy.write_bytes(b"DUCKDB_DEMO_DATA")
                get_app_path.return_value = str(bundled_dummy)

                DemoDataFactory.download_demo_data(fake_factory)

                self.assertTrue(temp_db.exists())
                self.assertEqual(temp_db.read_bytes(), b"DUCKDB_DEMO_DATA")
