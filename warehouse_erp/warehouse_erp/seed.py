"""Fictional, idempotent development data for Warehouse ERP manual testing."""

import secrets
import frappe
from warehouse_erp.roles import (
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)

SEED_WAREHOUSE_OPERATOR = "test-warehouse-operator@example.invalid"
SEED_WAREHOUSE_MANAGER = "test-warehouse-manager@example.invalid"


def _ensure_seed_user(email, first_name, role):
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        other_role = ROLE_WAREHOUSE_MANAGER if role == ROLE_WAREHOUSE_OPERATOR else ROLE_WAREHOUSE_OPERATOR
        user.remove_roles(other_role)
        user.add_roles(role)
    else:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "send_welcome_email": 0,
                "user_type": "System User",
                "roles": [{"role": role}],
            }
        ).insert(ignore_permissions=True)
    password = secrets.token_urlsafe(14)
    user.new_password = password
    user.save(ignore_permissions=True)
    return {"email": email, "password": password, "role": role}


def _ensure_user_permission(user, allow, for_value, is_default=False):
    existing = frappe.db.exists(
        "User Permission", {"user": user, "allow": allow, "for_value": for_value}
    )
    if existing:
        return existing
    return frappe.get_doc(
        {
            "doctype": "User Permission",
            "user": user,
            "allow": allow,
            "for_value": for_value,
            "apply_to_all_doctypes": 1,
            "is_default": int(bool(is_default)),
        }
    ).insert(ignore_permissions=True)


def seed_warehouse_data():
    """Provision seed warehouse operator and manager users with warehouse permissions."""
    operator = _ensure_seed_user(SEED_WAREHOUSE_OPERATOR, "TEST Warehouse Operator", ROLE_WAREHOUSE_OPERATOR)
    manager = _ensure_seed_user(SEED_WAREHOUSE_MANAGER, "TEST Warehouse Manager", ROLE_WAREHOUSE_MANAGER)

    warehouses = frappe.get_all("Warehouse", filters={"is_group": 0}, pluck="name")
    if warehouses:
        for wh in warehouses:
            _ensure_user_permission(operator["email"], "Warehouse", wh)
            _ensure_user_permission(manager["email"], "Warehouse", wh)

    return {
        "operator": operator,
        "manager": manager,
    }
