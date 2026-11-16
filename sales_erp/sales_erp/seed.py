"""Fictional, idempotent development data for end-to-end manual testing."""

import secrets

import frappe
from erpnext.controllers.item_variant import create_variant

from sales_erp.retailer_defaults import RETAILER_TYPES, ensure_retailer_defaults
from sales_erp.roles import (
    ROLE_ASM,
    ROLE_BUSINESS_ADMIN,
    ROLE_RSM,
    ROLE_WAREHOUSE_MANAGER,
)
from sales_erp.supervision import assign_asm_supervision, record_assignment_history

SEED_REFERENCE = "Clothing ERP fictional catalogue seed"
SEED_RETAILER = "TEST Catalogue Boutique"
SEED_RSM = "test-rsm@example.invalid"
SEED_ASM_NORTH = "test-asm-north@example.invalid"
SEED_ASM_SOUTH = "test-asm-south@example.invalid"
SEED_BUSINESS_ADMIN = "test-business-admin@example.invalid"
SEED_WAREHOUSE_MANAGER = "test-warehouse-manager@example.invalid"
SEED_TERRITORIES = (
    ("TEST North Sales Territory", SEED_ASM_NORTH),
    ("TEST South Sales Territory", SEED_ASM_SOUTH),
)
PRODUCTS = (
    {
        "code": "TEST-CLASSIC-TEE-BLK",
        "name": "TEST Classic Cotton T-shirt — Black",
        "brand": "TEST Threadline",
        "description": "Fictional cotton T-shirt for Clothing ERP testing only.",
        "image": "/assets/sales_erp/images/seed/test-classic-tee.jpg",
        "gallery": (
            (
                "/assets/sales_erp/images/seed/test-classic-tee.jpg",
                "Folded T-shirt view",
            ),
            (
                "/assets/sales_erp/images/seed/test-classic-tee-alt.jpg",
                "Hanging T-shirt detail",
            ),
        ),
        "colour": "Black",
        "style_code": "TEST-CT-001",
        "collection": "TEST Essentials",
        "fabric": "TEST Cotton Jersey",
        "fit": "TEST Regular Fit",
        "season": "TEST Core",
        "sizes": ("TEST S", "TEST M", "TEST L", "TEST XL"),
        "rate": 499,
        "hsn_code": "61091000",
    },
    {
        "code": "TEST-CLASSIC-TEE-WHT",
        "name": "TEST Classic Cotton T-shirt — White",
        "brand": "TEST Threadline",
        "description": "Fictional white cotton T-shirt for Clothing ERP testing only.",
        "image": "/assets/sales_erp/images/seed/test-classic-tee.jpg",
        "gallery": (
            (
                "/assets/sales_erp/images/seed/test-classic-tee.jpg",
                "Folded T-shirt view",
            ),
            (
                "/assets/sales_erp/images/seed/test-classic-tee-alt.jpg",
                "Hanging T-shirt detail",
            ),
        ),
        "colour": "White",
        "style_code": "TEST-CT-001",
        "collection": "TEST Essentials",
        "fabric": "TEST Cotton Jersey",
        "fit": "TEST Regular Fit",
        "season": "TEST Core",
        "sizes": ("TEST S", "TEST M", "TEST L", "TEST XL"),
        "rate": 499,
        "hsn_code": "61091000",
    },
    {
        "code": "TEST-CLASSIC-TEE-NVY",
        "name": "TEST Classic Cotton T-shirt — Navy",
        "brand": "TEST Threadline",
        "description": "Fictional navy cotton T-shirt for Clothing ERP testing only.",
        "image": "/assets/sales_erp/images/seed/test-classic-tee.jpg",
        "gallery": (
            (
                "/assets/sales_erp/images/seed/test-classic-tee.jpg",
                "Folded T-shirt view",
            ),
            (
                "/assets/sales_erp/images/seed/test-classic-tee-alt.jpg",
                "Hanging T-shirt detail",
            ),
        ),
        "colour": "Navy",
        "style_code": "TEST-CT-001",
        "collection": "TEST Essentials",
        "fabric": "TEST Cotton Jersey",
        "fit": "TEST Regular Fit",
        "season": "TEST Core",
        "sizes": ("TEST S", "TEST M", "TEST L", "TEST XL"),
        "rate": 499,
        "hsn_code": "61091000",
    },
    {
        "code": "TEST-DENIM-JEANS-IND",
        "name": "TEST Straight Fit Denim Jeans — Indigo",
        "brand": "TEST Denim Works",
        "description": "Fictional straight-fit jeans for Clothing ERP testing only.",
        "image": "/assets/sales_erp/images/seed/test-denim-jeans.jpg",
        "gallery": (
            (
                "/assets/sales_erp/images/seed/test-denim-jeans.jpg",
                "Folded denim detail",
            ),
            (
                "/assets/sales_erp/images/seed/test-denim-jeans-alt.jpg",
                "Back-pocket detail",
            ),
        ),
        "colour": "Indigo",
        "style_code": "TEST-DJ-101",
        "collection": "TEST Denim Edit",
        "fabric": "TEST Cotton Denim",
        "fit": "TEST Straight Fit",
        "season": "TEST Core",
        "sizes": ("TEST 28", "TEST 30", "TEST 32", "TEST 34"),
        "rate": 1299,
        "hsn_code": "62034200",
    },
    {
        "code": "TEST-DENIM-JEANS-WBK",
        "name": "TEST Straight Fit Denim Jeans — Washed Black",
        "brand": "TEST Denim Works",
        "description": "Fictional washed-black jeans for Clothing ERP testing only.",
        "image": "/assets/sales_erp/images/seed/test-denim-jeans.jpg",
        "gallery": (
            (
                "/assets/sales_erp/images/seed/test-denim-jeans.jpg",
                "Folded denim detail",
            ),
            (
                "/assets/sales_erp/images/seed/test-denim-jeans-alt.jpg",
                "Back-pocket detail",
            ),
        ),
        "colour": "Washed Black",
        "style_code": "TEST-DJ-101",
        "collection": "TEST Denim Edit",
        "fabric": "TEST Cotton Denim",
        "fit": "TEST Straight Fit",
        "season": "TEST Core",
        "sizes": ("TEST 28", "TEST 30", "TEST 32", "TEST 34"),
        "rate": 1299,
        "hsn_code": "62034200",
    },
    {
        "code": "TEST-FLEECE-HOODIE-CHR",
        "name": "TEST Everyday Fleece Hoodie — Charcoal",
        "brand": "TEST Threadline",
        "description": "Fictional fleece hoodie for Clothing ERP testing only.",
        "image": "/assets/sales_erp/images/seed/test-fleece-hoodie.jpg",
        "gallery": (
            (
                "/assets/sales_erp/images/seed/test-fleece-hoodie.jpg",
                "Hoodie lifestyle view",
            ),
            (
                "/assets/sales_erp/images/seed/test-fleece-hoodie-alt.jpg",
                "Plain back view",
            ),
        ),
        "colour": "Charcoal",
        "style_code": "TEST-FH-201",
        "collection": "TEST Winter Layers",
        "fabric": "TEST Brushed Fleece",
        "fit": "TEST Relaxed Fit",
        "season": "TEST Autumn/Winter",
        "sizes": ("TEST M", "TEST L", "TEST XL"),
        "rate": 999,
        "hsn_code": "61102000",
    },
    {
        "code": "TEST-FLEECE-HOODIE-MRN",
        "name": "TEST Everyday Fleece Hoodie — Maroon",
        "brand": "TEST Threadline",
        "description": "Fictional maroon fleece hoodie for Clothing ERP testing only.",
        "image": "/assets/sales_erp/images/seed/test-fleece-hoodie.jpg",
        "gallery": (
            (
                "/assets/sales_erp/images/seed/test-fleece-hoodie.jpg",
                "Hoodie lifestyle view",
            ),
            (
                "/assets/sales_erp/images/seed/test-fleece-hoodie-alt.jpg",
                "Plain back view",
            ),
        ),
        "colour": "Maroon",
        "style_code": "TEST-FH-201",
        "collection": "TEST Winter Layers",
        "fabric": "TEST Brushed Fleece",
        "fit": "TEST Relaxed Fit",
        "season": "TEST Autumn/Winter",
        "sizes": ("TEST M", "TEST L", "TEST XL"),
        "rate": 999,
        "hsn_code": "61102000",
    },
)

