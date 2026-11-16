"""Permission-aware catalogue pricing delegated to ERPNext's Sales Order engine."""

from collections import defaultdict
from decimal import Decimal, InvalidOperation

import erpnext
import frappe
from erpnext.accounts.doctype.pricing_rule.pricing_rule import (
    validate_pricing_parties,
    validate_pricing_price_lists,
)
from erpnext.setup.utils import get_exchange_rate
from erpnext.stock.get_item_details import _get_item_details
from frappe.utils import cint, flt, getdate, nowdate

from sales_erp.roles import ROLE_BUSINESS_ADMIN
from sales_erp.security import has_retailer_access
from sales_erp.security import require_role

PRICE_ADMIN_ROLES = {ROLE_BUSINESS_ADMIN}
MAX_PRICING_PAGE_SIZE = 24


def _effective_rate(details):
    """Apply ERPNext's Sales Order line-rate formula to native pricing-rule output."""
    effective = flt(details.price_list_rate)
    if details.blanket_order_rate:
        effective = flt(details.blanket_order_rate) * (flt(details.conversion_factor) or 1)
    if details.margin_type == "Percentage":
        rate_with_margin = effective * (1 + flt(details.margin_rate_or_amount) / 100)
    else:
        rate_with_margin = effective + flt(details.margin_rate_or_amount)
    discount_amount = flt(details.discount_amount)
    if details.discount_percentage:
        discount_amount = rate_with_margin * flt(details.discount_percentage) / 100
    return flt(rate_with_margin - discount_amount)


def _catalogue_item_details(context, document_context):
    """Use native pricing after this service has authorized the transaction boundary.

    ERPNext's public helper requires native Sales Order permission. Operational sales
    users intentionally do not have that permission, so this trusted adapter performs
    the remaining native party, price-list, Item and Warehouse checks explicitly before
    returning only the calculated catalogue rate.
    """
    context = frappe._dict(context)
    validate_pricing_parties(context)
    validate_pricing_price_lists(context, "Sales Order")
    details = _get_item_details(context, doc=document_context)
    for warehouse in (details.warehouse, context.warehouse, context.from_warehouse):
        if warehouse:
            erpnext.require_user_permission("Warehouse", warehouse)
    return details


def get_customer_prices(customer, item_codes):
    """Price quantity-one catalogue rows using the native Sales Order controller."""
    if not has_retailer_access(customer):
        frappe.throw(frappe._("You do not have access to this retailer."), frappe.PermissionError)
    if not item_codes:
        return {}, None, None

    company = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default("company")
    if not company:
        frappe.throw(frappe._("Configure a default Company before using retailer pricing."))

    customer_defaults = frappe.db.get_value(
        "Customer", customer, ["default_price_list", "default_currency"], as_dict=True
    )
    selling_price_list = customer_defaults.default_price_list or frappe.db.get_single_value(
        "Selling Settings", "selling_price_list"
    )
    if not selling_price_list:
        frappe.throw(frappe._("Configure a Selling Price List before using retailer pricing."))
    price_list = frappe.db.get_value(
        "Price List", selling_price_list, ["enabled", "selling", "currency"], as_dict=True
    )
    if not price_list or not price_list.enabled or not price_list.selling:
        frappe.throw(frappe._("The retailer's Selling Price List is unavailable."))

    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    currency = customer_defaults.default_currency or price_list.currency
    transaction_date = nowdate()
    conversion_rate = get_exchange_rate(currency, company_currency, transaction_date, "for_selling")
    plc_conversion_rate = get_exchange_rate(
        price_list.currency, currency, transaction_date, "for_selling"
    )
    document_context = {
        "doctype": "Sales Order",
        "customer": customer,
        "company": company,
        "transaction_date": transaction_date,
        "currency": currency,
        "selling_price_list": selling_price_list,
        "items": [{"item_code": item_code, "qty": 1} for item_code in item_codes],
    }
    prices = {}
    for item_code in item_codes:
        details = _catalogue_item_details(
            {
                "item_code": item_code,
                "customer": customer,
                "company": company,
                "doctype": "Sales Order",
                "transaction_date": transaction_date,
                "qty": 1,
                "price_list": selling_price_list,
                "selling_price_list": selling_price_list,
                "currency": currency,
                "price_list_currency": price_list.currency,
                "conversion_rate": conversion_rate,
                "plc_conversion_rate": plc_conversion_rate,
            },
            document_context,
        )
        prices[item_code] = {
            "rate": _effective_rate(details),
            "price_list_rate": details.price_list_rate,
            "discount_percentage": details.discount_percentage,
            "currency": currency,
        }
    return prices, selling_price_list, currency


def _selling_price_list(price_list):
    price_list = str(price_list or "").strip()[:140]
    details = frappe.db.get_value(
        "Price List",
        {"name": price_list, "enabled": 1, "selling": 1},
        ["name", "currency"],
        as_dict=True,
    )
    if not details:
        frappe.throw(frappe._("Select an enabled Selling Price List."))
    return details


def _active_generic_prices(item_codes, price_list):
    if not item_codes:
        return {}, set()
    today = getdate(nowdate())
    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": ["in", item_codes],
            "price_list": price_list,
            "customer": ["is", "not set"],
            "supplier": ["is", "not set"],
            "batch_no": ["is", "not set"],
        },
        fields=["name", "item_code", "uom", "price_list_rate", "valid_from", "valid_upto"],
        order_by="valid_from desc, modified desc, name desc",
    )
    active = defaultdict(list)
    for row in rows:
        if row.valid_from and getdate(row.valid_from) > today:
            continue
        if row.valid_upto and getdate(row.valid_upto) < today:
            continue
        active[row.item_code].append(row)
    return (
        {item_code: rows[0] for item_code, rows in active.items()},
        {item_code for item_code, rows in active.items() if len(rows) > 1},
    )


