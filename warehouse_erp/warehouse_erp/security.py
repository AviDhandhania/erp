"""Server authorization and warehouse assignment restrictions."""
import frappe
from warehouse_erp.roles import (
    ALL_ROLES,
    ROLE_BUSINESS_ADMIN,
    ROLE_WAREHOUSE_MANAGER,
    ROLE_WAREHOUSE_OPERATOR,
)

SUPER_USER_ROLES = {"System Manager", "Administrator"}


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


def is_warehouse_admin(user=None):
    return has_any_role({ROLE_BUSINESS_ADMIN}, user)


def is_warehouse_manager(user=None):
    return has_any_role({ROLE_BUSINESS_ADMIN, ROLE_WAREHOUSE_MANAGER}, user)


def is_warehouse_operator(user=None):
    return has_any_role({ROLE_WAREHOUSE_OPERATOR, ROLE_WAREHOUSE_MANAGER, ROLE_BUSINESS_ADMIN}, user)


def has_warehouse_app_access():
    return has_any_role({r["role_name"] for r in ALL_ROLES})


def assigned_warehouses(user=None):
    """Return permitted warehouses from native User Permissions, including permitted descendants."""
    from frappe.core.doctype.user_permission.user_permission import get_user_permissions
    permissions = get_user_permissions(get_current_user(user)).get("Warehouse", [])
    direct = {p.doc for p in permissions if not p.applicable_for or p.applicable_for == "Warehouse"}
    if not direct:
        return []
    descendants = set(direct)
    to_visit = list(direct)
    while to_visit:
        curr = to_visit.pop(0)
        children = frappe.get_all(
            "Warehouse",
            filters={"parent_warehouse": curr},
            fields=["name", "is_group"],
        )
        for ch in children:
            if ch.name not in descendants:
                descendants.add(ch.name)
                if ch.is_group:
                    to_visit.append(ch.name)
    return sorted(descendants)


def warehouse_has_permission(doc, ptype="read", user=None, **kwargs):
    user = get_current_user(user)
    if is_warehouse_admin(user):
        return True
    if not is_warehouse_operator(user):
        return False
    allowed = assigned_warehouses(user)
    doc_name = doc if isinstance(doc, str) else getattr(doc, "name", None)
    return doc_name in allowed if allowed else False


def pick_list_has_permission(doc, ptype="read", user=None, **kwargs):
    user = get_current_user(user)
    if is_warehouse_admin(user):
        return True
    if not is_warehouse_operator(user):
        return False
    doc_obj = frappe.get_doc("Pick List", doc) if isinstance(doc, str) else doc
    allowed = assigned_warehouses(user)
    if not allowed:
        return False
    parent_wh = doc_obj.get("parent_warehouse") if isinstance(doc_obj, dict) else getattr(doc_obj, "parent_warehouse", None)
    if parent_wh and parent_wh not in allowed:
        return False
    locations = doc_obj.get("locations") if isinstance(doc_obj, dict) else getattr(doc_obj, "locations", [])
    for item in (locations or []):
        wh = item.get("warehouse") if isinstance(item, dict) else getattr(item, "warehouse", None)
        if wh and wh not in allowed:
            return False
    return True


def delivery_note_has_permission(doc, ptype="read", user=None, **kwargs):
    user = get_current_user(user)
    if is_warehouse_admin(user):
        return True
    if not is_warehouse_operator(user):
        return False
    doc_obj = frappe.get_doc("Delivery Note", doc) if isinstance(doc, str) else doc
    allowed = assigned_warehouses(user)
    if not allowed:
        return False
    items = doc_obj.get("items") if isinstance(doc_obj, dict) else getattr(doc_obj, "items", [])
    for item in (items or []):
        wh = item.get("warehouse") if isinstance(item, dict) else getattr(item, "warehouse", None)
        if wh and wh not in allowed:
            return False
    return True


def serial_batch_bundle_has_permission(doc, user=None, ptype=None, **kwargs):
    """Allow bundle mutation only inside the authorized Pick List submit service or for warehouse admin."""
    user = get_current_user(user)
    if is_warehouse_admin(user):
        return True
    if ptype in {"create", "write", "submit", "cancel", "delete"}:
        pick_list = frappe.flags.get("clothing_pick_bundle")
        doc_obj = frappe.get_doc("Serial and Batch Bundle", doc) if isinstance(doc, str) else doc
        return bool(
            pick_list
            and is_warehouse_operator(user)
            and doc_obj
            and doc_obj.get("voucher_type") == "Pick List"
            and doc_obj.get("voucher_no") == pick_list
        )
    return is_warehouse_operator(user)


def get_warehouse_conditions(user=None):
    user = get_current_user(user)
    if is_warehouse_admin(user):
        return ""
    allowed = assigned_warehouses(user)
    if not allowed:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(wh) for wh in allowed)
    return f"`tabWarehouse`.`name` IN ({escaped})"


def get_pick_list_conditions(user=None):
    user = get_current_user(user)
    if is_warehouse_admin(user):
        return ""
    allowed = assigned_warehouses(user)
    if not allowed:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(wh) for wh in allowed)
    return (
        f"EXISTS (SELECT 1 FROM `tabPick List Item` pli "
        f"WHERE pli.parent = `tabPick List`.name AND pli.warehouse IN ({escaped}))"
    )


def get_delivery_note_conditions(user=None):
    user = get_current_user(user)
    if is_warehouse_admin(user):
        return ""
    allowed = assigned_warehouses(user)
    if not allowed:
        return "1=0"
    escaped = ", ".join(frappe.db.escape(wh) for wh in allowed)
    return (
        f"EXISTS (SELECT 1 FROM `tabDelivery Note Item` dni "
        f"WHERE dni.parent = `tabDelivery Note`.name AND dni.warehouse IN ({escaped}))"
    )
