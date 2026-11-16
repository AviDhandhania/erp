"""Explicit RSM-to-ASM supervision model with Territory scope and audit history."""

import frappe
from frappe.utils import add_days, getdate, now_datetime, nowdate

from clothing_erp.roles import ROLE_ASM, ROLE_BUSINESS_ADMIN, ROLE_RSM
from clothing_erp.security import (
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


def validate_assignment_territory(asm, rsm, territory):
    """Validate the native Territory selected as the ASM/RSM operating scope."""
    if not territory or not frappe.db.exists("Territory", territory):
        frappe.throw(frappe._("Select an existing Sales Territory."))
    if frappe.db.get_value("Territory", territory, "is_group"):
        frappe.throw(
            frappe._("Assign a leaf Sales Territory to an Area Sales Manager."),
            frappe.ValidationError,
        )


def _ensure_territory_permission(user, territory, make_default=False):
    existing = frappe.db.get_value(
        "User Permission",
        {
            "user": user,
            "allow": "Territory",
            "for_value": territory,
            "applicable_for": ["in", (None, "")],
        },
        "name",
    )
    if existing:
        return existing, False
    is_default = bool(
        make_default
        and not frappe.db.exists(
            "User Permission", {"user": user, "allow": "Territory", "is_default": 1}
        )
    )
    permission = frappe.get_doc(
        {
            "doctype": "User Permission",
            "user": user,
            "allow": "Territory",
            "for_value": territory,
            "apply_to_all_doctypes": 1,
            "is_default": is_default,
        }
    ).insert(ignore_permissions=True)
    return permission.name, True


def sync_assignment_permissions(doc):
    """Materialize one active territory assignment as native User Permissions."""
    asm_permission, asm_managed = _ensure_territory_permission(
        doc.asm, doc.territory, make_default=True
    )
    rsm_permission, rsm_managed = _ensure_territory_permission(doc.rsm, doc.territory)
    values = {
        "asm_user_permission": asm_permission,
        "asm_permission_managed": int(
            bool(doc.get("asm_permission_managed")) or asm_managed
        ),
        "rsm_user_permission": rsm_permission,
        "rsm_permission_managed": int(
            bool(doc.get("rsm_permission_managed")) or rsm_managed
        ),
    }
    frappe.db.set_value("ASM Supervision", doc.name, values, update_modified=False)
    doc.update(values)
    frappe.clear_cache(user=doc.asm)
    frappe.clear_cache(user=doc.rsm)


def _permission_still_required(doc, role_field, user):
    return bool(
        frappe.db.exists(
            "ASM Supervision",
            {
                role_field: user,
                "territory": doc.territory,
                "status": "Active",
                "name": ["!=", doc.name],
            },
        )
    )


def remove_assignment_permissions(doc):
    """Remove only User Permissions created and still owned by this assignment."""
    for role_field, user, permission_field, managed_field in (
        (
            "asm",
            doc.asm,
            "asm_user_permission",
            "asm_permission_managed",
        ),
        (
            "rsm",
            doc.rsm,
            "rsm_user_permission",
            "rsm_permission_managed",
        ),
    ):
        permission = doc.get(permission_field)
        if (
            doc.get(managed_field)
            and permission
            and not _permission_still_required(doc, role_field, user)
            and frappe.db.exists("User Permission", permission)
        ):
            # The technical ownership link must be cleared before Frappe will
            # permit deletion of the app-created User Permission.
            frappe.db.set_value(
                "ASM Supervision",
                doc.name,
                {permission_field: None, managed_field: 0},
                update_modified=False,
            )
            doc.set(permission_field, None)
            doc.set(managed_field, 0)
            frappe.delete_doc("User Permission", permission, ignore_permissions=True)
        frappe.clear_cache(user=user)


def migrate_existing_assignments():
    """Backfill the new Territory field only when legacy data is unambiguous."""
    if not frappe.db.exists("DocType", "ASM Supervision"):
        return
    for row in frappe.get_all(
        "ASM Supervision",
        fields=["name", "asm", "rsm", "territory", "status", "reason"],
    ):
        if row.territory:
            if row.status == "Active":
                sync_assignment_permissions(frappe.get_doc("ASM Supervision", row.name))
            continue
        asm_territories = set(
            frappe.get_all(
                "User Permission",
                filters={"user": row.asm, "allow": "Territory"},
                pluck="for_value",
            )
        )
        rsm_territories = set(
            frappe.get_all(
                "User Permission",
                filters={"user": row.rsm, "allow": "Territory"},
                pluck="for_value",
            )
        )
        common = sorted(asm_territories & rsm_territories)
        if len(common) == 1 and not frappe.db.get_value(
            "Territory", common[0], "is_group"
        ):
            frappe.db.set_value(
                "ASM Supervision", row.name, "territory", common[0], update_modified=False
            )
            if row.status == "Active":
                sync_assignment_permissions(frappe.get_doc("ASM Supervision", row.name))
        else:
            note = "Migration requires an administrator to create a Sales Territory Assignment."
            frappe.db.set_value(
                "ASM Supervision",
                row.name,
                {
                    "status": "Cancelled",
                    "reason": f"{row.reason or ''}\n{note}".strip(),
                },
                update_modified=False,
            )


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
    return [row.asm for row in records]


def is_active_supervisor(rsm, asm, on_date=None):
    """Check if an RSM actively supervises an ASM and shares territory on the given date."""
    if not rsm or not asm:
        return False
    active_rsm = get_active_supervising_rsm(asm, on_date=on_date)
    if active_rsm != rsm:
        return False
    return True


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
    assigned_territory = frappe.db.get_value(
        "ASM Supervision",
        {
            "asm": asm,
            "rsm": rsm,
            "status": "Active",
            "effective_from": ["<=", getdate(on_date or nowdate())],
        },
        "territory",
        order_by="effective_from desc, creation desc",
    )
    if territory and territory != assigned_territory:
        frappe.throw(
            frappe._("You are not authorized to manage actions in territory {0}.").format(territory),
            frappe.PermissionError,
        )


def get_territory_supervision(territory, on_date=None):
    """Return active Area Sales Manager and supervising RSM for a sales territory."""
    if not territory:
        return None
    target_date = getdate(on_date or nowdate())
    records = frappe.db.sql(
        """
        SELECT asm, rsm, territory, effective_from, effective_to
        FROM `tabASM Supervision`
        WHERE territory = %s
          AND status = 'Active'
          AND effective_from <= %s
          AND (effective_to IS NULL OR effective_to >= %s)
        ORDER BY effective_from DESC, creation DESC
        LIMIT 1
        """,
        (territory, target_date, target_date),
        as_dict=True,
    )
    return records[0] if records else None


def record_assignment_history(
    territory,
    new_asm=None,
    previous_asm=None,
    new_rsm=None,
    previous_rsm=None,
    reason=None,
    customer=None,
):
    """Log an immutable territory assignment history event."""
    if not frappe.db.exists("DocType", "Retailer Assignment History"):
        return None
    history = frappe.get_doc(
        {
            "doctype": "Retailer Assignment History",
            "territory": territory,
            "customer": customer,
            "previous_asm": previous_asm,
            "new_asm": new_asm,
            "previous_rsm": previous_rsm,
            "new_rsm": new_rsm,
            "previous_salesperson": previous_asm,
            "new_salesperson": new_asm,
            "reason": (reason or "").strip()
            or ("Territory assignment update" if new_asm else "Assignment ended"),
            "changed_by": get_current_user(),
            "changed_on": now_datetime(),
        }
    )
    history.flags.clothing_assignment_event = True
    history.flags.ignore_permissions = True
    history.insert(ignore_permissions=True)
    return history.name


@frappe.whitelist(methods=["POST"])
def assign_asm_supervision(asm, rsm, territory, effective_from=None, reason=None):
    """Administrator-controlled service to atomically assign or reassign supervision."""
    assert_supervision_admin()
    asm = (asm or "").strip()
    rsm = (rsm or "").strip()
    territory = (territory or "").strip()
    reason = (reason or "").strip()[:500]
    validate_asm_user(asm)
    validate_rsm_user(rsm)
    if asm == rsm:
        frappe.throw(frappe._("An Area Sales Manager cannot supervise themselves."))
    validate_assignment_territory(asm, rsm, territory)
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
        fields=["name", "rsm", "territory", "effective_from", "effective_to"],
        order_by="effective_from desc",
    )
    frappe.db.sql(
        """
        SELECT name FROM `tabASM Supervision`
        WHERE territory = %s AND status = 'Active'
        FOR UPDATE
        """,
        territory,
    )

    # If the active assignment is already for this RSM and starts on or before eff_from
    for cur in current_records:
        if cur.rsm == rsm and cur.territory == territory and cur.effective_from <= eff_from and (not cur.effective_to or cur.effective_to >= eff_from):
            return {
                "name": cur.name,
                "asm": asm,
                "rsm": rsm,
                "territory": territory,
                "effective_from": str(cur.effective_from),
                "unchanged": True,
            }

    # Supersede existing active records whose effective date ranges would overlap
    superseded = []
    prev_asm = None
    prev_rsm = None
    existing_territory_active = frappe.get_all(
        "ASM Supervision",
        filters={"territory": territory, "status": "Active"},
        fields=["asm", "rsm"],
        limit=1,
    )
    if existing_territory_active:
        prev_asm = existing_territory_active[0].asm
        prev_rsm = existing_territory_active[0].rsm
    elif current_records:
        prev_asm = current_records[0].get("asm")
        prev_rsm = current_records[0].get("rsm")

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
            "territory": territory,
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

    record_assignment_history(
        territory=territory,
        new_asm=asm,
        previous_asm=prev_asm,
        new_rsm=rsm,
        previous_rsm=prev_rsm,
        reason=reason,
    )

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
        "territory": territory,
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

    record_assignment_history(
        territory=doc.territory,
        new_asm=None,
        previous_asm=doc.asm,
        new_rsm=None,
        previous_rsm=doc.rsm,
        reason=f"Ended: {reason}" if reason else "Assignment ended",
    )

    frappe.clear_cache(user=doc.asm)
    frappe.clear_cache(user=doc.rsm)

    return {
        "name": doc.name,
        "status": doc.status,
        "effective_to": str(doc.effective_to),
    }


