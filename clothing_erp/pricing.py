"""Permission-aware catalogue pricing delegated to ERPNext's Sales Order engine."""

import frappe
from erpnext.setup.utils import get_exchange_rate
from erpnext.stock.get_item_details import get_item_details
from frappe.utils import flt, nowdate

from clothing_erp.security import has_retailer_access


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
        details = get_item_details(
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
            doc=document_context,
        )
        prices[item_code] = {
            "rate": _effective_rate(details),
            "price_list_rate": details.price_list_rate,
            "discount_percentage": details.discount_percentage,
            "currency": currency,
        }
    return prices, selling_price_list, currency
