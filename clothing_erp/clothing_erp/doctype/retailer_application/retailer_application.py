import re

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from clothing_erp.retailer_defaults import get_retailer_defaults
from clothing_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from clothing_erp.security import (
    get_current_user,
    get_user_roles,
    is_sales_manager,
    require_role,
)


def _phone(value):
    return re.sub(r"\D", "", value or "")[-15:]


def _same_phone(left, right):
    left, right = _phone(left), _phone(right)
    return (
        len(left) >= 7
        and len(right) >= 7
        and (left.endswith(right) or right.endswith(left))
    )


def find_duplicates(doc, exclude=None):
    matches = []
    customers = frappe.get_all(
        "Customer", fields=["name", "customer_name", "mobile_no", "email_id", "tax_id"]
    )
    for customer in customers:
        reasons = []
        if (
            customer.customer_name.strip().casefold()
            == doc.shop_name.strip().casefold()
        ):
            reasons.append("shop name")
        if _same_phone(customer.mobile_no, doc.phone):
            reasons.append("phone")
        if (
            doc.email
            and customer.email_id
            and customer.email_id.casefold() == doc.email.casefold()
        ):
            reasons.append("email")
        if (
            doc.gstin
            and customer.tax_id
            and customer.tax_id.upper() == doc.gstin.upper()
        ):
            reasons.append("GSTIN")
        if reasons:
            matches.append(
                {"doctype": "Customer", "name": customer.name, "reasons": reasons}
            )
    pending = frappe.get_all(
        "Retailer Application",
        filters={"name": ["!=", exclude or ""], "status": "Pending"},
        fields=["name", "shop_name", "phone", "email", "gstin"],
    )
    for application in pending:
        reasons = []
        if application.shop_name.strip().casefold() == doc.shop_name.strip().casefold():
            reasons.append("shop name")
        if _same_phone(application.phone, doc.phone):
            reasons.append("phone")
        if (
            doc.email
            and application.email
            and application.email.casefold() == doc.email.casefold()
        ):
            reasons.append("email")
        if (
            doc.gstin
            and application.gstin
            and application.gstin.upper() == doc.gstin.upper()
        ):
            reasons.append("GSTIN")
        if reasons:
            matches.append(
                {
                    "doctype": "Retailer Application",
                    "name": application.name,
                    "reasons": reasons,
                }
            )
    return matches


def _validate_salesperson(user):
    details = frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True)
    if not details or not details.enabled or details.user_type != "System User":
        frappe.throw(frappe._("Select an enabled system user as the salesperson."))
    if ROLE_SALESPERSON not in get_user_roles(user):
        frappe.throw(
            frappe._("The selected user must have the Clothing Salesperson role.")
        )


def _salesperson_application_defaults():
    defaults = get_retailer_defaults()
    if not frappe.db.exists("Territory", defaults.territory) or not frappe.db.exists(
        "Customer Group", defaults.customer_group
    ):
        frappe.throw(
            frappe._(
                "The default Territory or Customer Group configured in Selling Settings does not exist."
            )
        )
    return defaults


class RetailerApplication(Document):
    def validate(self):
        if not self.is_new():
            stored_status = frappe.db.get_value(
                "Retailer Application", self.name, "status"
            )
            if stored_status != self.status:
                frappe.throw(
                    frappe._(
                        "Use the manager approval or rejection action to change status."
                    ),
                    frappe.PermissionError,
                )
            if stored_status != "Pending":
                frappe.throw(
                    frappe._("Reviewed retailer applications cannot be edited.")
                )
        self.shop_name = self.shop_name.strip()
        self.contact_person = self.contact_person.strip()
        self.phone = _phone(self.phone)
        self.email = (self.email or "").strip().lower()
        self.gstin = (self.gstin or "").strip().upper()
        if len(self.phone) < 7:
            frappe.throw(frappe._("Enter a valid phone number."))
        if ROLE_SALESPERSON in get_user_roles() and not is_sales_manager():
            self.salesperson = get_current_user()
            defaults = _salesperson_application_defaults()
            self.territory = defaults.territory
            self.customer_group = defaults.customer_group
        _validate_salesperson(self.salesperson)
        if self.is_new() and find_duplicates(self):
            frappe.throw(
                frappe._(
                    "A possible duplicate retailer or pending application already exists."
                )
            )


