import re

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from sales_erp.retailer_defaults import validate_retailer_type
from sales_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from sales_erp.security import (
    assigned_sales_territories,
    get_current_user,
    get_user_roles,
    is_clothing_admin,
    is_sales_manager,
    require_role,
)
from sales_erp.supervision import assert_rsm_supervises_asm, get_active_supervising_rsm


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
        filters={
            "name": ["!=", exclude or ""],
            "status": ["in", ["Pending", "Pending Info", "Resubmitted", "Approved"]],
        },
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
        frappe.throw(frappe._("Select an enabled system user as the Area Sales Manager."))
    if ROLE_SALESPERSON not in get_user_roles(user):
        frappe.throw(
            frappe._("The selected user must have the Clothing Area Sales Manager role.")
        )


def _salesperson_application_territory(user):
    territories = assigned_sales_territories(user)
    if not territories:
        frappe.throw(
            frappe._("Your Area Sales Manager account has no assigned territory. Contact an administrator."),
            frappe.PermissionError,
        )
    if len(territories) > 1:
        frappe.throw(
            frappe._("An Area Sales Manager must have exactly one active Sales Territory Assignment."),
            frappe.PermissionError,
        )
    return territories[0]


def _validate_salesperson_territory(user, territory):
    if territory not in assigned_sales_territories(user):
        frappe.throw(
            frappe._("The selected Area Sales Manager is not assigned to this territory."),
            frappe.PermissionError,
        )


def _get_territory_assignment(territory):
    from frappe.utils import nowdate
    records = frappe.db.sql(
        """
        SELECT asm, rsm
        FROM `tabASM Supervision`
        WHERE territory = %s
          AND status = 'Active'
          AND effective_from <= %s
          AND (effective_to IS NULL OR effective_to >= %s)
        ORDER BY effective_from DESC, creation DESC
        LIMIT 1
        """,
        (territory, nowdate(), nowdate()),
        as_dict=True,
    )
    if records:
        return {"asm": records[0].asm, "rsm": records[0].rsm}
    return {}


@frappe.whitelist()
def get_territory_assignment(territory, check_permissions=True):
    """Return active Area Sales Manager and supervising RSM for a sales territory."""
    require_role({ROLE_SALES_MANAGER, ROLE_SALESPERSON, ROLE_BUSINESS_ADMIN, "System Manager", "Administrator"})
    territory = (territory or "").strip()
    if not territory:
        return {}
    if check_permissions:
        user = get_current_user()
        if not is_clothing_admin(user):
            allowed = assigned_sales_territories(user)
            if territory not in allowed:
                frappe.throw(
                    frappe._("You are not authorized to query territory assignments outside your assigned territories."),
                    frappe.PermissionError,
                )
    return _get_territory_assignment(territory)


