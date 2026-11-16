"""Manager-controlled retailer assignment backed by native User Permissions."""

import frappe
from frappe.utils import cint, now_datetime

from clothing_erp.clothing_erp.doctype.retailer_application.retailer_application import (
    _validate_salesperson,
)
from clothing_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from clothing_erp.security import (
    assigned_documents,
    get_current_user,
    get_user_roles,
    require_role,
)
from clothing_erp.supervision import get_supervised_asms, is_active_supervisor

MANAGER_ROLES = {ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}
MAX_BULK_REASSIGNMENTS = 100
MAX_DIRECTORY_PAGE_SIZE = 50


def _is_assignment_admin(user=None):
    user = get_current_user(user)
    roles = get_user_roles(user)
    return (
        user == "Administrator"
        or "System Manager" in roles
        or ROLE_BUSINESS_ADMIN in roles
    )


def _manager_territories(user=None):
    """None means unrestricted admin; an empty list means no manager scope."""
    if _is_assignment_admin(user):
        return None
    return assigned_documents("Territory", user)


def _assert_customer_scope(customer, territory=None):
    territories = _manager_territories()
    if territories is None:
        return
    territory = territory or frappe.db.get_value("Customer", customer, "territory")
    if not territory or territory not in territories:
        frappe.throw(
            frappe._("You are not authorized to manage retailers in this territory."),
            frappe.PermissionError,
        )


def _active_salespeople():
    users = frappe.get_all(
        "Has Role",
        filters={"role": ROLE_SALESPERSON, "parenttype": "User"},
        pluck="parent",
    )
    if not users:
        return []
    users = frappe.get_all(
        "User",
        filters={"name": ["in", users], "enabled": 1, "user_type": "System User"},
        fields=["name", "full_name"],
        order_by="full_name asc, name asc",
    )
    manager_territories = _manager_territories()
    if manager_territories is None:
        return users
    supervised = set(get_supervised_asms(get_current_user()))
    return [
        user
        for user in users
        if user.name in supervised
        and (set(assigned_documents("Territory", user.name)) & set(manager_territories))
    ]


def _assert_salesperson_scope(user, territory):
    if territory not in assigned_documents("Territory", user):
        frappe.throw(
            frappe._("The selected Area Sales Manager is not assigned to this retailer's territory."),
            frappe.PermissionError,
        )
    if not _is_assignment_admin():
        manager = get_current_user()
        if not is_active_supervisor(manager, user):
            frappe.throw(
                frappe._("You can only assign retailers to Area Sales Managers you supervise."),
                frappe.PermissionError,
            )


def _clear_assignment_caches(*users):
    users = tuple(sorted({user for user in users if user}))
    for user in users:
        frappe.clear_cache(user=user)

    def clear_after_commit():
        for user in users:
            frappe.clear_cache(user=user)

    frappe.db.after_commit.add(clear_after_commit)


def _lock_customer(customer):
    frappe.db.sql("SELECT name FROM `tabCustomer` WHERE name = %s FOR UPDATE", customer)
    details = frappe.db.get_value(
        "Customer", customer, ["name", "disabled", "territory"], as_dict=True
    )
    if not details:
        frappe.throw(frappe._("Retailer {0} does not exist.").format(customer))
    if details.disabled:
        frappe.throw(frappe._("A disabled retailer cannot be reassigned."))
    _assert_customer_scope(customer, details.territory)
    return details


def _assignments(customer):
    salespeople = frappe.get_all(
        "Has Role",
        filters={"role": ROLE_SALESPERSON, "parenttype": "User"},
        pluck="parent",
    )
    if not salespeople:
        return []
    return frappe.get_all(
        "User Permission",
        filters={
            "allow": "Customer",
            "for_value": customer,
            "user": ["in", salespeople],
        },
        fields=["name", "user"],
        order_by="creation asc, name asc",
    )


def _single_assignment(customer):
    assignments = _assignments(customer)
    if len(assignments) > 1:
        frappe.throw(
            frappe._(
                "This retailer has multiple legacy salesperson permissions. Resolve the duplicate permissions before reassigning."
            )
        )
    return assignments[0] if assignments else None


@frappe.whitelist()
def get_reassignment_directory(search=None, page=1, page_size=20, match_type="like"):
    """Return only retailers in the manager's native Territory scope."""
    require_role(MANAGER_ROLES)
    page = max(1, min(cint(page), 10_000))
    page_size = max(1, min(cint(page_size), MAX_DIRECTORY_PAGE_SIZE))
    territories = _manager_territories()
    if territories == []:
        return {
            "retailers": [],
            "salespeople": _active_salespeople(),
            "territories": [],
            "pagination": {"page": page, "has_more": False},
            "scope_required": True,
        }

    filters = {"disabled": 0}
    if territories is not None:
        filters["territory"] = ["in", territories]
    search = (search or "").strip()[:140]
    match_type = "=" if match_type == "=" else "like"
    or_filters = None
    if search:
        value = search if match_type == "=" else f"%{search}%"
        or_filters = {
            "name": [match_type, value],
            "customer_name": [match_type, value],
        }
    rows = frappe.get_list(
        "Customer",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "customer_name", "territory"],
        order_by="customer_name asc, name asc",
        start=(page - 1) * page_size,
        limit=page_size + 1,
    )
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    retailers = []
    for row in rows:
        assignment = _single_assignment(row.name)
        retailers.append(
            {
                **row,
                "current_salesperson": assignment.user if assignment else None,
            }
        )
    return {
        "retailers": retailers,
        "salespeople": _active_salespeople(),
        "territories": territories,
        "pagination": {"page": page, "has_more": has_more},
        "scope_required": False,
    }


