"""Clothing ERP portal homepage context provider."""

import frappe
from frappe import _


def get_navigation_items():
	"""Return the core navigation placeholders for Clothing ERP."""
	return [
		{
			"id": "admin",
			"label": _("Admin"),
			"description": _("User permissions, system settings, and ERP configuration."),
			"url": "/app/user",
			"doctype": "User",
			"icon": "shield-check",
			"badge": _("Foundation"),
		},
		{
			"id": "products",
			"label": _("Products"),
			"description": _("Garment catalog, styles, sizes, color variants, and pricing."),
			"url": "/app/item",
			"doctype": "Item",
			"icon": "tag",
			"badge": _("Catalog"),
		},
		{
			"id": "sales",
			"label": _("Sales"),
			"description": _("Wholesale distribution orders, quotations, and invoicing."),
			"url": "/app/sales-order",
			"doctype": "Sales Order",
			"icon": "shopping-cart",
			"badge": _("Distribution"),
		},
		{
			"id": "retailers",
			"label": _("Retailers"),
			"description": _("Boutique and chain retail partners, credit limits, and territories."),
			"url": "/app/customer",
			"doctype": "Customer",
			"icon": "users",
			"badge": _("Partners"),
		},
		{
			"id": "warehouse",
			"label": _("Warehouse"),
			"description": _("Inventory balances, picking lists, packing, and stock movements."),
			"url": "/app/stock-entry",
			"doctype": "Stock Entry",
			"icon": "archive",
			"badge": _("Inventory"),
		},
		{
			"id": "suppliers",
			"label": _("Suppliers"),
			"description": _("Garment manufacturers, fabric mills, trim suppliers, and POs."),
			"url": "/app/supplier",
			"doctype": "Supplier",
			"icon": "truck",
			"badge": _("Procurement"),
		},
		{
			"id": "reports",
			"label": _("Reports"),
			"description": _("Distribution analytics, sell-through rates, and stock valuation."),
			"url": "/app/query-report",
			"doctype": "Report",
			"icon": "bar-chart-2",
			"badge": _("Analytics"),
		},
	]


def get_context(context):
	"""Populate context for the Clothing ERP homepage."""
	user = frappe.session.user
	is_authenticated = user and user != "Guest"

	context.title = _("Clothing ERP")
	context.subtitle = _("Open-Source Clothing Distribution ERP")
	context.no_cache = 1
	context.no_sidebar = 1
	context.is_authenticated = is_authenticated
	context.current_user = user

	all_items = get_navigation_items()

	if is_authenticated:
		roles = set(frappe.get_roles(user))
		is_admin = user == "Administrator" or "System Manager" in roles or "Clothing ERP User" in roles
		# Filter links by read permission if authenticated, Administrator sees all
		if is_admin:
			context.navigation_items = all_items
		else:
			context.navigation_items = [
				item for item in all_items
				if frappe.has_permission(item["doctype"], "read")
			]
	else:
		# For guest visitors, show all navigation placeholders as a preview with login guidance
		context.navigation_items = all_items

	return context