LEGACY_COLOUR_TEMPLATE_CODES = (
    "TEST-CLASSIC-TEE",
    "TEST-DENIM-JEANS",
    "TEST-FLEECE-HOODIE",
)


def _require_development_site():
    if not (frappe.conf.developer_mode or frappe.flags.in_test):
        frappe.throw(
            frappe._(
                "Fictional seed data is restricted to sites with developer_mode enabled."
            ),
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
        frappe.throw(
            frappe._(
                "The development site must contain exactly one enabled TEST company."
            )
        )
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
        frappe.get_doc(
            {"doctype": "Brand", "brand": name, "description": SEED_REFERENCE}
        ).insert()


def _ensure_seed_user(email, first_name, role):
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
        if role not in {row.role for row in user.roles}:
            user.add_roles(role)
    else:
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "send_welcome_email": 0,
                "user_type": "System User",
                "roles": [{"role": role}],
            }
        ).insert(ignore_permissions=True)
    password = secrets.token_urlsafe(14)
    user.new_password = password
    user.save(ignore_permissions=True)
    return {"email": email, "password": password, "role": role}


def _ensure_user_permission(user, allow, for_value, is_default=False):
    existing = frappe.db.exists(
        "User Permission", {"user": user, "allow": allow, "for_value": for_value}
    )
    if existing:
        return existing
    return frappe.get_doc(
        {
            "doctype": "User Permission",
            "user": user,
            "allow": allow,
            "for_value": for_value,
            "apply_to_all_doctypes": 1,
            "is_default": int(bool(is_default)),
        }
    ).insert(ignore_permissions=True).name


