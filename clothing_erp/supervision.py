"""Explicit RSM-to-ASM supervision model with Territory scope and audit history."""

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

from clothing_erp.roles import ROLE_ASM, ROLE_BUSINESS_ADMIN, ROLE_RSM
from clothing_erp.security import (
    assigned_documents,
    get_current_user,
    get_user_roles,
    is_clothing_admin,
    require_role,
)

ADMIN_ROLES = {ROLE_BUSINESS_ADMIN, "System Manager", "Administrator"}


def is_supervision_admin(user=None):
    """Check if user has administrative authority to manage supervision."""
    user = get_current_user(user)
    if not user or user == "Guest":
        return False
    if user == "Administrator":
        return True
    roles = get_user_roles(user)
    return bool(roles & {"System Manager", ROLE_BUSINESS_ADMIN})


def assert_supervision_admin(user=None):
    """Ensure user is an authorized administrator before supervision mutation."""
    if not is_supervision_admin(user):
        frappe.throw(
            frappe._("Only administrators can create or change supervision assignments."),
            frappe.PermissionError,
        )


def validate_asm_user(user):
    """Validate that the user is an enabled System User with the Clothing ASM role."""
    if not user:
        frappe.throw(frappe._("Area Sales Manager is required."))
    details = frappe.db.get_value("User", user, ["name", "enabled", "user_type"], as_dict=True)
    if not details or not details.enabled or details.user_type != "System User":
        frappe.throw(frappe._("The Area Sales Manager must be an enabled System User."))
    roles = set(frappe.get_roles(user))
    if ROLE_ASM not in roles:
        frappe.throw(
            frappe._("The user {0} does not have the Clothing Area Sales Manager role.").format(user)
        )


def validate_rsm_user(user):
    """Validate that the user is an enabled System User with the Clothing RSM role."""
    if not user:
        frappe.throw(frappe._("Regional Sales Manager is required."))
    details = frappe.db.get_value("User", user, ["name", "enabled", "user_type"], as_dict=True)
    if not details or not details.enabled or details.user_type != "System User":
        frappe.throw(frappe._("The Regional Sales Manager must be an enabled System User."))
    roles = set(frappe.get_roles(user))
    if ROLE_RSM not in roles:
        frappe.throw(
            frappe._("The user {0} does not have the Clothing Regional Sales Manager role.").format(user)
        )


def validate_supervision_territories(asm, rsm):
    """Ensure that the ASM and RSM share at least one assigned Territory."""
    asm_territories = set(assigned_documents("Territory", asm))
    rsm_territories = set(assigned_documents("Territory", rsm))
    if not asm_territories:
        frappe.throw(
            frappe._("Area Sales Manager {0} has no assigned territory. Assign territory first.").format(asm),
            frappe.ValidationError,
        )
    if not rsm_territories:
        frappe.throw(
            frappe._("Regional Sales Manager {0} has no assigned territory. Assign territory first.").format(rsm),
            frappe.ValidationError,
        )
    common = asm_territories & rsm_territories
    if not common:
        frappe.throw(
            frappe._(
                "Regional Sales Manager {0} and Area Sales Manager {1} must share at least one assigned Territory."
            ).format(rsm, asm),
            frappe.ValidationError,
        )
    return common


def get_active_supervising_rsm(asm, on_date=None):
    """Return the active supervising RSM user for an ASM on the given date, or None."""
    if not asm:
        return None
    target_date = getdate(on_date or nowdate())
    records = frappe.db.sql(
        """
        SELECT rsm FROM `tabASM Supervision`
        WHERE asm = %s
          AND status = 'Active'
          AND effective_from <= %s
          AND (effective_to IS NULL OR effective_to >= %s)
        ORDER BY effective_from DESC, creation DESC
        LIMIT 1
        """,
        (asm, target_date, target_date),
        as_dict=True,
    )
    return records[0].rsm if records else None


