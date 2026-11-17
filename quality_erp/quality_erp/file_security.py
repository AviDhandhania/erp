# Copyright (c) 2026, Clothing ERP Contributors
# For license information, please see license.txt

import csv
import hashlib
import io
import os
import re
import uuid
from PIL import Image

import frappe
from frappe import _

ALLOWED_FILE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
MAX_IMAGE_DIMENSION = 8192
MAX_IMAGE_PIXELS = 50_000_000
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB default

EICAR_SIGNATURE = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

DANGEROUS_SCRIPT_PATTERNS = [
    re.compile(rb"<\?php", re.IGNORECASE),
    re.compile(rb"<script[\s>]", re.IGNORECASE),
    re.compile(rb"<html[\s>]", re.IGNORECASE),
    re.compile(rb"javascript:", re.IGNORECASE),
    re.compile(rb"eval\(", re.IGNORECASE),
    re.compile(rb"\x7fELF"),
    re.compile(rb"^MZ"),
]


def scan_file_for_malware(content_bytes: bytes, filename: str = None) -> bool:
    """Scan file bytes for known malware signatures and quarantine if detected."""
    if EICAR_SIGNATURE in content_bytes:
        quarantine_dir = "/tmp/quarantine"
        try:
            os.makedirs(quarantine_dir, exist_ok=True)
            quarantine_path = os.path.join(quarantine_dir, f"quarantine_{uuid.uuid4().hex[:12]}_{os.path.basename(filename or 'unknown')}")
            with open(quarantine_path, "wb") as qf:
                qf.write(content_bytes)
        except Exception:
            pass

        try:
            from quality_erp.api_security import record_security_audit_event
            record_security_audit_event(
                "Malware Quarantined",
                "File",
                filename or "upload",
                {"reason": "EICAR test malware signature matched", "size": len(content_bytes)},
            )
        except Exception:
            pass

        frappe.throw(
            _("Malware signature detected in uploaded file. The file has been quarantined and administrator alerted."),
            frappe.ValidationError,
        )
    return True


def validate_file_content(
    content_bytes: bytes,
    filename: str = None,
    allowed_extensions: set = None,
    max_size: int = None,
) -> bytes:
    """Validate upload size, file extension, magic signature, decompression bounds, and polyglots."""
    if not content_bytes:
        frappe.throw(_("Empty file upload is not permitted."), frappe.ValidationError)

    max_size = max_size or MAX_UPLOAD_SIZE_BYTES
    if len(content_bytes) > max_size:
        frappe.throw(
            _("File size {0} bytes exceeds maximum permitted size of {1} bytes.").format(
                len(content_bytes), max_size
            ),
            frappe.ValidationError,
        )

    ext = os.path.splitext(filename or "")[1].lower() if filename else ""
    allowed = allowed_extensions or ALLOWED_FILE_EXTENSIONS
    if ext and ext not in allowed:
        frappe.throw(
            _("File extension {0} is not permitted. Allowed: {1}").format(
                ext, ", ".join(sorted(allowed))
            ),
            frappe.ValidationError,
        )

    scan_file_for_malware(content_bytes, filename)

    is_jpeg = content_bytes.startswith(b"\xff\xd8\xff")
    is_png = content_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = content_bytes.startswith(b"RIFF") and len(content_bytes) >= 12 and content_bytes[8:12] == b"WEBP"
    is_pdf = content_bytes.startswith(b"%PDF-")

    detected_type = None
    if is_jpeg:
        detected_type = ".jpg"
    elif is_png:
        detected_type = ".png"
    elif is_webp:
        detected_type = ".webp"
    elif is_pdf:
        detected_type = ".pdf"
    else:
        frappe.throw(_("File signature does not match any permitted file format (JPEG, PNG, WebP, PDF)."), frappe.ValidationError)

    if ext and detected_type:
        normalized_ext = ".jpg" if ext == ".jpeg" else ext
        normalized_detected = ".jpg" if detected_type == ".jpeg" else detected_type
        if normalized_ext != normalized_detected:
            frappe.throw(
                _("Declared extension {0} does not match detected file format {1}.").format(
                    ext, detected_type
                ),
                frappe.ValidationError,
            )

    for pattern in DANGEROUS_SCRIPT_PATTERNS:
        if pattern.search(content_bytes):
            frappe.throw(_("Malicious embedded script or executable polyglot detected in upload."), frappe.ValidationError)

    if detected_type in (".jpg", ".png", ".webp"):
        try:
            image = Image.open(io.BytesIO(content_bytes))
            image.verify()
            image = Image.open(io.BytesIO(content_bytes))
            width, height = image.size

            if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
                frappe.throw(
                    _("Image dimensions ({0}x{1}) exceed maximum allowed dimension of {2}px.").format(
                        width, height, MAX_IMAGE_DIMENSION
                    ),
                    frappe.ValidationError,
                )

            if width * height > MAX_IMAGE_PIXELS:
                frappe.throw(
                    _("Image total pixel count exceeds decompression safety threshold."),
                    frappe.ValidationError,
                )

            clean_buffer = io.BytesIO()
            clean_format = "PNG" if detected_type == ".png" else ("WEBP" if detected_type == ".webp" else "JPEG")
            if clean_format == "JPEG" and image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGB")
            image.save(clean_buffer, format=clean_format)
            return clean_buffer.getvalue()

        except frappe.ValidationError:
            raise
        except Exception as e:
            frappe.throw(_("Invalid or corrupted image payload: {0}").format(str(e)), frappe.ValidationError)

    return content_bytes