def _ensure_sales_territories():
    parent = "TEST India Sales Region"
    if not frappe.db.exists("Territory", parent):
        frappe.get_doc(
            {
                "doctype": "Territory",
                "territory_name": parent,
                "parent_territory": "All Territories",
                "is_group": 1,
            }
        ).insert(ignore_permissions=True)
    for territory, _asm in SEED_TERRITORIES:
        if not frappe.db.exists("Territory", territory):
            frappe.get_doc(
                {
                    "doctype": "Territory",
                    "territory_name": territory,
                    "parent_territory": parent,
                    "is_group": 0,
                }
            ).insert(ignore_permissions=True)


def _ensure_seed_retailers():
    retailers = []
    for territory_index, (territory, _asm) in enumerate(SEED_TERRITORIES, 1):
        for type_index, retailer_type in enumerate(RETAILER_TYPES, 1):
            name = (
                SEED_RETAILER
                if territory_index == 1 and type_index == 1
                else f"TEST {territory_index}-{type_index} {retailer_type} Store"
            )
            if frappe.db.exists("Customer", name):
                customer = frappe.get_doc("Customer", name)
                changed = False
                if customer.customer_group != retailer_type:
                    customer.customer_group = retailer_type
                    changed = True
                if customer.territory != territory:
                    customer.territory = territory
                    changed = True
                if changed:
                    customer.save(ignore_permissions=True)
            else:
                frappe.get_doc(
                    {
                        "doctype": "Customer",
                        "customer_name": name,
                        "customer_type": "Company",
                        "customer_group": retailer_type,
                        "territory": territory,
                    }
                ).insert(ignore_permissions=True)
            retailers.append(name)
    return retailers