def get_supervised_asms(rsm, on_date=None):
    """Return all active ASMs supervised by an RSM within the RSM's Territory scope."""
    if not rsm:
        return []
    target_date = getdate(on_date or nowdate())
    records = frappe.db.sql(
        """
        SELECT asm FROM `tabASM Supervision`
        WHERE rsm = %s
          AND status = 'Active'
          AND effective_from <= %s
          AND (effective_to IS NULL OR effective_to >= %s)
        ORDER BY asm ASC
        """,
        (rsm, target_date, target_date),
        as_dict=True,
    )
    if not records:
        return []
    rsm_territories = set(assigned_documents("Territory", rsm))
    if not rsm_territories:
        return []
    supervised = []
    for row in records:
        asm_territories = set(assigned_documents("Territory", row.asm))
        if asm_territories & rsm_territories:
            supervised.append(row.asm)
    return supervised


def is_active_supervisor(rsm, asm, on_date=None):
    """Check if an RSM actively supervises an ASM and shares territory on the given date."""
    if not rsm or not asm:
        return False
    active_rsm = get_active_supervising_rsm(asm, on_date=on_date)
    if active_rsm != rsm:
        return False
    rsm_territories = set(assigned_documents("Territory", rsm))
    asm_territories = set(assigned_documents("Territory", asm))
    return bool(rsm_territories & asm_territories)


def assert_rsm_supervises_asm(rsm, asm, territory=None, on_date=None):
    """Raise PermissionError if RSM does not supervise ASM or lacks territory access."""
    active_rsm = get_active_supervising_rsm(asm, on_date=on_date)
    if not active_rsm:
        frappe.throw(
            frappe._(
                "Area Sales Manager {0} has no active supervising Regional Sales Manager. "
                "An administrator must assign supervision before this application can be reviewed."
            ).format(asm),
            frappe.PermissionError,
        )
    if active_rsm != rsm:
        frappe.throw(
            frappe._("You do not supervise Area Sales Manager {0}.").format(asm),
            frappe.PermissionError,
        )
    rsm_territories = set(assigned_documents("Territory", rsm))
    asm_territories = set(assigned_documents("Territory", asm))
    if not (rsm_territories & asm_territories):
        frappe.throw(
            frappe._("You and Area Sales Manager {0} do not share an assigned territory.").format(asm),
            frappe.PermissionError,
        )
    if territory and territory not in rsm_territories:
        frappe.throw(
            frappe._("You are not authorized to manage actions in territory {0}.").format(territory),
            frappe.PermissionError,
        )


@frappe.whitelist(methods=["POST"])
def assign_asm_supervision(asm, rsm, effective_from=None, reason=None):
    """Administrator-controlled service to atomically assign or reassign supervision."""
    assert_supervision_admin()
    asm = (asm or "").strip()
    rsm = (rsm or "").strip()
    reason = (reason or "").strip()[:500]
    validate_asm_user(asm)
    validate_rsm_user(rsm)
    if asm == rsm:
        frappe.throw(frappe._("An Area Sales Manager cannot supervise themselves."))
    validate_supervision_territories(asm, rsm)
    eff_from = getdate(effective_from or nowdate())

    # Lock active records for this ASM to prevent concurrent conflicting assignments
    frappe.db.sql(
        """
        SELECT name FROM `tabASM Supervision`
        WHERE asm = %s AND status = 'Active'
        FOR UPDATE
        """,
        asm,
    )

    current_records = frappe.get_all(
        "ASM Supervision",
        filters={"asm": asm, "status": "Active"},
        fields=["name", "rsm", "effective_from", "effective_to"],
        order_by="effective_from desc",
    )

    # If the active assignment is already for this RSM and starts on or before eff_from
    for cur in current_records:
        if cur.rsm == rsm and cur.effective_from <= eff_from and (not cur.effective_to or cur.effective_to >= eff_from):
            return {
                "name": cur.name,
                "asm": asm,
                "rsm": rsm,
                "effective_from": str(cur.effective_from),
                "unchanged": True,
            }

    # Supersede existing active records whose effective date ranges would overlap
    superseded = []
    for cur in current_records:
        cur_from = getdate(cur.effective_from)
        doc = frappe.get_doc("ASM Supervision", cur.name)
        if cur_from < eff_from:
            doc.effective_to = add_days(eff_from, -1)
        else:
            doc.effective_to = cur_from
        doc.status = "Superseded"
        doc.flags.ignore_permissions = True
        doc.save()
        superseded.append(doc.name)

    # Insert the new active supervision
    new_doc = frappe.get_doc(
        {
            "doctype": "ASM Supervision",
            "asm": asm,
            "rsm": rsm,
            "status": "Active",
            "effective_from": eff_from,
            "effective_to": None,
            "reason": reason or None,
            "assigned_by": get_current_user(),
            "assigned_on": now_datetime(),
        }
    )
    new_doc.flags.ignore_permissions = True
    new_doc.insert()

    frappe.clear_cache(user=asm)
    frappe.clear_cache(user=rsm)

    def _clear_after():
        frappe.clear_cache(user=asm)
        frappe.clear_cache(user=rsm)

    frappe.db.after_commit.add(_clear_after)

    return {
        "name": new_doc.name,
        "asm": asm,
        "rsm": rsm,
        "effective_from": str(eff_from),
        "superseded": superseded,
        "unchanged": False,
    }


