"""Fictional, idempotent development data for manual catalogue testing."""

import frappe
from erpnext.controllers.item_variant import create_variant

SEED_REFERENCE = "Clothing ERP fictional catalogue seed"
SEED_IMAGE = "/assets/clothing_erp/images/clothing_erp_logo.svg"

PRODUCTS = (
    {
        "code": "TEST-CLASSIC-TEE",
        "name": "TEST Classic Cotton T-shirt",
        "brand": "TEST Threadline",
        "description": "Fictional cotton T-shirt for Clothing ERP testing only.",
        "colours": ("TEST Black", "TEST White", "TEST Navy"),
        "sizes": ("TEST S", "TEST M", "TEST L", "TEST XL"),
        "rate": 499,
    },
    {
        "code": "TEST-DENIM-JEANS",
        "name": "TEST Straight Fit Denim Jeans",
        "brand": "TEST Denim Works",
        "description": "Fictional straight-fit jeans for Clothing ERP testing only.",
        "colours": ("TEST Indigo", "TEST Washed Black"),
        "sizes": ("TEST 28", "TEST 30", "TEST 32", "TEST 34"),
        "rate": 1299,
    },
    {
        "code": "TEST-FLEECE-HOODIE",
        "name": "TEST Everyday Fleece Hoodie",
        "brand": "TEST Threadline",
        "description": "Fictional fleece hoodie for Clothing ERP testing only.",
        "colours": ("TEST Charcoal", "TEST Maroon"),
        "sizes": ("TEST M", "TEST L", "TEST XL"),
        "rate": 999,
    },
)


def _require_development_site():
    if not (frappe.conf.developer_mode or frappe.flags.in_test):
        frappe.throw(
            frappe._("Fictional seed data is restricted to sites with developer_mode enabled."),
            frappe.PermissionError,
        )


def _seed_company():
    companies = frappe.get_all(
        "Company",
        filters={"name": ["like", "TEST%"]},
        fields=["name", "default_currency", "default_warehouse"],
        order_by="creation asc",
        limit=2,
    )
    if len(companies) != 1:
        frappe.throw(frappe._("The development site must contain exactly one enabled TEST company."))
    company = companies[0]
    if not company.default_warehouse:
        frappe.throw(frappe._("The TEST company needs a default warehouse."))
    return company


def _ensure_item_group():
    name = "TEST Clothing Products"
    if not frappe.db.exists("Item Group", name):
        frappe.get_doc(
            {
                "doctype": "Item Group",
                "item_group_name": name,
                "parent_item_group": "Products",
                "is_group": 0,
            }
        ).insert()
    return name


def _ensure_brand(name):
    if not frappe.db.exists("Brand", name):
        frappe.get_doc({"doctype": "Brand", "brand": name, "description": SEED_REFERENCE}).insert()


def _ensure_attribute(name, values):
    attribute = frappe.db.exists("Item Attribute", name)
    if attribute:
        doc = frappe.get_doc("Item Attribute", attribute)
    else:
        doc = frappe.get_doc({"doctype": "Item Attribute", "attribute_name": name})
    existing = {row.attribute_value for row in doc.item_attribute_values}
    changed = False
    for index, value in enumerate(values, 1):
        if value not in existing:
            doc.append(
                "item_attribute_values",
                {"attribute_value": value, "abbr": f"T{index:02d}"},
            )
            changed = True
    if doc.is_new():
        doc.insert()
    elif changed:
        doc.save()


def _ensure_template(product, item_group):
    if frappe.db.exists("Item", product["code"]):
        template = frappe.get_doc("Item", product["code"])
        if not template.has_variants:
            frappe.throw(frappe._("Seed item {0} exists but is not a template.").format(product["code"]))
        return template
    return frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": product["code"],
            "item_name": product["name"],
            "description": product["description"],
            "item_group": item_group,
            "brand": product["brand"],
            "stock_uom": "Nos",
            "image": SEED_IMAGE,
            "has_variants": 1,
            "variant_based_on": "Item Attribute",
            "attributes": [{"attribute": "Colour"}, {"attribute": "Size"}],
        }
    ).insert()


def _variant_code(template_code, colour_index, size_index):
    return f"{template_code}-C{colour_index:02d}-S{size_index:02d}"


def _ensure_variants(template, product):
    variants = []
    for colour_index, colour in enumerate(product["colours"], 1):
        for size_index, size in enumerate(product["sizes"], 1):
            item_code = _variant_code(template.name, colour_index, size_index)
            if frappe.db.exists("Item", item_code):
                variant = frappe.get_doc("Item", item_code)
                if variant.variant_of != template.name:
                    frappe.throw(frappe._("Seed item code {0} belongs to another template.").format(item_code))
            else:
                variant = create_variant(template.name, {"Colour": colour, "Size": size})
                variant.item_code = item_code
                variant.item_name = f"{product['name']} — {colour.removeprefix('TEST ')} / {size.removeprefix('TEST ')}"
                variant.image = SEED_IMAGE
                variant.insert()
            variants.append(variant)
    return variants


def _ensure_price(item_code, price_list, rate):
    filters = {"item_code": item_code, "price_list": price_list, "uom": "Nos"}
    name = frappe.db.exists("Item Price", filters)
    if name:
        price = frappe.get_doc("Item Price", name)
        if price.price_list_rate != rate:
            price.price_list_rate = rate
            price.note = SEED_REFERENCE
            price.save()
    else:
        frappe.get_doc(
            {
                "doctype": "Item Price",
                **filters,
                "price_list_rate": rate,
                "note": SEED_REFERENCE,
            }
        ).insert()


def _receive_initial_stock(company, variants):
    items = []
    for index, variant in enumerate(variants, 1):
        if not frappe.db.exists(
            "Bin", {"item_code": variant.name, "warehouse": company.default_warehouse}
        ):
            items.append(
                {
                    "item_code": variant.name,
                    "t_warehouse": company.default_warehouse,
                    "qty": 10 + (index * 3) % 41,
                    "basic_rate": 200,
                }
            )
    if not items:
        return None
    entry = frappe.get_doc(
        {
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Receipt",
            "company": company.name,
            "remarks": SEED_REFERENCE,
            "items": items,
        }
    )
    entry.insert()
    entry.submit()
    return entry.name


def seed_catalogue():
    """Create or complete the fictional catalogue and return a concise summary."""
    _require_development_site()
    company = _seed_company()
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    if not price_list:
        frappe.throw(frappe._("Configure a default Selling Price List before seeding."))

    item_group = _ensure_item_group()
    for brand in {product["brand"] for product in PRODUCTS}:
        _ensure_brand(brand)
    _ensure_attribute("Colour", sorted({value for product in PRODUCTS for value in product["colours"]}))
    _ensure_attribute("Size", sorted({value for product in PRODUCTS for value in product["sizes"]}))

    all_variants = []
    for product in PRODUCTS:
        template = _ensure_template(product, item_group)
        variants = _ensure_variants(template, product)
        for variant in variants:
            _ensure_price(variant.name, price_list, product["rate"])
        all_variants.extend(variants)
    stock_entry = _receive_initial_stock(company, all_variants)
    frappe.db.commit()
    return {
        "company": company.name,
        "warehouse": company.default_warehouse,
        "price_list": price_list,
        "templates": len(PRODUCTS),
        "variants": len(all_variants),
        "stock_entry": stock_entry,
        "catalogue_url": "/desk/clothing-catalogue",
    }