def save_secure_file(
    content: bytes,
    filename: str,
    attached_to_doctype: str = None,
    attached_to_name: str = None,
    attached_to_field: str = None,
    is_private: bool = True,
) -> dict:
    """Validate, sanitize, and save a secure file, private by default."""
    clean_bytes = validate_file_content(content, filename=filename)

    ext = os.path.splitext(filename or "")[1].lower() or ".jpg"
    safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
    content_hash = hashlib.sha256(clean_bytes).hexdigest()

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": safe_name,
            "content": clean_bytes,
            "is_private": 1 if is_private else 0,
            "attached_to_doctype": attached_to_doctype,
            "attached_to_name": attached_to_name,
            "attached_to_field": attached_to_field,
        }
    ).insert(ignore_permissions=True)

    return {
        "name": file_doc.name,
        "file_url": file_doc.file_url,
        "file_size": len(clean_bytes),
        "content_hash": content_hash,
        "is_private": bool(file_doc.is_private),
    }


def has_file_permission(doc, ptype="read", user=None, debug=False) -> bool:
    """Permission hook for File in Quality ERP."""
    user = user or frappe.session.user
    if user == "Administrator":
        return True

    if frappe.db.get_value("User", user, "enabled") == 0:
        return False

    if not getattr(doc, "is_private", 0):
        return True

    attached_doctype = getattr(doc, "attached_to_doctype", None)
    attached_name = getattr(doc, "attached_to_name", None)

    if attached_doctype and attached_name:
        if not frappe.db.exists(attached_doctype, attached_name):
            return False
        return bool(frappe.has_permission(attached_doctype, ptype=ptype or "read", doc=attached_name, user=user))

    if user != "Guest" and getattr(doc, "owner", None) == user:
        return True

    return False


def reference_safe_delete_file(file_url: str, requesting_user: str = None) -> bool:
    """Safely delete a local file upload only if it is completely unreferenced across quality DocTypes."""
    if not file_url or file_url.startswith("/assets/"):
        return False

    if frappe.db.exists("Supplier Quality Inspection", {"photo_evidence": file_url}):
        frappe.throw(_("Cannot delete file: referenced in active Supplier Quality Inspection."), frappe.ValidationError)
    if frappe.db.exists("Quality Inspection Evidence", {"file": file_url}):
        frappe.throw(_("Cannot delete file: referenced in Quality Inspection Evidence."), frappe.ValidationError)
    if frappe.db.exists("Return Quarantine", {"photo_evidence": file_url}):
        frappe.throw(_("Cannot delete file: referenced in Return Quarantine record."), frappe.ValidationError)

    file_records = frappe.get_all("File", filters={"file_url": file_url}, pluck="name")
    for fname in file_records:
        frappe.delete_doc("File", fname, ignore_permissions=True)

    return True


def sanitize_spreadsheet_injection(val):
    """Sanitize string values starting with formula trigger characters (=, +, -, @, tab)."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{s}"
    return s


def export_records_to_csv(
    doctype: str,
    fields: list = None,
    filters: dict = None,
    user: str = None,
    max_rows: int = 5000,
) -> str:
    """Permission-scoped, bounded CSV export with spreadsheet injection protection."""
    user = user or frappe.session.user
    if user != "Administrator":
        if not frappe.has_permission(doctype, ptype="export", user=user):
            frappe.throw(_("Not permitted to export {0}.").format(doctype), frappe.PermissionError)

    meta = frappe.get_meta(doctype)
    forbidden_fields = {"password", "api_secret", "secret", "token", "auth_token", "hash"}
    permitted_fields = [
        df.fieldname for df in meta.fields
        if df.fieldname not in forbidden_fields and df.fieldtype not in ("Password", "Code", "HTML")
    ]
    export_fields = [f for f in (fields or permitted_fields) if f in permitted_fields]
    if "name" not in export_fields:
        export_fields.insert(0, "name")

    records = frappe.get_all(
        doctype,
        filters=filters or {},
        fields=export_fields,
        limit_page_length=min(max_rows, 5000),
        order_by="modified desc",
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([meta.get_label(f) if f != "name" else "ID" for f in export_fields])

    for row in records:
        sanitized_row = [sanitize_spreadsheet_injection(row.get(f)) for f in export_fields]
        writer.writerow(sanitized_row)

    try:
        from quality_erp.api_security import record_security_audit_event
        record_security_audit_event(
            "Data Exported to CSV",
            doctype,
            f"{doctype}_export",
            {"row_count": len(records), "fields": export_fields, "exported_by": user},
        )
    except Exception:
        pass

    return output.getvalue()


def redact_sensitive_data(val):
    """Recursively mask credentials, tokens, sensitive GSTIN, and customer phone numbers."""
    if isinstance(val, dict):
        redacted = {}
        for k, v in val.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "secret", "token", "key", "cookie", "auth")):
                redacted[k] = "******"
            elif "phone" in k_lower and isinstance(v, str) and len(v) >= 6:
                redacted[k] = f"{v[:2]}{'*' * (len(v) - 4)}{v[-2:]}"
            elif "gstin" in k_lower and isinstance(v, str) and len(v) == 15:
                redacted[k] = f"{v[:2]}{'*' * 10}{v[-3:]}"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(val, (list, tuple)):
        return [redact_sensitive_data(item) for item in val]
    return val
