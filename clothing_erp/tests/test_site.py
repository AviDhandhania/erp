"""Database integration checks. Run through bench on a disposable test site."""
import unittest
import frappe
from frappe.tests import IntegrationTestCase
from clothing_erp.roles import ROLE_SALESPERSON, ROLE_WAREHOUSE_OPERATOR
from clothing_erp import api, catalogue, security


@unittest.skipUnless(getattr(frappe.local, "site", None), "Requires bench site test runner")
class TestSitePermissions(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.db.savepoint("clothing_test_case")
        self.previous_user = frappe.session.user
        frappe.set_user("Administrator")
        self.email = "test-clothing-salesperson@example.invalid"
        if not frappe.db.exists("User", self.email):
            frappe.get_doc({"doctype": "User", "email": self.email, "first_name": "Test Clothing", "send_welcome_email": 0, "roles": [{"role": ROLE_SALESPERSON}]}).insert()

    def tearDown(self):
        frappe.set_user(self.previous_user)
        frappe.db.rollback(save_point="clothing_test_case")
        frappe.clear_cache(user=self.email)
        super().tearDown()

    def test_unassigned_salesperson_cannot_list_any_retailers(self):
        frappe.set_user(self.email)
        self.assertTrue(frappe.db.exists("Page", "clothing-catalogue"))
        gallery = frappe.get_meta("Item").get_field("custom_clothing_product_images")
        self.assertEqual((gallery.fieldtype, gallery.options), ("Table", "Clothing Product Image"))
        self.assertEqual(frappe.get_list("Customer", pluck="name"), [])
        self.assertEqual(frappe.get_list("Sales Order", pluck="name"), [])
        self.assertEqual(api.get_salesperson_dashboard()["metrics"]["assigned_retailers_count"], 0)
        with self.assertRaises(frappe.PermissionError):
            api.switch_preview_role("Administrator")
        with self.assertRaises(frappe.PermissionError):
            api.get_warehouse_dashboard()

    def test_native_user_permission_controls_customer_access(self):
        for doctype, field, value in (("Customer Group", "customer_group_name", "TEST Clothing Group"), ("Territory", "territory_name", "TEST Clothing Territory")):
            if not frappe.db.exists(doctype, value):
                frappe.get_doc({"doctype": doctype, field: value, "is_group": 0}).insert()
        customer = frappe.get_doc({"doctype": "Customer", "customer_name": "TEST Clothing Assigned Retailer", "customer_type": "Company", "customer_group": "TEST Clothing Group", "territory": "TEST Clothing Territory"}).insert()
        frappe.get_doc({"doctype": "User Permission", "user": self.email, "allow": "Customer", "for_value": customer.name, "apply_to_all_doctypes": 1}).insert()
        frappe.clear_cache(user=self.email)
        frappe.set_user(self.email)
        self.assertTrue(security.has_retailer_access(customer.name))
        self.assertEqual(frappe.get_list("Customer", pluck="name"), [customer.name])
        self.assertTrue(frappe.has_permission("Customer", "read", customer.name))
        self.assertFalse(security.has_retailer_access("TEST Unassigned Retailer"))

    def test_operator_queries_with_native_warehouse_assignment(self):
        user = frappe.get_doc({"doctype": "User", "email": "test-clothing-warehouse@example.invalid", "first_name": "TEST Warehouse", "send_welcome_email": 0, "roles": [{"role": ROLE_WAREHOUSE_OPERATOR}]}).insert()
        # Minimal relational fixture: no company/accounting setup is needed to exercise SQL scopes.
        warehouse = frappe.get_doc({"doctype": "Warehouse", "name": "TEST Clothing Warehouse", "warehouse_name": "TEST Clothing Warehouse", "is_group": 0})
        warehouse.db_insert()
        frappe.get_doc({"doctype": "User Permission", "user": user.name, "allow": "Warehouse", "for_value": warehouse.name, "hide_descendants": 1, "apply_to_all_doctypes": 1}).insert()
        frappe.clear_cache(user=user.name)
        frappe.set_user(user.name)
        self.assertEqual(frappe.get_list("Warehouse", pluck="name"), [warehouse.name])
        self.assertEqual(frappe.get_list("Pick List", pluck="name"), [])
        self.assertEqual(frappe.get_list("Delivery Note", pluck="name"), [])
        self.assertEqual(api.get_warehouse_dashboard()["pick_tasks"], [])

    def test_catalogue_reads_real_erpnext_variants_prices_and_stock(self):
        from erpnext.controllers.item_variant import create_variant

        frappe.set_user("Administrator")
        for attribute, values in (
            ("TEST Clothing Colour", (("Black", "BLK"),)),
            ("TEST Clothing Size", (("Medium", "M"),)),
        ):
            frappe.get_doc({
                "doctype": "Item Attribute",
                "attribute_name": attribute,
                "item_attribute_values": [
                    {"attribute_value": value, "abbr": abbreviation}
                    for value, abbreviation in values
                ],
            }).insert()

        template = frappe.get_doc({
            "doctype": "Item",
            "item_code": "TEST-CLOTHING-CATALOGUE",
            "item_name": "TEST Clothing Catalogue Shirt",
            "description": "Fictional integration-test garment",
            "item_group": "Products",
            "stock_uom": "Nos",
            "has_variants": 1,
            "variant_based_on": "Item Attribute",
            "attributes": [
                {"attribute": "TEST Clothing Colour"},
                {"attribute": "TEST Clothing Size"},
            ],
        }).insert()
        variant = create_variant(template.name, {
            "TEST Clothing Colour": "Black",
            "TEST Clothing Size": "Medium",
        })
        variant.item_code = "TEST-CLOTHING-CATALOGUE-BLK-M"
        variant.item_name = "TEST Clothing Catalogue Shirt Black Medium"
        variant.insert()

        price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
        frappe.get_doc({
            "doctype": "Item Price",
            "price_list": price_list,
            "item_code": variant.name,
            "uom": variant.stock_uom,
            "price_list_rate": 749,
        }).insert()
        warehouse = frappe.get_doc({
            "doctype": "Warehouse",
            "warehouse_name": "TEST Catalogue Warehouse",
            "is_group": 0,
        })
        warehouse.db_insert()
        frappe.get_doc({
            "doctype": "Bin",
            "item_code": variant.name,
            "warehouse": warehouse.name,
            "stock_uom": variant.stock_uom,
            "actual_qty": 17,
        }).db_insert()

        result = catalogue.get_catalogue(search="Catalogue Shirt")
        self.assertEqual(len(result["products"]), 1)
        row = result["products"][0]["variants"][0]
        self.assertEqual(row["item_code"], variant.name)
        self.assertEqual(row["price"], 749)
        self.assertEqual(row["actual_qty"], 17)
        self.assertEqual(
            {(value["attribute"], value["value"]) for value in row["attributes"]},
            {("TEST Clothing Colour", "Black"), ("TEST Clothing Size", "Medium")},
        )
