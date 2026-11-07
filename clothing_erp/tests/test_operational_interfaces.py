"""Tests for operational APIs, dashboard metrics, and workspace definitions."""

import json
import os
import unittest
import frappe
from clothing_erp.api import (
	get_user_context,
	switch_preview_role,
	get_salesperson_dashboard,
	get_warehouse_dashboard,
)


class TestOperationalInterfaces(unittest.TestCase):
	"""Test operational APIs and Frappe workspace definitions."""

	def test_get_user_context(self):
		"""Verify user context returns valid operational permissions."""
		ctx = get_user_context()
		self.assertIn("user", ctx)
		self.assertIn("active_role", ctx)
		self.assertIn("permissions", ctx)
		self.assertTrue(ctx["permissions"]["salesperson_portal"])
		self.assertTrue(ctx["permissions"]["warehouse_operations"])

	def test_role_switch_validation(self):
		"""Verify preview role switching enforces valid operational roles."""
		res = switch_preview_role("Salesperson")
		self.assertEqual(res["active_role"], "Salesperson")

		res2 = switch_preview_role("Warehouse Operator")
		self.assertEqual(res2["active_role"], "Warehouse Operator")

		# Switch back to Administrator
		switch_preview_role("Administrator")

		with self.assertRaises((ValueError, frappe.ValidationError)):
			switch_preview_role("InvalidNonexistentRole")

	def test_salesperson_dashboard_payload(self):
		"""Verify salesperson dashboard returns expected metrics and structure."""
		switch_preview_role("Salesperson")
		try:
			data = get_salesperson_dashboard()
			self.assertIn("metrics", data)
			self.assertIn("today_orders_count", data["metrics"])
			self.assertIn("assigned_retailers_count", data["metrics"])
			self.assertIn("recent_orders", data)
			self.assertIn("shortcuts", data)
			self.assertGreater(len(data["recent_orders"]), 0)
		finally:
			switch_preview_role("Administrator")

	def test_warehouse_dashboard_payload(self):
		"""Verify warehouse dashboard returns expected tasks and dispatch readiness."""
		switch_preview_role("Warehouse Operator")
		try:
			data = get_warehouse_dashboard()
			self.assertIn("metrics", data)
			self.assertIn("assigned_pick_lists", data["metrics"])
			self.assertIn("orders_ready_for_dispatch", data["metrics"])
			self.assertIn("pick_tasks", data)
			self.assertIn("dispatch_ready", data)
			self.assertGreater(len(data["pick_tasks"]), 0)
		finally:
			switch_preview_role("Administrator")

	def test_workspace_json_definitions_exist(self):
		"""Verify workspace JSON definitions for Desk are valid JSON."""
		test_dir = os.path.dirname(os.path.abspath(__file__))
		workspace_dir = os.path.abspath(os.path.join(test_dir, "..", "clothing_erp", "workspace"))

		workspaces = [
			("clothing_erp", "clothing_erp.json"),
			("salesperson_portal", "salesperson_portal.json"),
			("warehouse_operations", "warehouse_operations.json"),
		]

		for ws_folder, ws_file in workspaces:
			path = os.path.join(workspace_dir, ws_folder, ws_file)
			self.assertTrue(os.path.exists(path), f"Workspace file missing: {path}")
			with open(path, "r", encoding="utf-8") as f:
				data = json.load(f)
				self.assertEqual(data.get("doctype"), "Workspace")
				self.assertIn("label", data)
				self.assertIn("roles", data)
