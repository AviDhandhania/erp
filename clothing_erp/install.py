"""Installation hooks for the clothing_erp application."""

try:
	import frappe
except ImportError:
	frappe = None

from clothing_erp.roles import ALL_ROLES


def after_install():
	"""Run post-installation steps: set up roles, workspaces, and initial configurations."""
	if not frappe:
		return

	# Provision all Clothing ERP roles
	for role_data in ALL_ROLES:
		role_name = role_data["role_name"]
		if not frappe.db.exists("Role", role_name):
			doc = frappe.get_doc({
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": role_data.get("desk_access", 1),
				"is_custom": 1,
			})
			doc.insert(ignore_permissions=True)


def after_migrate():
	"""Ensure roles and permissions remain up-to-date across migrations."""
	after_install()