class RetailerApplication(Document):
    def validate(self):
        if not self.is_new():
            stored_status = frappe.db.get_value(
                "Retailer Application", self.name, "status"
            )
            if stored_status in ("Approved", "Rejected"):
                frappe.throw(
                    frappe._("Reviewed retailer applications cannot be edited.")
                )
            if stored_status != self.status:
                frappe.throw(
                    frappe._(
                        "Use the specific workflow action to change status."
                    ),
                    frappe.PermissionError,
                )
        self.shop_name = self.shop_name.strip()
        self.contact_person = self.contact_person.strip()
        self.phone = _phone(self.phone)
        self.email = (self.email or "").strip().lower()
        self.gstin = (self.gstin or "").strip().upper()
        self.billing_state = (self.billing_state or "").strip()
        self.shipping_state = (self.shipping_state or "").strip()
        if len(self.phone) < 7:
            frappe.throw(frappe._("Enter a valid phone number."))
        if self.country == "India" and not self.billing_state:
            frappe.throw(frappe._("Billing State is required for an Indian address."))
        if (
            self.country == "India"
            and self.shipping_address_line1
            and not self.shipping_state
        ):
            frappe.throw(
                frappe._("Shipping State is required for an Indian shipping address.")
            )
        if ROLE_SALESPERSON in get_user_roles() and not is_sales_manager():
            self.salesperson = get_current_user()
            self.territory = _salesperson_application_territory(self.salesperson)
        if self.territory:
            assignment = get_territory_assignment(self.territory, check_permissions=False)
            if assignment:
                if not self.salesperson:
                    self.salesperson = assignment.get("asm")
                if not self.rsm:
                    self.rsm = assignment.get("rsm")
        if self.salesperson and not self.rsm:
            self.rsm = get_active_supervising_rsm(self.salesperson)
        validate_retailer_type(self.customer_group)
        _validate_salesperson(self.salesperson)
        _validate_salesperson_territory(self.salesperson, self.territory)
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
def approve(name, initial_credit_limit=None):
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    application = _lock_application(name)
    application.check_permission("write")
    if application.status not in ("Pending", "Resubmitted"):
        frappe.throw(frappe._("Only pending or resubmitted applications can be approved."))
    if not is_clothing_admin():
        assert_rsm_supervises_asm(
            rsm=get_current_user(),
            asm=application.salesperson,
            territory=application.territory,
        )
    _validate_salesperson(application.salesperson)

    parsed_limit = 0.0
    if initial_credit_limit is not None and str(initial_credit_limit).strip() != "":
        try:
            parsed_limit = flt(initial_credit_limit)
        except (ValueError, TypeError):
            frappe.throw(frappe._("Initial credit limit must be a valid number."))
        if parsed_limit < 0:
            frappe.throw(frappe._("Initial credit limit cannot be negative."))
    elif getattr(application, "initial_credit_limit", None):
        parsed_limit = flt(application.initial_credit_limit)

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

    if parsed_limit > 0:
        company = (
            frappe.defaults.get_user_default("Company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
        )
        if not company:
            companies = frappe.get_all("Company", limit=1, pluck="name")
            company = companies[0] if companies else None
        if company:
            customer.append(
                "credit_limits",
                {
                    "company": company,
                    "credit_limit": parsed_limit,
                },
            )
            customer.save(ignore_permissions=True)

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
    application.db_set(
        {
            "status": "Approved",
            "customer": customer.name,
            "initial_credit_limit": parsed_limit,
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
        "initial_credit_limit": parsed_limit,
    }


@frappe.whitelist(methods=["POST"])
def request_more_info(name, comments):
    """RSM requests more information from the responsible ASM."""
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    if not (comments or "").strip():
        frappe.throw(frappe._("A comment explaining the required information is required."))
    application = _lock_application(name)
    application.check_permission("write")
    if application.status not in ("Pending", "Resubmitted"):
        frappe.throw(frappe._("Information can only be requested on pending or resubmitted applications."))
    if not is_clothing_admin():
        assert_rsm_supervises_asm(
            rsm=get_current_user(),
            asm=application.salesperson,
            territory=application.territory,
        )
    user = get_current_user()
    application.db_set(
        {
            "status": "More Information Requested",
            "info_requested_by": user,
            "info_requested_on": now_datetime(),
            "requested_information": comments.strip(),
        }
    )
    return {
        "application": application.name,
        "status": "More Information Requested",
        "requested_information": comments.strip(),
    }


@frappe.whitelist(methods=["POST"])
def resubmit(name, notes=None):
    """Responsible ASM resubmits application after updating requested details."""
    require_role({ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    application = _lock_application(name)
    application.check_permission("write")
    if application.status != "More Information Requested":
        frappe.throw(frappe._("Only applications with 'More Information Requested' can be resubmitted."))
    user = get_current_user()
    if user != application.salesperson and not is_clothing_admin(user):
        frappe.throw(
            frappe._("Only the responsible Area Sales Manager can resubmit this application."),
            frappe.PermissionError,
        )
    application.validate()
    updates = {
        "status": "Resubmitted",
        "resubmitted_on": now_datetime(),
    }
    if notes and notes.strip():
        existing_notes = application.notes or ""
        updates["notes"] = f"{existing_notes}\nResubmission notes ({user}): {notes.strip()}".strip()
    application.db_set(updates)
    return {
        "application": application.name,
        "status": "Resubmitted",
    }


@frappe.whitelist(methods=["POST"])
def reject(name, reason):
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    if not (reason or "").strip():
        frappe.throw(frappe._("A rejection reason is required."))
    application = _lock_application(name)
    application.check_permission("write")
    if application.status in ("Approved", "Rejected"):
        frappe.throw(frappe._("Already reviewed applications cannot be rejected."))
    if not is_clothing_admin():
        assert_rsm_supervises_asm(
            rsm=get_current_user(),
            asm=application.salesperson,
            territory=application.territory,
        )
    application.db_set(
        {
            "status": "Rejected",
            "reviewed_by": get_current_user(),
            "reviewed_on": now_datetime(),
            "rejection_reason": reason.strip(),
        }
    )
    return {"application": application.name, "status": "Rejected"}