def _seed_test_accounts_and_assignments(company):
    ensure_retailer_defaults()
    _ensure_sales_territories()
    credentials = [
        _ensure_seed_user(SEED_RSM, "TEST Regional Manager", ROLE_RSM),
        _ensure_seed_user(SEED_ASM_NORTH, "TEST North ASM", ROLE_ASM),
        _ensure_seed_user(SEED_ASM_SOUTH, "TEST South ASM", ROLE_ASM),
        _ensure_seed_user(
            SEED_BUSINESS_ADMIN, "TEST Business Administrator", ROLE_BUSINESS_ADMIN
        ),
        _ensure_seed_user(
            SEED_WAREHOUSE_MANAGER, "TEST Warehouse Manager", ROLE_WAREHOUSE_MANAGER
        ),
    ]
    _ensure_user_permission(
        SEED_WAREHOUSE_MANAGER, "Warehouse", company.default_warehouse, is_default=True
    )
    assignments = []
    for territory, asm in SEED_TERRITORIES:
        assignment = assign_asm_supervision(
            asm=asm,
            rsm=SEED_RSM,
            territory=territory,
            reason=SEED_REFERENCE,
        )
        assignments.append(assignment["name"])
        if not frappe.db.exists("Retailer Assignment History", {"territory": territory}):
            record_assignment_history(
                territory=territory,
                new_asm=asm,
                new_rsm=SEED_RSM,
                reason=SEED_REFERENCE,
            )
    return {
        "credentials": credentials,
        "assignments": assignments,
        "retailers": _ensure_seed_retailers(),
    }


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
            frappe.throw(
                frappe._("Seed item {0} exists but is not a template.").format(
                    product["code"]
                )
            )
        changed = False
        for fieldname, value in (
            ("item_name", product["name"]),
            ("description", product["description"]),
            ("brand", product["brand"]),
            ("image", product["image"]),
            ("gst_hsn_code", product["hsn_code"]),
            ("custom_clothing_style_code", product["style_code"]),
            ("custom_clothing_collection", product["collection"]),
            ("custom_clothing_fabric", product["fabric"]),
            ("custom_clothing_fit", product["fit"]),
            ("custom_clothing_season", product["season"]),
        ):
            if template.get(fieldname) != value:
                template.set(fieldname, value)
                changed = True
        existing_gallery = {
            row.image: row
            for row in template.get("custom_clothing_product_images") or []
        }
        for image, caption in product["gallery"]:
            if image not in existing_gallery:
                template.append(
                    "custom_clothing_product_images",
                    {"image": image, "caption": caption},
                )
                changed = True
            elif (existing_gallery[image].caption or "") != caption:
                existing_gallery[image].caption = caption
                changed = True
        if changed:
            template.save()
        return template
    template = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": product["code"],
            "item_name": product["name"],
            "description": product["description"],
            "item_group": item_group,
            "brand": product["brand"],
            "stock_uom": "Nos",
            "gst_hsn_code": product["hsn_code"],
            "image": product["image"],
            "custom_clothing_style_code": product["style_code"],
            "custom_clothing_collection": product["collection"],
            "custom_clothing_fabric": product["fabric"],
            "custom_clothing_fit": product["fit"],
            "custom_clothing_season": product["season"],
            "has_variants": 1,
            "variant_based_on": "Item Attribute",
            "attributes": [{"attribute": "Size"}],
        }
    )
    for image, caption in product["gallery"]:
        template.append(
            "custom_clothing_product_images", {"image": image, "caption": caption}
        )
    return template.insert()


def _variant_code(template_code, size_index):
    return f"{template_code}-S{size_index:02d}"


def _ensure_variants(template, product):
    variants = []
    for size_index, size in enumerate(product["sizes"], 1):
        item_code = _variant_code(template.name, size_index)
        if frappe.db.exists("Item", item_code):
            variant = frappe.get_doc("Item", item_code)
            if variant.variant_of != template.name:
                frappe.throw(
                    frappe._("Seed item code {0} belongs to another template.").format(
                        item_code
                    )
                )
            if variant.image != product["image"]:
                variant.image = product["image"]
                variant.save()
        else:
            variant = create_variant(template.name, {"Size": size})
            variant.item_code = item_code
            variant.item_name = f"{product['name']} / {size.removeprefix('TEST ')}"
            variant.image = product["image"]
            variant.insert()
        variants.append(variant)
    return variants


def _retire_legacy_colour_templates():
    """Hide only the obsolete fictional templates; their stock history remains intact."""
    for template_code in LEGACY_COLOUR_TEMPLATE_CODES:
        if frappe.db.exists("Item", template_code):
            frappe.db.set_value(
                "Item", template_code, "disabled", 1, update_modified=False
            )
            for variant in frappe.get_all(
                "Item", filters={"variant_of": template_code}, pluck="name"
            ):
                frappe.db.set_value(
                    "Item", variant, "disabled", 1, update_modified=False
                )


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
    """Create the fictional catalogue, users, territories and retailer hierarchy."""
    _require_development_site()
    company = _seed_company()
    price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    if not price_list:
        frappe.throw(frappe._("Configure a default Selling Price List before seeding."))

    item_group = _ensure_item_group()
    field_sales = _seed_test_accounts_and_assignments(company)
    for brand in {product["brand"] for product in PRODUCTS}:
        _ensure_brand(brand)
    _ensure_attribute(
        "Size", sorted({value for product in PRODUCTS for value in product["sizes"]})
    )
    _retire_legacy_colour_templates()

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
        "retailer": SEED_RETAILER,
        "retailers": field_sales["retailers"],
        "sales_territory_assignments": field_sales["assignments"],
        "test_accounts": field_sales["credentials"],
        "templates": len(PRODUCTS),
        "variants": len(all_variants),
        "stock_entry": stock_entry,
        "catalogue_url": "/desk/clothing-catalogue",
    }