@frappe.whitelist(methods=["POST"])
def end_asm_supervision(name, reason=None, end_date=None):
    """End an active supervision record without reassigning."""
    assert_supervision_admin()
    name = (name or "").strip()
    if not frappe.db.exists("ASM Supervision", name):
        frappe.throw(frappe._("Supervision record {0} does not exist.").format(name))

    frappe.db.sql(
        "SELECT name FROM `tabASM Supervision` WHERE name = %s FOR UPDATE",
        name,
    )
    doc = frappe.get_doc("ASM Supervision", name)
    if doc.status != "Active":
        frappe.throw(frappe._("Only active supervision records can be ended."))

    cutoff = getdate(end_date or nowdate())
    if cutoff < getdate(doc.effective_from):
        frappe.throw(frappe._("End date cannot be earlier than Effective From date."))

    doc.effective_to = cutoff
    doc.status = "Cancelled"
    if reason:
        doc.reason = f"{doc.reason or ''}\nEnded: {reason}".strip()
    doc.flags.ignore_permissions = True
    doc.save()

    frappe.clear_cache(user=doc.asm)
    frappe.clear_cache(user=doc.rsm)

    return {
        "name": doc.name,
        "status": doc.status,
        "effective_to": str(doc.effective_to),
    }


@frappe.whitelist()
def get_asm_supervision_directory(search=None, status=None, page=1, page_size=20):
    """Return bounded supervision records, scoped by role and territory."""
    require_role(ADMIN_ROLES | {ROLE_RSM, ROLE_ASM})
    from frappe.utils import cint

    page = max(1, min(cint(page), 10_000))
    page_size = max(1, min(cint(page_size), 50))
    search = (search or "").strip()[:140]

    filters = {}
    if status and status in ("Active", "Superseded", "Cancelled"):
        filters["status"] = status

    or_filters = None
    if search:
        pattern = f"%{search}%"
        or_filters = {
            "name": ["like", pattern],
            "asm": ["like", pattern],
            "rsm": ["like", pattern],
        }

    rows = frappe.get_list(
        "ASM Supervision",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "asm",
            "rsm",
            "status",
            "effective_from",
            "effective_to",
            "reason",
            "assigned_by",
            "assigned_on",
        ],
        order_by="effective_from desc, creation desc",
        start=(page - 1) * page_size,
        limit=page_size + 1,
    )

    has_more = len(rows) > page_size
    return {
        "records": rows[:page_size],
        "pagination": {"page": page, "has_more": has_more},
    }
