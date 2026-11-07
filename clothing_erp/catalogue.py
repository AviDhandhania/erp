"""Read-only clothing catalogue built from native ERPNext records."""

from collections import defaultdict
from datetime import date

import frappe
from frappe.utils import cint, flt, getdate, nowdate

from clothing_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_SALESPERSON
from clothing_erp.security import assigned_documents, require_role

CATALOGUE_ROLES = {ROLE_SALESPERSON, ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN}
PAGE_SIZE = 12
MAX_PAGE_SIZE = 24
MAX_SEARCH_LENGTH = 80
METADATA_FIELDS = {
    "collection": "custom_clothing_collection",
    "fabric": "custom_clothing_fabric",
    "fit": "custom_clothing_fit",
    "season": "custom_clothing_season",
}


def _clean(value, limit=MAX_SEARCH_LENGTH):
    return (value or "").strip()[:limit]


def _selling_price_list(requested=None):
    default_price_list = frappe.db.get_single_value(
        "Selling Settings", "selling_price_list"
    )
    requested = _clean(requested, 140)
    if requested and requested != default_price_list:
        frappe.throw(
            frappe._("You cannot access that selling price list."),
            frappe.PermissionError,
        )
    price_list = default_price_list
    if not price_list:
        frappe.throw(frappe._("Configure a default Selling Price List first."))
    enabled = frappe.db.get_value(
        "Price List", price_list, ["enabled", "selling", "currency"], as_dict=True
    )
    if not enabled or not enabled.enabled or not enabled.selling:
        frappe.throw(frappe._("The selected selling price list is unavailable."))
    return price_list, enabled.currency


def _active_prices(item_uoms, price_list):
    if not item_uoms:
        return {}
    current_date = nowdate()
    rows = frappe.get_all(
        "Item Price",
        filters={
            "item_code": ["in", list(item_uoms)],
            "price_list": price_list,
            "selling": 1,
        },
        fields=[
            "item_code",
            "uom",
            "price_list_rate",
            "currency",
            "valid_from",
            "valid_upto",
            "customer",
            "supplier",
            "batch_no",
        ],
        order_by="valid_from desc, modified desc",
    )
    prices = {}
    today_value = date.fromisoformat(current_date)
    for row in rows:
        if row.customer or row.supplier or row.batch_no:
            continue
        if row.uom and row.uom != item_uoms[row.item_code]:
            continue
        if row.valid_from and getdate(row.valid_from) > today_value:
            continue
        if row.valid_upto and getdate(row.valid_upto) < today_value:
            continue
        prices.setdefault(
            row.item_code,
            {"rate": flt(row.price_list_rate), "currency": row.currency},
        )
    return prices


def _stock(item_codes):
    """Return aggregate on-hand stock, respecting configured Warehouse User Permissions."""
    if not item_codes:
        return {}
    filters = {"item_code": ["in", item_codes]}
    permitted_warehouses = assigned_documents("Warehouse")
    if permitted_warehouses:
        filters["warehouse"] = ["in", permitted_warehouses]
    rows = frappe.get_all(
        "Bin",
        filters=filters,
        fields=["item_code", {"SUM": "actual_qty", "as": "actual_qty"}],
        group_by="item_code",
    )
    return {row.item_code: flt(row.actual_qty) for row in rows}


def _variant_attributes(item_codes):
    if not item_codes:
        return {}
    rows = frappe.get_all(
        "Item Variant Attribute",
        filters={"parent": ["in", item_codes], "parenttype": "Item"},
        fields=["parent", "attribute", "attribute_value", "idx"],
        order_by="parent asc, idx asc",
    )
    values = defaultdict(list)
    for row in rows:
        values[row.parent].append(
            {"attribute": row.attribute, "value": row.attribute_value}
        )
    return values


def _product_images(item_codes):
    """Return gallery rows only for already permission-filtered Item templates."""
    images = defaultdict(list)
    if not item_codes:
        return images
    rows = frappe.get_all(
        "Clothing Product Image",
        filters={
            "parent": ["in", item_codes],
            "parenttype": "Item",
            "parentfield": "custom_clothing_product_images",
        },
        fields=["parent", "image", "caption", "idx"],
        order_by="parent asc, idx asc",
    )
    for row in rows:
        if row.image:
            images[row.parent].append(
                {"image": row.image, "caption": row.caption or ""}
            )
    return images


def _templates(
    search=None,
    item_group=None,
    brand=None,
    metadata=None,
    start=0,
    page_size=PAGE_SIZE,
):
    filters = {"disabled": 0, "has_variants": 1, "is_sales_item": 1}
    if item_group:
        filters["item_group"] = item_group
    if brand:
        filters["brand"] = brand
    for key, fieldname in METADATA_FIELDS.items():
        if metadata and metadata.get(key):
            filters[fieldname] = metadata[key]
    kwargs = {}
    if search:
        pattern = f"%{search}%"
        kwargs["or_filters"] = {
            "name": ["like", pattern],
            "item_name": ["like", pattern],
            "custom_clothing_style_code": ["like", pattern],
        }
    return frappe.get_list(
        "Item",
        filters=filters,
        fields=[
            "name",
            "item_name",
            "item_group",
            "brand",
            "description",
            "image",
            "stock_uom",
            "custom_clothing_style_code",
            "custom_clothing_collection",
            "custom_clothing_fabric",
            "custom_clothing_fit",
            "custom_clothing_season",
        ],
        order_by="item_name asc, name asc",
        start=start,
        limit=page_size + 1,
        **kwargs,
    )