def _size_only_variants(template_names):
    if not template_names:
        return []
    variants = frappe.get_list(
        "Item",
        filters={
            "variant_of": ["in", template_names],
            "disabled": 0,
            "is_sales_item": 1,
        },
        fields=["name", "item_name", "variant_of", "stock_uom"],
        order_by="variant_of asc, name asc",
        limit=1000,
    )
    attributes = frappe.get_all(
        "Item Variant Attribute",
        filters={"parent": ["in", [row.name for row in variants]], "parenttype": "Item"},
        fields=["parent", "attribute", "attribute_value"],
        order_by="parent asc, idx asc",
    )
    by_variant = defaultdict(list)
    for row in attributes:
        by_variant[row.parent].append(row)
    return [
        frappe._dict(
            row,
            size=by_variant[row.name][0].attribute_value,
        )
        for row in variants
        if {attribute.attribute for attribute in by_variant[row.name]} == {"Size"}
    ]


@frappe.whitelist()
def get_product_pricing(search=None, price_list=None, page=1, page_size=12):
    """Return colour-specific templates and current native prices for every Size."""
    require_role(PRICE_ADMIN_ROLES)
    price_list = price_list or frappe.db.get_single_value(
        "Selling Settings", "selling_price_list"
    )
    price_list_details = _selling_price_list(price_list)
    search = str(search or "").strip()[:80]
    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), MAX_PRICING_PAGE_SIZE)
    query = {
        "doctype": "Item",
        "filters": {"disabled": 0, "has_variants": 1, "is_sales_item": 1},
        "fields": ["name", "item_name", "image", "brand", "item_group"],
        "order_by": "item_name asc, name asc",
        "start": (page - 1) * page_size,
        "limit": page_size + 1,
    }
    if search:
        pattern = f"%{search}%"
        query["or_filters"] = {
            "name": ["like", pattern],
            "item_name": ["like", pattern],
            "custom_clothing_style_code": ["like", pattern],
        }
    templates = frappe.get_list(**query)
    has_more = len(templates) > page_size
    templates = templates[:page_size]
    variants = _size_only_variants([row.name for row in templates])
    prices, ambiguous = _active_generic_prices(
        [row.name for row in variants], price_list_details.name
    )
    by_template = defaultdict(list)
    for variant in variants:
        price = prices.get(variant.name)
        by_template[variant.variant_of].append(
            {
                "item_code": variant.name,
                "item_name": variant.item_name,
                "size": variant.size,
                "uom": variant.stock_uom,
                "rate": price.price_list_rate if price else None,
                "ambiguous": variant.name in ambiguous,
            }
        )
    return {
        "price_list": price_list_details.name,
        "currency": price_list_details.currency,
        "price_lists": frappe.get_all(
            "Price List",
            filters={"enabled": 1, "selling": 1},
            pluck="name",
            order_by="name asc",
        ),
        "products": [{**template, "variants": by_template[template.name]} for template in templates],
        "pagination": {"page": page, "page_size": page_size, "has_more": has_more},
    }


@frappe.whitelist(methods=["POST"])
def set_template_price(template, price_list, rate):
    """Apply one rate to every enabled Size variant using native Item Price records."""
    require_role(PRICE_ADMIN_ROLES)
    price_list_details = _selling_price_list(price_list)
    template = str(template or "").strip()[:140]
    template_row = frappe.get_list(
        "Item",
        filters={
            "name": template,
            "disabled": 0,
            "has_variants": 1,
            "is_sales_item": 1,
        },
        pluck="name",
        limit=1,
    )
    if not template_row:
        frappe.throw(frappe._("Select an enabled clothing product template."))
    try:
        rate = Decimal(str(rate))
    except InvalidOperation, ValueError:
        frappe.throw(frappe._("Enter a valid positive price."))
    if not rate.is_finite() or rate <= 0:
        frappe.throw(frappe._("Enter a valid positive price."))
    variants = _size_only_variants([template])
    if not variants:
        frappe.throw(frappe._("This product has no enabled Size-only variants."))
    item_codes = sorted(row.name for row in variants)
    placeholders = ", ".join(["%s"] * len(item_codes))
    frappe.db.sql(
        f"select name from `tabItem` where name in ({placeholders}) order by name for update",
        item_codes,
    )
    prices, ambiguous = _active_generic_prices(item_codes, price_list_details.name)
    if ambiguous:
        frappe.throw(
            frappe._(
                "Overlapping active Item Prices exist for: {0}. Resolve them in ERPNext before bulk updating."
            ).format(", ".join(sorted(ambiguous)))
        )
    changed = []
    for variant in variants:
        if current := prices.get(variant.name):
            price = frappe.get_doc("Item Price", current.name)
            price.price_list_rate = rate
            price.save(ignore_permissions=True)
            action = "updated"
        else:
            price = frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": variant.name,
                    "uom": variant.stock_uom,
                    "price_list": price_list_details.name,
                    "price_list_rate": rate,
                    "valid_from": nowdate(),
                }
            )
            price.insert(ignore_permissions=True)
            action = "created"
        changed.append({"item_code": variant.name, "item_price": price.name, "action": action})
    return {
        "template": template,
        "price_list": price_list_details.name,
        "currency": price_list_details.currency,
        "rate": flt(rate),
        "changed": changed,
    }
