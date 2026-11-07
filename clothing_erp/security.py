"""Server authorization and assignment restrictions, alongside native permissions."""
import frappe
from clothing_erp.roles import (
    ALL_ROLES, ROLE_BUSINESS_ADMIN, ROLE_SALESPERSON, ROLE_SALES_MANAGER,
    ROLE_WAREHOUSE_MANAGER, ROLE_WAREHOUSE_OPERATOR, SUPER_USER_ROLES,
)
ClothingPermissionError = frappe.PermissionError

def get_current_user(user=None):
    return user or frappe.session.user

def get_user_roles(user=None):
    user = get_current_user(user)
    return set(frappe.get_roles(user)) if user and user != "Guest" else set()

def has_any_role(required_roles, user=None):
    if get_current_user(user) == "Administrator":
        return True
    required = {required_roles} if isinstance(required_roles, str) else set(required_roles)
    return bool(get_user_roles(user) & (required | SUPER_USER_ROLES))

def require_role(allowed_roles, user=None):
    if not has_any_role(allowed_roles, user):
        frappe.throw(frappe._("You do not have permission to access this operation."), frappe.PermissionError)
    return True

def is_clothing_admin(user=None):
    return has_any_role({ROLE_BUSINESS_ADMIN}, user)

def is_sales_manager(user=None):
    return has_any_role({ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER}, user)

def is_warehouse_manager(user=None):
    return has_any_role({ROLE_BUSINESS_ADMIN, ROLE_WAREHOUSE_MANAGER}, user)

def is_salesperson(user=None):
    return has_any_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}, user)

def is_warehouse_operator(user=None):
    return has_any_role({ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN}, user)

def has_app_access():
    return has_any_role({r["role_name"] for r in ALL_ROLES})

def get_active_operational_role(user=None):
    for check, label in ((is_clothing_admin, "Administrator"), (is_sales_manager, "Sales Manager"),
                         (is_warehouse_manager, "Warehouse Manager"), (is_salesperson, "Salesperson"),
                         (is_warehouse_operator, "Warehouse Operator")):
        if check(user):
            return label
    return "Standard User"

def assigned_documents(doctype, user=None, applicable_for=None):
    """Native User Permissions include permitted warehouse descendants."""
    from frappe.core.doctype.user_permission.user_permission import get_user_permissions
    permissions = get_user_permissions(get_current_user(user)).get(doctype, [])
    return sorted({p.doc for p in permissions if not p.applicable_for or p.applicable_for == (applicable_for or doctype)})

def has_retailer_access(customer_name, user=None):
    return is_sales_manager(user) or (is_salesperson(user) and customer_name in assigned_documents("Customer", user))

def has_warehouse_access(warehouse_name, user=None):
    return is_warehouse_manager(user) or (is_warehouse_operator(user) and warehouse_name in assigned_documents("Warehouse", user))

def customer_has_permission(doc, user=None, ptype=None, **kwargs):
    if ROLE_SALESPERSON not in get_user_roles(user) or is_sales_manager(user):
        return True
    return has_retailer_access(doc.name, user)

def warehouse_has_permission(doc, user=None, ptype=None, **kwargs):
    if ROLE_WAREHOUSE_OPERATOR not in get_user_roles(user) or is_warehouse_manager(user):
        return True
    return has_warehouse_access(doc.name, user)

def _assignment_conditions(doctype, role, manager_check, user):
    if role not in get_user_roles(user) or manager_check(user):
        return ""
    names = assigned_documents(doctype, user)
    if not names:
        return "1=0"
    return f"`tab{doctype}`.`name` in ({', '.join(frappe.db.escape(n) for n in names)})"

def get_salesperson_customer_conditions(user=None):
    return _assignment_conditions("Customer", ROLE_SALESPERSON, is_sales_manager, user)

def get_operator_warehouse_conditions(user=None):
    return _assignment_conditions("Warehouse", ROLE_WAREHOUSE_OPERATOR, is_warehouse_manager, user)


def _sales_document_conditions(doctype, user=None):
    if ROLE_SALESPERSON not in get_user_roles(user) or is_sales_manager(user):
        return ""
    names = assigned_documents("Customer", user)
    return f"`tab{doctype}`.`customer` in ({', '.join(frappe.db.escape(n) for n in names)})" if names else "1=0"


def _warehouse_document_conditions(doctype, user=None):
    if ROLE_WAREHOUSE_OPERATOR not in get_user_roles(user) or is_warehouse_manager(user):
        return ""
    names = assigned_documents("Warehouse", user)
    if not names:
        return "1=0"
    allowed = ', '.join(frappe.db.escape(n) for n in names)
    child, field = ("Pick List Item", "locations") if doctype == "Pick List" else ("Delivery Note Item", "items")
    relation = f"clothing_line.parent = `tab{doctype}`.name AND clothing_line.parenttype = {frappe.db.escape(doctype)} AND clothing_line.parentfield = {frappe.db.escape(field)}"
    # Reject mixed-warehouse documents as well as documents without a warehouse.
    conditions = f"EXISTS (SELECT 1 FROM `tab{child}` clothing_line WHERE {relation}) AND NOT EXISTS (SELECT 1 FROM `tab{child}` clothing_line WHERE {relation} AND (clothing_line.warehouse IS NULL OR clothing_line.warehouse NOT IN ({allowed})))"
    if doctype == "Pick List":
        conditions += f" AND EXISTS (SELECT 1 FROM `tabToDo` task WHERE task.reference_type = 'Pick List' AND task.reference_name = `tabPick List`.name AND task.allocated_to = {frappe.db.escape(get_current_user(user))} AND task.status = 'Open')"
    return conditions


def sales_order_conditions(user=None):
    return _sales_document_conditions("Sales Order", user)


def delivery_note_conditions(user=None):
    return " AND ".join(f"({c})" for c in (_sales_document_conditions("Delivery Note", user), _warehouse_document_conditions("Delivery Note", user)) if c)


def pick_list_conditions(user=None):
    return _warehouse_document_conditions("Pick List", user)


def operational_document_has_permission(doc, user=None, ptype=None, **kwargs):
    roles = get_user_roles(user)
    if doc.doctype in ("Sales Order", "Delivery Note") and ROLE_SALESPERSON in roles and not is_sales_manager(user):
        if not has_retailer_access(doc.get("customer"), user):
            return False
    if doc.doctype in ("Pick List", "Delivery Note") and ROLE_WAREHOUSE_OPERATOR in roles and not is_warehouse_manager(user):
        rows = doc.get("locations" if doc.doctype == "Pick List" else "items") or []
        if not rows or not all(has_warehouse_access(row.warehouse, user) for row in rows):
            return False
        if doc.doctype == "Pick List":
            return bool(frappe.db.exists("ToDo", {"reference_type": "Pick List", "reference_name": doc.name, "allocated_to": get_current_user(user), "status": "Open"}))
    return True
