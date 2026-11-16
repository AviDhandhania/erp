"""Lifecycle management for Item gallery uploads owned by the Frappe site."""

import frappe

LOCAL_FILE_PREFIXES = ("/files/", "/private/files/")
GALLERY_ATTACHMENT_FIELDS = ("image", "custom_clothing_product_images")


def _gallery_urls(doc):
    return {
        row.image
        for row in (doc.get("custom_clothing_product_images") or [])
        if row.image
    }


def _is_local_upload(file_url):
    return bool(file_url and file_url.startswith(LOCAL_FILE_PREFIXES))


def _is_referenced(file_url):
    """Protect files still used as a primary image or in any product gallery."""
    return bool(
        frappe.db.exists("Item", {"image": file_url})
        or frappe.db.exists("Clothing Product Image", {"image": file_url})
    )


def _delete_orphan(file_url, item_name=None):
    if not _is_local_upload(file_url) or _is_referenced(file_url):
        return 0

    filters = {
        "file_url": file_url,
        "attached_to_doctype": "Item",
        "attached_to_field": ["in", GALLERY_ATTACHMENT_FIELDS],
    }
    if item_name:
        filters["attached_to_name"] = item_name

    file_names = frappe.get_all("File", filters=filters, pluck="name")
    for file_name in file_names:
        frappe.delete_doc("File", file_name, ignore_permissions=True)
    return len(file_names)


def cleanup_removed_gallery_files(doc, method=None):
    """Delete unreferenced local uploads after gallery rows are removed and saved."""
    previous = doc.get_doc_before_save()
    if not previous:
        return

    for file_url in _gallery_urls(previous) - _gallery_urls(doc):
        _delete_orphan(file_url, item_name=doc.name)


def cleanup_orphan_gallery_files(limit=500):
    """Conservative scheduled sweep for abandoned Item image/gallery uploads."""
    candidates = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Item",
            "attached_to_field": ["in", GALLERY_ATTACHMENT_FIELDS],
            "file_url": ["like", "/%files/%"],
        },
        fields=["file_url"],
        distinct=True,
        limit=limit,
    )
    deleted = 0
    for candidate in candidates:
        deleted += _delete_orphan(candidate.file_url)
    return deleted