@frappe.whitelist()
def get_territory_assignment_history(territory, limit=10):
    """Return recent assignment history for a territory."""
    require_role(ADMIN_ROLES | {ROLE_RSM, ROLE_ASM})
    from frappe.utils import cint

    territory = (territory or "").strip()
    if not territory:
        return []
    limit = max(1, min(cint(limit), 50))
    return frappe.get_list(
        "Retailer Assignment History",
        filters={"territory": territory},
        fields=[
            "name",
            "territory",
            "previous_asm",
            "new_asm",
            "previous_rsm",
            "new_rsm",
            "reason",
            "changed_by",
            "changed_on",
        ],
        order_by="changed_on desc, creation desc",
        limit=limit,
    )


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
            "territory": ["like", pattern],
        }

    rows = frappe.get_list(
        "ASM Supervision",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "territory",
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
    admin_access = is_clothing_admin()
    current = get_current_user()
    roles = get_user_roles(current)
    if admin_access:
        scope_info = "Administrator scope — all territories"
    elif ROLE_RSM in roles:
        scope_info = "RSM scope — territories of supervised ASMs"
    elif ROLE_ASM in roles:
        scope_info = "ASM scope — assigned territory"
    else:
        scope_info = ""

    return {
        "records": rows[:page_size],
        "pagination": {"page": page, "has_more": has_more},
        "is_admin": admin_access,
        "scope_info": scope_info,
    }


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def sales_role_user_query(doctype, txt, searchfield, start, page_len, filters):
    """Filter enabled System Users possessing the required Clothing ERP sales role."""
    require_role(ADMIN_ROLES | {ROLE_RSM, ROLE_ASM})
    from frappe.utils import cint
    role = (filters or {}).get("role")
    if not role:
        return []

    return frappe.db.sql(
        """
        SELECT DISTINCT `tabUser`.name, `tabUser`.full_name
        FROM `tabUser`
        INNER JOIN `tabHas Role` ON `tabHas Role`.parent = `tabUser`.name
        WHERE `tabHas Role`.role = %(role)s
          AND `tabUser`.enabled = 1
          AND `tabUser`.user_type = 'System User'
          AND (`tabUser`.name LIKE %(txt)s OR `tabUser`.full_name LIKE %(txt)s)
        ORDER BY `tabUser`.name ASC
        LIMIT %(start)s, %(page_len)s
        """,
        {
            "role": role,
            "txt": f"%{txt}%",
            "start": cint(start),
            "page_len": cint(page_len),
        },
        as_list=True,
    )