@frappe.whitelist()
def get_catalogue(
    search=None,
    item_group=None,
    brand=None,
    collection=None,
    fabric=None,
    fit=None,
    season=None,
    customer=None,
    page=1,
    page_size=PAGE_SIZE,
    price_list=None,
):
    """Return a paginated, matrix-ready view of ERPNext item variants."""
    require_role(CATALOGUE_ROLES)
    search = _clean(search)
    item_group = _clean(item_group, 140)
    brand = _clean(brand, 140)
    metadata = {
        key: _clean(value, 140)
        for key, value in {
            "collection": collection,
            "fabric": fabric,
            "fit": fit,
            "season": season,
        }.items()
    }
    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), MAX_PAGE_SIZE)
    if customer:
        if price_list:
            frappe.throw(
                frappe._("The retailer's configured Price List is used automatically."),
                frappe.PermissionError,
            )
        selected_price_list, default_currency = None, None
    else:
        selected_price_list, default_currency = _selling_price_list(price_list)

    template_rows = _templates(
        search, item_group, brand, metadata, (page - 1) * page_size, page_size
    )
    has_more = len(template_rows) > page_size
    template_rows = template_rows[:page_size]
    template_names = [row.name for row in template_rows]
    galleries = _product_images(template_names)
    variants = (
        frappe.get_list(
            "Item",
            filters={
                "disabled": 0,
                "is_sales_item": 1,
                "variant_of": ["in", template_names],
            },
            fields=["name", "item_name", "variant_of", "image", "stock_uom"],
            order_by="variant_of asc, name asc",
            limit=500,
        )
        if template_names
        else []
    )
    variant_codes = [row.name for row in variants]
    attributes = _variant_attributes(variant_codes)
    prices = (
        _active_prices(
            {row.name: row.stock_uom for row in variants}, selected_price_list
        )
        if selected_price_list
        else {}
    )
    stock = _stock(variant_codes)
    customer_prices = {}
    if customer:
        from clothing_erp.pricing import get_customer_prices

        customer_prices, customer_price_list, customer_currency = get_customer_prices(
            _clean(customer, 140), variant_codes
        )
        selected_price_list = customer_price_list or selected_price_list
        default_currency = customer_currency or default_currency
    grouped = defaultdict(list)
    for variant in variants:
        price = customer_prices.get(variant.name) or prices.get(variant.name)
        grouped[variant.variant_of].append(
            {
                "item_code": variant.name,
                "item_name": variant.item_name,
                "image": variant.image,
                "uom": variant.stock_uom,
                "attributes": attributes.get(variant.name, []),
                "price": price["rate"] if price else None,
                "currency": price["currency"] if price else default_currency,
                "actual_qty": stock.get(variant.name, 0),
                "available": stock.get(variant.name, 0) > 0,
            }
        )

    products = []
    for template in template_rows:
        images = galleries.get(template.name, [])
        if template.image and template.image not in {row["image"] for row in images}:
            images.insert(0, {"image": template.image, "caption": template.item_name})
        products.append(
            {
                "item_code": template.name,
                "item_name": template.item_name,
                "item_group": template.item_group,
                "brand": template.brand,
                "style_code": template.get("custom_clothing_style_code"),
                "collection": template.get("custom_clothing_collection"),
                "fabric": template.get("custom_clothing_fabric"),
                "fit": template.get("custom_clothing_fit"),
                "season": template.get("custom_clothing_season"),
                "description": template.description,
                "image": template.image,
                "images": images,
                "uom": template.stock_uom,
                "variants": grouped.get(template.name, []),
            }
        )
    return {
        "products": products,
        "pagination": {"page": page, "page_size": page_size, "has_more": has_more},
        "price_list": selected_price_list,
        "currency": default_currency,
        "customer": customer or None,
    }


@frappe.whitelist()
def get_catalogue_filters():
    require_role(CATALOGUE_ROLES)
    item_filters = {"disabled": 0, "has_variants": 1, "is_sales_item": 1}
    metadata = {}
    for key, fieldname in METADATA_FIELDS.items():
        rows = frappe.get_list(
            "Item",
            filters=item_filters,
            fields=[fieldname],
            group_by=fieldname,
            order_by=f"{fieldname} asc",
            limit=500,
        )
        metadata[key] = [row.get(fieldname) for row in rows if row.get(fieldname)]
    return {
        "item_groups": frappe.get_list(
            "Item Group",
            filters={"is_group": 0},
            pluck="name",
            order_by="name asc",
            limit=500,
        ),
        "brands": frappe.get_list(
            "Brand", pluck="name", order_by="name asc", limit=500
        ),
        "retailers": frappe.get_list(
            "Customer",
            filters={"disabled": 0},
            fields=["name", "customer_name"],
            order_by="customer_name asc",
            limit=500,
        ),
        **metadata,
    }
