"""Fictional, idempotent development data for Quality ERP manual testing."""

import secrets
import frappe
from quality_erp.roles import (
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)

SEED_QUALITY_INSPECTOR = "test-quality-inspector@example.invalid"
SEED_QUALITY_MANAGER = "test-quality-manager@example.invalid"


def _ensure_seed_user(email, first_name, role):
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        current_roles = set(frappe.get_roles(email))
        if role not in current_roles:
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


def seed_quality_data():
    """Provision seed quality inspector and manager users."""
    inspector = _ensure_seed_user(SEED_QUALITY_INSPECTOR, "TEST Quality Inspector", ROLE_QUALITY_INSPECTOR)
    manager = _ensure_seed_user(SEED_QUALITY_MANAGER, "TEST Quality Manager", ROLE_QUALITY_MANAGER)

    return {
        "inspector": inspector,
        "manager": manager,
    }
