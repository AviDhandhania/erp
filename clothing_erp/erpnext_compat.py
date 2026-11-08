"""Idempotent repairs for ERPNext-owned installation artifacts."""

import frappe


def ensure_erpnext_contact_fields():
    """Restore ERPNext's own Contact/Address fields when an old patch log skipped them."""
    required = (
        ("Address", "tax_category"),
        ("Address", "is_your_company_address"),
        ("Contact", "is_billing_contact"),
    )
    if all(frappe.db.has_column(doctype, fieldname) for doctype, fieldname in required):
        return False

    from erpnext.setup.install import create_address_and_contact_custom_fields

    create_address_and_contact_custom_fields()
    return True
