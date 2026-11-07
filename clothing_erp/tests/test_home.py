"""Tests for Clothing ERP homepage navigation placeholders and foundation hooks."""

from importlib import import_module
import unittest


class TestClothingERPHomepageUnit(unittest.TestCase):
	"""Unit tests verifying navigation placeholders without requiring a live database."""

	def test_required_placeholders_present(self):
		"""Verify that all 7 required navigation placeholders are registered."""
		clothing_module = import_module("clothing_erp.clothing_erp.www.clothing")
		items = clothing_module.get_navigation_items()
		labels = {item["label"] for item in items}
		expected = {"Admin", "Products", "Sales", "Retailers", "Warehouse", "Suppliers", "Reports"}
		self.assertTrue(expected.issubset(labels), f"Missing placeholders: {expected - labels}")

	def test_placeholder_attributes(self):
		"""Verify each navigation placeholder has required attributes."""
		clothing_module = import_module("clothing_erp.clothing_erp.www.clothing")
		items = clothing_module.get_navigation_items()
		for item in items:
			self.assertIn("id", item)
			self.assertIn("label", item)
			self.assertIn("description", item)
			self.assertIn("url", item)
			self.assertIn("doctype", item)


class TestClothingERPHomepageIntegration(unittest.TestCase):
	"""Integration tests run within Frappe site test runner."""

	def test_homepage_context_generation(self):
		"""Verify get_context provides title, subtitle, and navigation items."""
		try:
			import frappe
		except ImportError:
			self.skipTest("Frappe framework not imported in current process")

		clothing_module = import_module("clothing_erp.clothing_erp.www.clothing")
		context = frappe._dict()
		res = clothing_module.get_context(context)
		self.assertEqual(res.title, "Clothing ERP")
		self.assertIn("navigation_items", res)
		self.assertGreaterEqual(len(res.navigation_items), 7)
