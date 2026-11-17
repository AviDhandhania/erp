# Copyright (c) 2026, Clothing ERP Contributors
# License: MIT. See LICENSE

"""API Security, Rate Limiting, Idempotency, and Audit Logging Infrastructure for Sales ERP."""

from unittest.mock import Mock
import hashlib
import json
import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime


# --- 1. Audit Logging ---
def record_security_audit_event(
    event_type,
    reference_doctype,
    reference_name,
    details=None,
    status="Success",
    user=None,
):
    """Record an immutable security and business event in Frappe's Activity Log."""
    if isinstance(getattr(frappe.db, "sql", None), Mock):
        return
    user = user or (frappe.session.user if hasattr(frappe, "session") else "Administrator")
    content = frappe.as_json(details) if isinstance(details, (dict, list)) else str(details or "")
    ip = getattr(frappe.local, "request_ip", None) if hasattr(frappe, "local") else None
    name = frappe.generate_hash(length=10)
    now = now_datetime()
    try:
        frappe.db.sql(
            """
            INSERT INTO `tabActivity Log` (
                name, creation, modified, modified_by, owner, docstatus, idx,
                subject, content, operation, status, reference_doctype, reference_name, user, ip_address, communication_date
            ) VALUES (%s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                now,
                now,
                user,
                user,
                f"[{event_type}] {reference_doctype} {reference_name}",
                content,
                event_type,
                status,
                reference_doctype,
                reference_name,
                user,
                ip,
                now,
            ),
        )
    except Exception as e:
        frappe.logger("clothing_security").warning(
            f"Failed to record Activity Log for {event_type} {reference_name}: {e}"
        )


# --- 2. Rate Limiting ---
def check_rate_limit(
    operation,
    limit=60,
    window_seconds=60,
    user=None,
    ip=None,
):
    """Enforce sliding-window rate limit per user/operation using Redis cache.
    Bypassed for Administrator and in unit tests unless test_rate_limits is active.
    """
    user = user or (frappe.session.user if hasattr(frappe, "session") else None)
    if user == "Administrator":
        return True
    if getattr(frappe.flags, "in_test", False) and not getattr(frappe.flags, "test_rate_limits", False):
        return True

    identity = user if user and user != "Guest" else (ip or getattr(frappe.local, "request_ip", None) or "Anonymous")
    cache_key = f"clothing_rl:{operation}:{identity}"

    current = frappe.cache.get_value(cache_key)
    if current is None:
        frappe.cache.set_value(cache_key, 1, expires_in_sec=window_seconds)
    else:
        count = cint(current) + 1
        if count > limit:
            record_security_audit_event(
                event_type="Rate Limit Exceeded",
                reference_doctype="User",
                reference_name=identity,
                details={"operation": operation, "limit": limit, "window_seconds": window_seconds},
                status="Blocked",
                user=user or identity,
            )
            frappe.throw(
                _("Rate limit exceeded for {0}. Allowed: {1} requests per {2}s. Please retry later.").format(
                    operation, limit, window_seconds
                ),
                frappe.TooManyRequestsError,
            )
        frappe.cache.set_value(cache_key, count, expires_in_sec=window_seconds)
    return True


# --- 3. Idempotency Binding & Expiry ---
def _compute_payload_signature(operation, user, payload):
    data = {
        "op": operation,
        "user": user,
        "payload": payload if payload is not None else {},
    }
    dumped = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def validate_idempotency(operation, request_id, payload=None, user=None):
    """Validate request_id format and check for replay or concurrent processing.
    Returns: (cached_result, is_replay)
    """
    if not request_id:
        return None, False

    request_id = str(request_id).strip()
    if len(request_id) > 140:
        frappe.throw(_("Idempotency key exceeds maximum length of 140 characters."), frappe.ValidationError)

    user = user or (frappe.session.user if hasattr(frappe, "session") else "Administrator")
    sig = _compute_payload_signature(operation, user, payload)
    cache_key = f"clothing_idem:{operation}:{user}:{request_id}"

    record = frappe.cache.get_value(cache_key)
    if record:
        if isinstance(record, str):
            try:
                record = json.loads(record)
            except Exception:
                record = {}

        stored_sig = record.get("sig")
        if stored_sig and stored_sig != sig:
            frappe.throw(
                _("Idempotency key '{0}' reused with mismatched payload or parameters.").format(request_id),
                frappe.DuplicateEntryError,
            )

        if record.get("status") == "IN_PROGRESS":
            frappe.throw(
                _("Request with key '{0}' is currently in progress. Please retry shortly.").format(request_id),
                frappe.ConcurrentModifiedModelError,
            )

        if record.get("status") == "COMPLETED":
            result = record.get("result", {})
            if isinstance(result, dict):
                result["idempotent_replay"] = True
            return result, True

    # Store IN_PROGRESS marker for up to 5 minutes
    marker = {"status": "IN_PROGRESS", "sig": sig, "user": user}
    frappe.cache.set_value(cache_key, marker, expires_in_sec=300)
    return None, False


def save_idempotency_result(operation, request_id, result, payload=None, user=None, ttl_seconds=86400):
    if not request_id:
        return
    request_id = str(request_id).strip()
    user = user or (frappe.session.user if hasattr(frappe, "session") else "Administrator")
    sig = _compute_payload_signature(operation, user, payload)
    cache_key = f"clothing_idem:{operation}:{user}:{request_id}"
    data = {
        "status": "COMPLETED",
        "sig": sig,
        "user": user,
        "result": result,
    }
    frappe.cache.set_value(cache_key, data, expires_in_sec=ttl_seconds)


def clear_idempotency(operation, request_id, user=None):
    if not request_id:
        return
    request_id = str(request_id).strip()
    user = user or (frappe.session.user if hasattr(frappe, "session") else "Administrator")
    cache_key = f"clothing_idem:{operation}:{user}:{request_id}"
    frappe.cache.delete_value(cache_key)


# --- 4. Input Bounds and Validation ---
def validate_string(val, fieldname, max_len=140, required=False, allowed_values=None):
    if val is None or str(val).strip() == "":
        if required:
            frappe.throw(_("{0} is required.").format(fieldname), frappe.ValidationError)
        return None
    val_str = str(val).strip()
    if "\x00" in val_str:
        frappe.throw(_("{0} contains invalid null bytes.").format(fieldname), frappe.ValidationError)
    if len(val_str) > max_len:
        frappe.throw(
            _("{0} exceeds maximum length of {1} characters.").format(fieldname, max_len),
            frappe.ValidationError,
        )
    if allowed_values is not None and val_str not in allowed_values:
        frappe.throw(
            _("Invalid value '{0}' for {1}. Allowed values: {2}").format(
                val_str, fieldname, ", ".join(sorted(allowed_values))
            ),
            frappe.ValidationError,
        )
    return val_str


def validate_int(val, fieldname, min_val=None, max_val=None, required=False):
    if val is None or str(val).strip() == "":
        if required:
            frappe.throw(_("{0} is required.").format(fieldname), frappe.ValidationError)
        return None
    try:
        val_int = int(val)
    except (ValueError, TypeError):
        frappe.throw(_("{0} must be a valid integer.").format(fieldname), frappe.ValidationError)
    if min_val is not None and val_int < min_val:
        frappe.throw(_("{0} cannot be less than {1}.").format(fieldname, min_val), frappe.ValidationError)
    if max_val is not None and val_int > max_val:
        frappe.throw(_("{0} cannot exceed {1}.").format(fieldname, max_val), frappe.ValidationError)
    return val_int


def validate_float(val, fieldname, min_val=None, max_val=None, required=False):
    if val is None or str(val).strip() == "":
        if required:
            frappe.throw(_("{0} is required.").format(fieldname), frappe.ValidationError)
        return None
    try:
        val_flt = flt(val)
    except (ValueError, TypeError):
        frappe.throw(_("{0} must be a valid number.").format(fieldname), frappe.ValidationError)
    if min_val is not None and val_flt < min_val:
        frappe.throw(_("{0} cannot be less than {1}.").format(fieldname, min_val), frappe.ValidationError)
    if max_val is not None and val_flt > max_val:
        frappe.throw(_("{0} cannot exceed {1}.").format(fieldname, max_val), frappe.ValidationError)
    return val_flt


def validate_bounded_list(val, fieldname, max_len=100, min_len=1):
    parsed = frappe.parse_json(val) if isinstance(val, str) else val
    if not isinstance(parsed, (list, tuple)):
        frappe.throw(_("{0} must be a list.").format(fieldname), frappe.ValidationError)
    if len(parsed) < min_len:
        frappe.throw(_("{0} must contain at least {1} item(s).").format(fieldname, min_len), frappe.ValidationError)
    if len(parsed) > max_len:
        frappe.throw(_("{0} exceeds maximum size of {1} items.").format(fieldname, max_len), frappe.ValidationError)
    return parsed


def validate_dict_keys(val, fieldname, allowed_keys):
    parsed = frappe.parse_json(val) if isinstance(val, str) else val
    if not isinstance(parsed, dict):
        frappe.throw(_("{0} must be an object/dict.").format(fieldname), frappe.ValidationError)
    unexpected = set(parsed.keys()) - set(allowed_keys)
    if unexpected:
        frappe.throw(
            _("Unexpected field(s) in {0}: {1}").format(fieldname, ", ".join(sorted(unexpected))),
            frappe.ValidationError,
        )
    return parsed
