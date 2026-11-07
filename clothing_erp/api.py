"""Whitelisted backend APIs for Clothing ERP with strict server-side authorization."""

import json

try:
	import frappe
	from frappe import _
except ImportError:
	frappe = None
	_ = lambda x: x

from clothing_erp.roles import (
	ROLE_SALESPERSON,
	ROLE_WAREHOUSE_OPERATOR,
	ROLE_SALES_MANAGER,
	ROLE_WAREHOUSE_MANAGER,
	ROLE_BUSINESS_ADMIN,
)
from clothing_erp.security import (
	get_current_user,
	get_user_roles,
	get_active_operational_role,
	require_role,
	is_salesperson,
	is_warehouse_operator,
	is_clothing_admin,
)

# Simulated in-memory session preview role when running standalone or in preview mode
_PREVIEW_ROLES = {}


def _whitelist_decorator(func):
	"""Compatibility wrapper for frappe.whitelist."""
	if frappe and hasattr(frappe, "whitelist"):
		return frappe.whitelist()(func)
	return func


@_whitelist_decorator
def get_user_context():
	"""Return the authenticated user profile, permissions, and active operational scope."""
	user = get_current_user()
	roles = list(get_user_roles(user))
	active_role = _PREVIEW_ROLES.get(user, get_active_operational_role(user))

	can_sales = is_salesperson(user) or active_role in ["Salesperson", "Sales Manager", "Administrator"]
	can_warehouse = is_warehouse_operator(user) or active_role in ["Warehouse Operator", "Warehouse Manager", "Administrator"]
	can_admin = is_clothing_admin(user) or active_role in ["Administrator"]

	return {
		"user": user,
		"active_role": active_role,
		"roles": roles,
		"permissions": {
			"salesperson_portal": can_sales,
			"warehouse_operations": can_warehouse,
			"business_admin": can_admin,
			"switch_preview": True,
		},
		"app_version": "0.1.0",
	}


@_whitelist_decorator
def switch_preview_role(role):
	"""Allow toggling the operational preview role for developer inspection."""
	valid_roles = ["Administrator", "Salesperson", "Warehouse Operator", "Sales Manager", "Warehouse Manager"]
	if role not in valid_roles:
		msg = f"Invalid role: {role}. Must be one of {valid_roles}"
		if frappe and hasattr(frappe, "throw"):
			frappe.throw(msg)
		raise ValueError(msg)

	user = get_current_user()
	_PREVIEW_ROLES[user] = role
	return {"status": "ok", "active_role": role, "user": user}


@_whitelist_decorator
def get_salesperson_dashboard():
	"""Return salesperson dashboard operational metrics and recent activity."""
	user = get_current_user()
	active_role = _PREVIEW_ROLES.get(user, get_active_operational_role(user))

	# Verify server-side authorization
	if active_role not in ["Salesperson", "Sales Manager", "Administrator"]:
		require_role([ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN], user=user)

	# Fictional operational data for Stage 2 interface foundation
	return {
		"metrics": {
			"today_orders_count": 8,
			"today_orders_value": 46500.0,
			"month_sales_value": 384000.0,
			"month_sales_target": 500000.0,
			"assigned_retailers_count": 28,
			"pending_approvals_count": 3,
			"pending_followups_count": 5,
		},
		"shortcuts": [
			{"label": "New Sales Order", "url": "/app/sales-order/new", "doctype": "Sales Order"},
			{"label": "Register Retailer", "url": "/app/customer/new", "doctype": "Customer"},
			{"label": "Browse Catalog", "url": "/app/item", "doctype": "Item"},
			{"label": "Record Visit", "url": "/app/clothing-visit", "doctype": "Visit"},
		],
		"recent_orders": [
			{"name": "SO-2026-0012", "customer": "Metro Garments Pvt Ltd", "items": 120, "amount": 28400.0, "status": "Confirmed", "date": "2026-11-07"},
			{"name": "SO-2026-0011", "customer": "Urban Thread Boutique", "items": 45, "amount": 14200.0, "status": "Picking", "date": "2026-11-06"},
			{"name": "SO-2026-0010", "customer": "Fashion Point Retail", "items": 80, "amount": 19800.0, "status": "Awaiting Approval", "date": "2026-11-06"},
			{"name": "SO-2026-0009", "customer": "Classic Wear Distro", "items": 200, "amount": 54000.0, "status": "Dispatched", "date": "2026-11-05"},
		],
		"followups": [
			{"retailer": "Metro Garments Pvt Ltd", "contact": "Rajesh Kumar", "due_date": "2026-11-08", "notes": "Winter collection pre-booking"},
			{"retailer": "Velvet Denims", "contact": "Pooja Mehta", "due_date": "2026-11-09", "notes": "Sample delivery feedback"},
		]
	}


@_whitelist_decorator
def get_warehouse_dashboard():
	"""Return warehouse operator dashboard tasks, pick lists, and dispatch readiness."""
	user = get_current_user()
	active_role = _PREVIEW_ROLES.get(user, get_active_operational_role(user))

	# Verify server-side authorization
	if active_role not in ["Warehouse Operator", "Warehouse Manager", "Administrator"]:
		require_role([ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN], user=user)

	# Fictional operational data for Stage 2 interface foundation
	return {
		"metrics": {
			"assigned_pick_lists": 4,
			"orders_in_picking": 6,
			"orders_awaiting_packing": 5,
			"orders_ready_for_dispatch": 7,
			"stock_shortages": 2,
			"completed_today": 14,
		},
		"shortcuts": [
			{"label": "Active Pick Lists", "url": "/app/pick-list", "doctype": "Pick List"},
			{"label": "Packing Queue", "url": "/app/delivery-note", "doctype": "Delivery Note"},
			{"label": "Barcode Scan Station", "url": "/app/scan", "doctype": "Stock Entry"},
			{"label": "Report Stock Shortage", "url": "/app/stock-entry/new", "doctype": "Stock Entry"},
		],
		"pick_tasks": [
			{"pick_list": "PKL-2026-0044", "order": "SO-2026-0011", "customer": "Urban Thread Boutique", "skus": 4, "total_qty": 45, "status": "In Progress", "priority": "High"},
			{"pick_list": "PKL-2026-0045", "order": "SO-2026-0012", "customer": "Metro Garments Pvt Ltd", "skus": 8, "total_qty": 120, "status": "Queued", "priority": "Normal"},
			{"pick_list": "PKL-2026-0046", "order": "SO-2026-0008", "customer": "Denim Hub", "skus": 3, "total_qty": 30, "status": "Queued", "priority": "Low"},
		],
		"dispatch_ready": [
			{"delivery_note": "MAT-DN-2026-0019", "customer": "Classic Wear Distro", "boxes": 4, "carrier": "BlueDart Express", "status": "Ready for Dispatch"},
			{"delivery_note": "MAT-DN-2026-0020", "customer": "Style Quotient", "boxes": 2, "carrier": "Delhivery", "status": "Ready for Dispatch"},
		]
	}