def _make_contact(application, customer):
    contact = frappe.get_doc(
        {
            "doctype": "Contact",
            "first_name": application.contact_person,
            "is_primary_contact": 1,
            "links": [{"link_doctype": "Customer", "link_name": customer.name}],
        }
    )
    if application.email:
        contact.append("email_ids", {"email_id": application.email, "is_primary": 1})
    if application.phone:
        contact.append(
            "phone_nos",
            {
                "phone": application.phone,
                "is_primary_phone": 1,
                "is_primary_mobile_no": 1,
            },
        )
    contact.insert(ignore_permissions=True)


def _make_address(application, customer, shipping=False):
    line = (
        application.shipping_address_line1
        if shipping
        else application.billing_address_line1
    )
    city = application.shipping_city if shipping else application.billing_city
    state = application.shipping_state if shipping else application.billing_state
    pincode = application.shipping_pincode if shipping else application.billing_pincode
    if not line:
        return
    frappe.get_doc(
        {
            "doctype": "Address",
            "address_title": application.shop_name,
            "address_type": "Shipping" if shipping else "Billing",
            "address_line1": line,
            "city": city or application.billing_city,
            "state": state,
            "pincode": pincode,
            "country": application.country,
            "phone": application.phone,
            "email_id": application.email,
            "is_primary_address": 0 if shipping else 1,
            "is_shipping_address": 1 if shipping else 0,
            "links": [{"link_doctype": "Customer", "link_name": customer.name}],
        }
    ).insert(ignore_permissions=True)


def _lock_application(name):
    """Serialize review actions so one application cannot create two customers."""
    frappe.db.sql(
        "SELECT name FROM `tabRetailer Application` WHERE name = %s FOR UPDATE",
        name,
    )
    return frappe.get_doc("Retailer Application", name)


@frappe.whitelist(methods=["POST"])
def approve(name):
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    application = _lock_application(name)
    if application.status != "Pending":
        frappe.throw(frappe._("Only pending applications can be approved."))
    _validate_salesperson(application.salesperson)
    duplicates = find_duplicates(application, exclude=application.name)
    if duplicates:
        frappe.throw(
            frappe._("Approval stopped because a duplicate retailer was found.")
        )
    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": application.shop_name,
            "customer_type": "Company",
            "customer_group": application.customer_group,
            "territory": application.territory,
            "tax_id": application.gstin or None,
        }
    ).insert(ignore_permissions=True)
    _make_contact(application, customer)
    _make_address(application, customer)
    billing_address = (
        application.billing_address_line1,
        application.billing_city,
        application.billing_state,
        application.billing_pincode,
    )
    shipping_address = (
        application.shipping_address_line1,
        application.shipping_city,
        application.shipping_state,
        application.shipping_pincode,
    )
    if application.shipping_address_line1 and shipping_address != billing_address:
        _make_address(application, customer, shipping=True)
    if not frappe.db.exists(
        "User Permission",
        {
            "user": application.salesperson,
            "allow": "Customer",
            "for_value": customer.name,
        },
    ):
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": application.salesperson,
                "allow": "Customer",
                "for_value": customer.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert(ignore_permissions=True)
    application.db_set(
        {
            "status": "Approved",
            "customer": customer.name,
            "reviewed_by": get_current_user(),
            "reviewed_on": now_datetime(),
            "rejection_reason": None,
        }
    )
    frappe.clear_cache(user=application.salesperson)
    frappe.db.after_commit.add(
        lambda user=application.salesperson: frappe.clear_cache(user=user)
    )
    return {
        "application": application.name,
        "customer": customer.name,
        "status": "Approved",
    }


@frappe.whitelist(methods=["POST"])
def reject(name, reason):
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    if not (reason or "").strip():
        frappe.throw(frappe._("A rejection reason is required."))
    application = _lock_application(name)
    if application.status != "Pending":
        frappe.throw(frappe._("Only pending applications can be rejected."))
    application.db_set(
        {
            "status": "Rejected",
            "reviewed_by": get_current_user(),
            "reviewed_on": now_datetime(),
            "rejection_reason": reason.strip(),
        }
    )
    return {"application": application.name, "status": "Rejected"}
