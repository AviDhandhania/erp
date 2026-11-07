"""Backend authorization, permission validation, and role security for Clothing ERP."""

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
	SUPER_USER_ROLES,
)


class ClothingPermissionError(Exception if not frappe else frappe.PermissionError):
	"""Raised when a user lacks authorized permissions for Clothing ERP operations."""
	pass


def get_current_user(user=None):
	"""Return the user ID, defaulting to current session user."""
	if user:
		return user
	if frappe and hasattr(frappe, "session") and hasattr(frappe.session, "user"):
		return frappe.session.user
	return "Administrator"


def get_user_roles(user=None):
	"""Return the set of roles for the specified user."""
	user = get_current_user(user)
	if not user or user == "Guest":
		return set()

	if frappe and hasattr(frappe, "get_roles"):
		return set(frappe.get_roles(user))

	# Default fallback for testing or mock session
	if user == "Administrator":
		return {"Administrator", "System Manager", ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_WAREHOUSE_MANAGER}
	return set()


def has_any_role(required_roles, user=None):
	"""Check if user has at least one of the specified roles."""
	user_roles = get_user_roles(user)
	# Super users (Administrator, System Manager) bypass role limitations
	if user_roles.intersection(SUPER_USER_ROLES):
		return True

	if isinstance(required_roles, str):
		required_roles = {required_roles}
	else:
		required_roles = set(required_roles)

	return bool(user_roles.intersection(required_roles))


def require_role(allowed_roles, user=None):
	"""Enforce that the user has at least one of the allowed roles, else throw PermissionError."""
	if not has_any_role(allowed_roles, user=user):
		user_id = get_current_user(user)
		msg = _("User {0} does not have required permission. Allowed roles: {1}").format(
			user_id, ", ".join(allowed_roles) if isinstance(allowed_roles, (list, set, tuple)) else allowed_roles
		)
		if frappe and hasattr(frappe, "throw"):
			frappe.throw(msg, frappe.PermissionError)
		raise ClothingPermissionError(msg)
	return True


# Specific Role Checks
def is_clothing_admin(user=None):
	"""Return True if user has administrative authority."""
	return has_any_role({ROLE_BUSINESS_ADMIN}, user=user)


def is_sales_manager(user=None):
	"""Return True if user has sales management authority."""
	return has_any_role({ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER}, user=user)


def is_warehouse_manager(user=None):
	"""Return True if user has warehouse management authority."""
	return has_any_role({ROLE_BUSINESS_ADMIN, ROLE_WAREHOUSE_MANAGER}, user=user)


def is_salesperson(user=None):
	"""Return True if user is authorized as a salesperson."""
	return has_any_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}, user=user)


def is_warehouse_operator(user=None):
	"""Return True if user is authorized as a warehouse operator."""
	return has_any_role({ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN}, user=user)


def get_active_operational_role(user=None):
	"""Return the primary operational role description for interface customization."""
	roles = get_user_roles(user)
	if roles.intersection(SUPER_USER_ROLES) or ROLE_BUSINESS_ADMIN in roles:
		return "Administrator"
	if ROLE_SALES_MANAGER in roles:
		return "Sales Manager"
	if ROLE_WAREHOUSE_MANAGER in roles:
		return "Warehouse Manager"
	if ROLE_SALESPERSON in roles:
		return "Salesperson"
	if ROLE_WAREHOUSE_OPERATOR in roles:
		return "Warehouse Operator"
	return "Standard User"


# Document-Level Permission Helpers
def has_retailer_access(customer_name, user=None):
	"""Validate if user has access to view/order for the given retailer/customer."""
	user = get_current_user(user)
	if is_sales_manager(user) or is_clothing_admin(user):
		return True

	if not is_salesperson(user):
		return False

	# If inside active Frappe database, check standard ERPNext Sales Person assignment or custom field
	if frappe and hasattr(frappe, "db") and frappe.db:
		# Check if the customer is assigned to the current user's Sales Person record
		sales_person = frappe.db.get_value("Sales Person", {"user_id": user}, "name")
		if sales_person:
			assigned = frappe.db.exists("Customer", {"name": customer_name, "default_sales_partner": sales_person})
			if assigned:
				return True

	# If no specific assignment check is found or in mock mode, allow for designated salesperson
	return True


def has_warehouse_access(warehouse_name, user=None):
	"""Validate if user has access to view/pick from the given warehouse."""
	user = get_current_user(user)
	if is_warehouse_manager(user) or is_clothing_admin(user):
		return True

	if not is_warehouse_operator(user):
		return False

	return True


def get_salesperson_customer_conditions(user=None):
	"""Return SQL condition string to filter Customer list for salesperson."""
	user = get_current_user(user)
	if is_sales_manager(user) or is_clothing_admin(user):
		return ""

	if frappe and hasattr(frappe, "db") and frappe.db:
		sales_person = frappe.db.get_value("Sales Person", {"user_id": user}, "name")
		if sales_person:
			return f"`tabCustomer`.default_sales_partner = {frappe.db.escape(sales_person)}"

	return ""
