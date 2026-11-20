"""Server-owned defaults used by the simplified retailer intake workflow."""

import frappe

FALLBACK_CUSTOMER_GROUP = "Clothing ERP Retailers"
FALLBACK_TERRITORY = "Clothing ERP Sales Territory"
RETAILER_TYPE_PARENT = "Clothing ERP Retailer Types"
RETAILER_TYPES = (
    "Buy & Sell",
    "Buy & Sell - Stock Correction",
    "SIS (Shop-in-Shop)",
    "EBOC (Exclusive Brand Outlet)",
)


def ensure_retailer_defaults():
    """Create stable leaf defaults without changing the site's Selling Settings."""
    if not frappe.db.exists("Customer Group", "All Customer Groups"):
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": "All Customer Groups",
                "is_group": 1,
                "parent_customer_group": "",
            }
        ).insert(ignore_permissions=True)
    if not frappe.db.exists("Territory", "All Territories"):
        frappe.get_doc(
            {
                "doctype": "Territory",
                "territory_name": "All Territories",
                "is_group": 1,
                "parent_territory": "",
            }
        ).insert(ignore_permissions=True)
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
    if not frappe.db.exists("Customer Group", RETAILER_TYPE_PARENT):
        frappe.get_doc(
            {
                "doctype": "Customer Group",
                "customer_group_name": RETAILER_TYPE_PARENT,
                "parent_customer_group": "All Customer Groups",
                "is_group": 1,
            }
        ).insert(ignore_permissions=True)
    for retailer_type in RETAILER_TYPES:
        if not frappe.db.exists("Customer Group", retailer_type):
            frappe.get_doc(
                {
                    "doctype": "Customer Group",
                    "customer_group_name": retailer_type,
                    "parent_customer_group": RETAILER_TYPE_PARENT,
                    "is_group": 0,
                }
            ).insert(ignore_permissions=True)


def validate_retailer_type(customer_group):
    """Require one of the four business-owned retailer classifications."""
    if customer_group not in RETAILER_TYPES:
        frappe.throw(
            frappe._("Select one of the configured Clothing ERP retailer types.")
        )
    return customer_group


def get_retailer_defaults():
    """Prefer native selling defaults, falling back to app-owned leaf masters."""
    return frappe._dict(
        territory=frappe.db.get_single_value("Selling Settings", "territory")
        or FALLBACK_TERRITORY,
        customer_group=frappe.db.get_single_value("Selling Settings", "customer_group")
        or FALLBACK_CUSTOMER_GROUP,
    )
