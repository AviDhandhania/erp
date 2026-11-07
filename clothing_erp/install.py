"""Installation hooks for the clothing_erp application."""

import frappe


def after_install():
	"""Run post-installation steps: set up roles and permissions."""
	role_name = "Clothing ERP User"
	if not frappe.db.exists("Role", role_name):
		frappe.get_doc({
			"doctype": "Role",
			"role_name": role_name,
			"desk_access": 1,
			"is_custom": 1,
		}).insert(ignore_permissions=True)
