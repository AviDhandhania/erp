"""Unit and integration tests for Clothing ERP roles and permissions."""

import unittest
from clothing_erp.roles import (
	ROLE_SALESPERSON,
	ROLE_WAREHOUSE_OPERATOR,
	ROLE_SALES_MANAGER,
	ROLE_WAREHOUSE_MANAGER,
	ROLE_BUSINESS_ADMIN,
	ALL_ROLES,
	MANAGEMENT_ROLES,
	OPERATIONAL_ROLES,
)
from clothing_erp.security import (
	has_any_role,
	require_role,
	is_salesperson,
	is_warehouse_operator,
	is_sales_manager,
	is_warehouse_manager,
	is_clothing_admin,
	has_retailer_access,
	has_warehouse_access,
	get_salesperson_customer_conditions,
	ClothingPermissionError,
)


class TestClothingRolesAndSecurity(unittest.TestCase):
	"""Test role definitions, backend authorization checks, and access boundaries."""

	def test_roles_definition(self):
		"""Verify all 5 core roles are defined with required metadata."""
		role_names = {r["role_name"] for r in ALL_ROLES}
		expected = {
			ROLE_SALESPERSON,
			ROLE_WAREHOUSE_OPERATOR,
			ROLE_SALES_MANAGER,
			ROLE_WAREHOUSE_MANAGER,
			ROLE_BUSINESS_ADMIN,
		}
		self.assertEqual(expected, role_names)
		for r in ALL_ROLES:
			self.assertIn("desk_access", r)
			self.assertIn("description", r)
			self.assertIn("home_page", r)

	def test_administrator_super_user_access(self):
		"""Administrator must have universal access across all operational modules."""
		self.assertTrue(is_clothing_admin("Administrator"))
		self.assertTrue(is_sales_manager("Administrator"))
		self.assertTrue(is_warehouse_manager("Administrator"))
		self.assertTrue(is_salesperson("Administrator"))
		self.assertTrue(is_warehouse_operator("Administrator"))
		self.assertTrue(require_role([ROLE_SALESPERSON], user="Administrator"))
		self.assertTrue(require_role([ROLE_WAREHOUSE_OPERATOR], user="Administrator"))

	def test_unauthorized_user_rejection(self):
		"""Unauthorized users must be rejected by require_role."""
		unauthorized_user = "guest_or_stranger@example.invalid"
		with self.assertRaises((ClothingPermissionError, Exception)):
			require_role([ROLE_SALESPERSON], user=unauthorized_user)

		with self.assertRaises((ClothingPermissionError, Exception)):
			require_role([ROLE_WAREHOUSE_OPERATOR], user=unauthorized_user)

	def test_retailer_and_warehouse_access_helpers(self):
		"""Test document-level authorization helpers."""
		# Administrator has access
		self.assertTrue(has_retailer_access("CUST-0001", user="Administrator"))
		self.assertTrue(has_warehouse_access("Stores - CE", user="Administrator"))

		# Non-salesperson / guest cannot access retailer
		self.assertFalse(has_retailer_access("CUST-0001", user="random_user@example.invalid"))
		self.assertFalse(has_warehouse_access("Stores - CE", user="random_user@example.invalid"))

	def test_customer_query_conditions_manager_bypass(self):
		"""Sales managers and admins should not have query filter conditions applied."""
		conditions = get_salesperson_customer_conditions(user="Administrator")
		self.assertEqual(conditions, "")
