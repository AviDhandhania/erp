"""Server-owned defaults used by the simplified retailer intake workflow."""

import frappe

FALLBACK_CUSTOMER_GROUP = "Clothing ERP Retailers"
FALLBACK_TERRITORY = "Clothing ERP Sales Territory"


def ensure_retailer_defaults():
    """Create stable leaf defaults without changing the site's Selling Settings."""
    if not frappe.db.exists("Customer Group", FALLBACK_CUSTOMER_GROUP):
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": FALLBACK_CUSTOMER_GROUP,
                "parent_customer_group": "All Customer Groups",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
    if not frappe.db.exists("Territory", FALLBACK_TERRITORY):
        frappe.get_doc(
            {
                "doctype": "Territory",
                "territory_name": FALLBACK_TERRITORY,
                "parent_territory": "All Territories",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)


def get_retailer_defaults():
    """Prefer native selling defaults, falling back to app-owned leaf masters."""
    return frappe._dict(
        territory=frappe.db.get_single_value("Selling Settings", "territory")
        or FALLBACK_TERRITORY,
        customer_group=frappe.db.get_single_value("Selling Settings", "customer_group")
        or FALLBACK_CUSTOMER_GROUP,
    )