@frappe.whitelist()
def get_retailer_assignment(customer):
    require_role(MANAGER_ROLES)
    customer = (customer or "").strip()[:140]
    if not customer:
        frappe.throw(frappe._("Select a retailer."))
    if not frappe.db.exists("Customer", customer):
        frappe.throw(frappe._("Retailer {0} does not exist.").format(customer))
    _assert_customer_scope(customer)
    assignment = _single_assignment(customer)
    history = frappe.get_list(
        "Retailer Assignment History",
        filters={"customer": customer},
        fields=[
            "name",
            "previous_salesperson",
            "new_salesperson",
            "reason",
            "changed_by",
            "changed_on",
        ],
        order_by="changed_on desc, creation desc",
        limit=10,
    )
    return {
        "customer": customer,
        "current_salesperson": assignment.user if assignment else None,
        "salespeople": _active_salespeople(),
        "history": history,
    }


@frappe.whitelist(methods=["POST"])
def reassign_retailer(
    customer,
    new_salesperson,
    reason,
    expected_current_salesperson=None,
):
    """Atomically replace one retailer's native salesperson User Permission."""
    require_role(MANAGER_ROLES)
    customer = (customer or "").strip()[:140]
    new_salesperson = (new_salesperson or "").strip()[:140]
    reason = (reason or "").strip()[:500]
    expected_was_supplied = expected_current_salesperson is not None
    expected_current_salesperson = (expected_current_salesperson or "").strip()[
        :140
    ] or None
    if not customer or not new_salesperson:
        frappe.throw(frappe._("Retailer and new Area Sales Manager are required."))
    _validate_salesperson(new_salesperson)
    details = _lock_customer(customer)
    _assert_salesperson_scope(new_salesperson, details.territory)
    assignment = _single_assignment(customer)
    current_salesperson = assignment.user if assignment else None
    if expected_was_supplied and expected_current_salesperson != current_salesperson:
        frappe.throw(
            frappe._(
                "The retailer assignment changed after this form was opened. Refresh and try again."
            )
        )
    if current_salesperson == new_salesperson:
        return {
            "customer": customer,
            "previous_salesperson": current_salesperson,
            "new_salesperson": new_salesperson,
            "unchanged": True,
        }
    if not reason:
        frappe.throw(frappe._("A reassignment reason is required."))
    return _replace_assignment(customer, new_salesperson, reason, assignment)


def _replace_assignment(customer, new_salesperson, reason, assignment):
    current_salesperson = assignment.user if assignment else None
    if assignment:
        frappe.delete_doc(
            "User Permission",
            assignment.name,
            ignore_permissions=True,
        )
    frappe.get_doc(
        {
            "doctype": "User Permission",
            "user": new_salesperson,
            "allow": "Customer",
            "for_value": customer,
            "apply_to_all_doctypes": 1,
        }
    ).insert(ignore_permissions=True)
    history = frappe.get_doc(
        {
            "doctype": "Retailer Assignment History",
            "customer": customer,
            "previous_salesperson": current_salesperson,
            "new_salesperson": new_salesperson,
            "reason": reason,
            "changed_by": get_current_user(),
            "changed_on": now_datetime(),
        }
    )
    history.flags.clothing_assignment_event = True
    history.insert(ignore_permissions=True)
    _clear_assignment_caches(current_salesperson, new_salesperson)
    return {
        "customer": customer,
        "previous_salesperson": current_salesperson,
        "new_salesperson": new_salesperson,
        "history": history.name,
        "unchanged": False,
    }


@frappe.whitelist(methods=["POST"])
def bulk_reassign_retailers(customers, new_salesperson, reason):
    """Atomically reassign a bounded Customer selection after preflighting every row."""
    require_role(MANAGER_ROLES)
    customers = (
        frappe.parse_json(customers) if isinstance(customers, str) else customers
    )
    if not isinstance(customers, (list, tuple)) or not customers:
        frappe.throw(frappe._("Select at least one retailer."))
    if any(
        not isinstance(customer, str) or not customer.strip() for customer in customers
    ):
        frappe.throw(frappe._("The retailer selection is invalid."))
    customers = sorted({customer.strip()[:140] for customer in customers})
    new_salesperson = (new_salesperson or "").strip()[:140]
    reason = (reason or "").strip()[:500]
    if len(customers) > MAX_BULK_REASSIGNMENTS:
        frappe.throw(
            frappe._("You can reassign at most {0} retailers at once.").format(
                MAX_BULK_REASSIGNMENTS
            )
        )
    if not new_salesperson:
        frappe.throw(frappe._("Select a new Area Sales Manager."))
    if not reason:
        frappe.throw(frappe._("A reassignment reason is required."))
    _validate_salesperson(new_salesperson)
    assignments = []
    for customer in customers:
        details = _lock_customer(customer)
        _assert_salesperson_scope(new_salesperson, details.territory)
        assignments.append((customer, _single_assignment(customer)))
    results = [
        (
            {
                "customer": customer,
                "previous_salesperson": assignment.user,
                "new_salesperson": new_salesperson,
                "unchanged": True,
            }
            if assignment and assignment.user == new_salesperson
            else _replace_assignment(customer, new_salesperson, reason, assignment)
        )
        for customer, assignment in assignments
    ]
    return {
        "selected": len(results),
        "changed": sum(not result["unchanged"] for result in results),
        "unchanged": sum(result["unchanged"] for result in results),
        "results": results,
    }
