"""Database integration checks. Run through bench on a disposable test site."""

import unittest

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime

from clothing_erp import api, catalogue, fulfillment, security, supervision
from clothing_erp.clothing_erp.doctype.retailer_application.retailer_application import (
    approve,
    reject,
)
from clothing_erp.pricing import get_customer_prices
from clothing_erp.roles import ROLE_ASM, ROLE_RSM, ROLE_SALESPERSON, ROLE_WAREHOUSE_OPERATOR


@unittest.skipUnless(
    getattr(frappe.local, "site", None), "Requires bench site test runner"
)
class TestSitePermissions(IntegrationTestCase):
    def setUp(self):
        super().setUp()
        frappe.db.savepoint("clothing_test_case")
        self.previous_user = frappe.session.user
        frappe.set_user("Administrator")
        self.email = "test-clothing-salesperson@example.invalid"
        self.rsm_email = "test-clothing-rsm@example.invalid"
        if not frappe.db.exists("User", self.email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": self.email,
                    "first_name": "Test Clothing",
                    "send_welcome_email": 0,
                    "roles": [{"role": ROLE_SALESPERSON}],
                }
            ).insert()
        if not frappe.db.exists("User", self.rsm_email):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": self.rsm_email,
                    "first_name": "Test Clothing RSM",
                    "send_welcome_email": 0,
                    "roles": [{"role": ROLE_RSM}],
                }
            ).insert()

    def tearDown(self):
        frappe.set_user(self.previous_user)
        frappe.db.rollback(save_point="clothing_test_case")
        frappe.clear_cache(user=self.email)
        frappe.clear_cache(user=self.rsm_email)
        super().tearDown()

    def _assign_sales_territory(self, territory, user=None):
        asm = user or self.email
        frappe.set_user("Administrator")
        supervision.assign_asm_supervision(
            asm=asm,
            rsm=self.rsm_email,
            territory=territory,
            reason="TEST integration territory assignment",
        )
        frappe.clear_cache(user=asm)

    def test_unassigned_salesperson_cannot_list_any_retailers(self):
        frappe.set_user(self.email)
        self.assertTrue(frappe.db.exists("Page", "clothing-catalogue"))
        gallery = frappe.get_meta("Item").get_field("custom_clothing_product_images")
        self.assertEqual(
            (gallery.fieldtype, gallery.options), ("Table", "Clothing Product Image")
        )
        request_id = frappe.get_meta("Sales Order").get_field(
            "custom_clothing_request_id"
        )
        self.assertTrue(request_id.unique)
        self.assertTrue(frappe.db.has_column("Contact", "is_billing_contact"))
        self.assertTrue(request_id.read_only)
        self.assertEqual(frappe.get_list("Customer", pluck="name"), [])
        with self.assertRaises(frappe.PermissionError):
            frappe.get_list("Sales Order", pluck="name")
        self.assertEqual(
            api.get_salesperson_dashboard()["metrics"]["assigned_retailers_count"], 0
        )
        with self.assertRaises(frappe.PermissionError):
            api.switch_preview_role("Administrator")
        with self.assertRaises(frappe.PermissionError):
            api.get_warehouse_dashboard()

    def test_native_territory_permission_controls_customer_access(self):
        for doctype, field, value in (
            ("Customer Group", "customer_group_name", "TEST Clothing Group"),
            ("Territory", "territory_name", "TEST Clothing Territory"),
        ):
            if not frappe.db.exists(doctype, value):
                frappe.get_doc(
                    {"doctype": doctype, field: value, "is_group": 0}
                ).insert()
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": "TEST Clothing Assigned Retailer",
                "customer_type": "Company",
                "customer_group": "TEST Clothing Group",
                "territory": "TEST Clothing Territory",
            }
        ).insert()
        second_customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": "TEST Clothing Same Territory Retailer",
                "customer_type": "Company",
                "customer_group": "TEST Clothing Group",
                "territory": "TEST Clothing Territory",
            }
        ).insert()
        self._assign_sales_territory("TEST Clothing Territory")
        frappe.set_user(self.email)
        self.assertTrue(security.has_retailer_access(customer.name))
        visible = set(frappe.get_list("Customer", pluck="name"))
        self.assertTrue({customer.name, second_customer.name}.issubset(visible))
        self.assertTrue(frappe.has_permission("Customer", "read", customer.name))
        self.assertFalse(security.has_retailer_access("TEST Unassigned Retailer"))

    def test_operator_queries_with_native_warehouse_assignment(self):
        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": "test-clothing-warehouse@example.invalid",
                "first_name": "TEST Warehouse",
                "send_welcome_email": 0,
                "roles": [{"role": ROLE_WAREHOUSE_OPERATOR}],
            }
        ).insert()
        # Minimal relational fixture: no company/accounting setup is needed to exercise SQL scopes.
        warehouse = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "name": "TEST Clothing Warehouse",
                "warehouse_name": "TEST Clothing Warehouse",
                "is_group": 0,
            }
        )
        warehouse.db_insert()
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": user.name,
                "allow": "Warehouse",
                "for_value": warehouse.name,
                "hide_descendants": 1,
                "apply_to_all_doctypes": 1,
            }
        ).insert()
        frappe.clear_cache(user=user.name)
        frappe.set_user(user.name)
        self.assertEqual(frappe.get_list("Warehouse", pluck="name"), [warehouse.name])
        self.assertEqual(frappe.get_list("Pick List", pluck="name"), [])
        self.assertEqual(frappe.get_list("Delivery Note", pluck="name"), [])
        self.assertEqual(api.get_warehouse_dashboard()["pick_tasks"], [])

    def test_pick_verification_and_completion_use_native_pick_list(self):
        from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

        company = frappe.defaults.get_global_default("company")
        frappe.db.set_single_value(
            "Stock Settings", "enable_serial_and_batch_no_for_item", 1
        )
        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": "TEST-PICK-SCAN-ITEM",
                "item_name": "TEST Pick Scan Item",
                "item_group": "Products",
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "gst_hsn_code": "61091000",
            }
        ).insert()
        warehouse = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "TEST Pick Scan Warehouse",
                "company": company,
                "is_group": 0,
            }
        ).insert()
        make_stock_entry(
            item_code=item.name,
            target=warehouse.name,
            qty=10,
            basic_rate=100,
            company=company,
        )
        batch_item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": "TEST-PICK-BATCH-ITEM",
                "item_name": "TEST Pick Batch Item",
                "item_group": "Products",
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "gst_hsn_code": "61091000",
                "has_batch_no": 1,
                "create_new_batch": 1,
            }
        ).insert()
        batch = frappe.get_doc(
            {"doctype": "Batch", "item": batch_item.name}
        ).insert()
        make_stock_entry(
            item_code=batch_item.name,
            target=warehouse.name,
            qty=2,
            batch_no=batch.name,
            basic_rate=100,
            company=company,
        )
        serial_item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": "TEST-PICK-SERIAL-ITEM",
                "item_name": "TEST Pick Serial Item",
                "item_group": "Products",
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "gst_hsn_code": "61091000",
                "has_serial_no": 1,
                "serial_no_series": "TEST-PICK-SERIAL-.#####",
            }
        ).insert()
        serial_receipt = make_stock_entry(
            item_code=serial_item.name,
            target=warehouse.name,
            qty=1,
            basic_rate=100,
            company=company,
        )
        serial_no = frappe.db.get_value(
            "Serial and Batch Entry",
            {"parent": serial_receipt.items[0].serial_and_batch_bundle},
            "serial_no",
        )
        pick_list = frappe.get_doc(
            {
                "doctype": "Pick List",
                "company": company,
                "purpose": "Material Transfer",
                "pick_manually": 1,
                "locations": [
                    {
                        "item_code": item.name,
                        "item_name": item.item_name,
                        "warehouse": warehouse.name,
                        "qty": 3,
                        "stock_qty": 3,
                        "uom": item.stock_uom,
                        "stock_uom": item.stock_uom,
                        "conversion_factor": 1,
                        "picked_qty": 0,
                    },
                    {
                        "item_code": batch_item.name,
                        "item_name": batch_item.item_name,
                        "warehouse": warehouse.name,
                        "qty": 2,
                        "stock_qty": 2,
                        "uom": batch_item.stock_uom,
                        "stock_uom": batch_item.stock_uom,
                        "conversion_factor": 1,
                        "picked_qty": 0,
                        "batch_no": batch.name,
                        "use_serial_batch_fields": 1,
                    },
                    {
                        "item_code": serial_item.name,
                        "item_name": serial_item.item_name,
                        "warehouse": warehouse.name,
                        "qty": 1,
                        "stock_qty": 1,
                        "uom": serial_item.stock_uom,
                        "stock_uom": serial_item.stock_uom,
                        "conversion_factor": 1,
                        "picked_qty": 0,
                        "serial_no": serial_no,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        ).insert()
        resolution = fulfillment.resolve_pick_shortage(
            pick_list.name, "TEST refresh all unpicked stock locations"
        )
        self.assertEqual(resolution["unallocated_qty"], 0)
        self.assertTrue(
            frappe.db.exists(
                "Comment",
                {
                    "reference_doctype": "Pick List",
                    "reference_name": pick_list.name,
                    "content": ["like", "%Clothing ERP shortage resolution%"],
                },
            )
        )
        pick_list.reload()
        locations = {row.item_code: row for row in pick_list.locations}
        location = locations[item.name]
        batch_location = locations[batch_item.name]
        serial_location = locations[serial_item.name]
        scanner = frappe.get_doc(
            {
                "doctype": "User",
                "email": "test-clothing-scanner@example.invalid",
                "first_name": "TEST Clothing Scanner",
                "send_welcome_email": 0,
                "roles": [{"role": ROLE_WAREHOUSE_OPERATOR}],
            }
        ).insert()
        frappe.get_doc(
            {
                "doctype": "User Permission",
                "user": scanner.name,
                "allow": "Warehouse",
                "for_value": warehouse.name,
                "apply_to_all_doctypes": 1,
            }
        ).insert()
        assignment = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": scanner.name,
                "reference_type": "Pick List",
                "reference_name": pick_list.name,
                "status": "Open",
                "description": "TEST assigned clothing pick",
            }
        ).insert()
        frappe.clear_cache(user=scanner.name)
        frappe.set_user(scanner.name)
        try:
            result = fulfillment.verify_pick_item(
                pick_list.name, location.name, item.name, 2
            )
            pick_list.reload()
            self.assertEqual(
                next(
                    row.picked_qty
                    for row in pick_list.locations
                    if row.item_code == item.name
                ),
                2,
            )
            self.assertEqual(result["item_code"], item.name)
            self.assertFalse(result["complete"])
            with self.assertRaises(frappe.ValidationError):
                fulfillment.complete_pick_list(pick_list.name)
            fulfillment.verify_pick_item(
                pick_list.name, location.name, item.name, 1
            )
            batch_result = fulfillment.verify_pick_item(
                pick_list.name, batch_location.name, batch.name, 2
            )
            self.assertEqual(batch_result["scan_type"], "batch")
            self.assertEqual(batch_result["batch_no"], batch.name)
            serial_result = fulfillment.verify_pick_item(
                pick_list.name, serial_location.name, serial_no
            )
            self.assertEqual(serial_result["scan_type"], "serial")
            self.assertEqual(serial_result["serial_no"], serial_no)
            detail = fulfillment.get_fulfillment_task("pick", pick_list.name)
            self.assertTrue(detail["can_complete_pick"])
            completion = fulfillment.complete_pick_list(pick_list.name)
        finally:
            frappe.set_user("Administrator")
            frappe.clear_cache(user=scanner.name)
        pick_list.reload()
        assignment.reload()
        locations = {row.item_code: row for row in pick_list.locations}
        self.assertEqual(pick_list.docstatus, 1)
        self.assertEqual(locations[item.name].picked_qty, 3)
        self.assertEqual(locations[batch_item.name].picked_qty, 2)
        self.assertEqual(locations[batch_item.name].batch_no, batch.name)
        self.assertEqual(locations[serial_item.name].picked_qty, 1)
        self.assertEqual(locations[serial_item.name].serial_no, serial_no)
        self.assertEqual(completion["docstatus"], 1)
        self.assertEqual(assignment.status, "Closed")

    def test_catalogue_reads_real_erpnext_variants_prices_and_stock(self):
        from erpnext.controllers.item_variant import create_variant

        frappe.set_user("Administrator")
        for attribute, values in (
            ("TEST Clothing Colour", (("Black", "BLK"),)),
            ("TEST Clothing Size", (("Medium", "M"),)),
        ):
            frappe.get_doc(
                {
                    "doctype": "Item Attribute",
                    "attribute_name": attribute,
                    "item_attribute_values": [
                        {"attribute_value": value, "abbr": abbreviation}
                        for value, abbreviation in values
                    ],
                }
            ).insert()

        template = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": "TEST-CLOTHING-CATALOGUE",
                "item_name": "TEST Clothing Catalogue Shirt",
                "description": "Fictional integration-test garment",
                "item_group": "Products",
                "stock_uom": "Nos",
                "gst_hsn_code": "61091000",
                "has_variants": 1,
                "variant_based_on": "Item Attribute",
                "attributes": [
                    {"attribute": "TEST Clothing Colour"},
                    {"attribute": "TEST Clothing Size"},
                ],
                "custom_clothing_product_images": [
                    {
                        "image": "/assets/clothing_erp/images/seed/test-classic-tee.jpg",
                        "caption": "TEST catalogue front",
                    }
                ],
            }
        ).insert()
        variant = create_variant(
            template.name,
            {
                "TEST Clothing Colour": "Black",
                "TEST Clothing Size": "Medium",
            },
        )
        variant.item_code = "TEST-CLOTHING-CATALOGUE-BLK-M"
        variant.item_name = "TEST Clothing Catalogue Shirt Black Medium"
        variant.insert()

        price_list = frappe.db.get_single_value(
            "Selling Settings", "selling_price_list"
        )
        frappe.get_doc(
            {
                "doctype": "Item Price",
                "price_list": price_list,
                "item_code": variant.name,
                "uom": variant.stock_uom,
                "price_list_rate": 749,
            }
        ).insert()
        warehouse = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": "TEST Catalogue Warehouse",
                "is_group": 0,
            }
        )
        warehouse.db_insert()
        frappe.get_doc(
            {
                "doctype": "Bin",
                "item_code": variant.name,
                "warehouse": warehouse.name,
                "stock_uom": variant.stock_uom,
                "actual_qty": 17,
            }
        ).db_insert()

        result = catalogue.get_catalogue(search="Catalogue Shirt")
        self.assertEqual(len(result["products"]), 1)
        self.assertEqual(
            result["products"][0]["images"][0]["caption"], "TEST catalogue front"
        )
        row = result["products"][0]["variants"][0]
        self.assertEqual(row["item_code"], variant.name)
        self.assertEqual(row["price"], 749)
        self.assertEqual(row["actual_qty"], 17)
        self.assertEqual(
            {(value["attribute"], value["value"]) for value in row["attributes"]},
            {("TEST Clothing Colour", "Black"), ("TEST Clothing Size", "Medium")},
        )
        for doctype, field, value in (
            ("Customer Group", "customer_group_name", "TEST Catalogue Retailers"),
            ("Territory", "territory_name", "TEST Catalogue Territory"),
        ):
            if not frappe.db.exists(doctype, value):
                frappe.get_doc(
                    {"doctype": doctype, field: value, "is_group": 0}
                ).insert()
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": "TEST Catalogue Pricing Retailer",
                "customer_type": "Company",
                "customer_group": "TEST Catalogue Retailers",
                "territory": "TEST Catalogue Territory",
            }
        ).insert()
        customer_prices, price_list_name, currency = get_customer_prices(
            customer.name, [variant.name]
        )
        self.assertEqual(customer_prices[variant.name]["rate"], 749)
        self.assertEqual(price_list_name, price_list)
        self.assertEqual(currency, "INR")

        self._assign_sales_territory(customer.territory)
        frappe.set_user(self.email)
        assigned_prices, assigned_price_list, assigned_currency = get_customer_prices(
            customer.name, [variant.name]
        )
        self.assertEqual(assigned_prices[variant.name]["rate"], 749)
        self.assertEqual(assigned_price_list, price_list)
        self.assertEqual(assigned_currency, "INR")

    def test_retailer_application_approval_creates_native_customer_and_assignment(self):
        for doctype, field, value, parent_field, parent in (
            (
                "Territory",
                "territory_name",
                "TEST Stage Four Territory",
                "parent_territory",
                "All Territories",
            ),
        ):
            if not frappe.db.exists(doctype, value):
                frappe.get_doc(
                    {
                        "doctype": doctype,
                        field: value,
                        parent_field: parent,
                        "is_group": 0,
                    }
                ).insert()
        self._assign_sales_territory("TEST Stage Four Territory")
        frappe.set_user(self.email)
        application = frappe.get_doc(
            {
                "doctype": "Retailer Application",
                "shop_name": "TEST Stage Four Boutique",
                "contact_person": "TEST Retail Contact",
                "phone": "+91 90000 12345",
                "email": "test-stage-four@example.invalid",
                "gstin": "TESTGSTIN123",
                "territory": "TEST Stage Four Territory",
                "customer_group": "Buy & Sell",
                "salesperson": self.email,
                "billing_address_line1": "TEST 10 Fictional Market Road",
                "billing_city": "TEST City",
                "billing_state": "Maharashtra",
                "country": "India",
                "shipping_address_line1": "TEST 20 Fictional Warehouse Road",
                "shipping_city": "TEST City",
                "shipping_state": "Maharashtra",
                "notes": "Fictional integration test application.",
            }
        ).insert()
        self.assertEqual(application.status, "Pending")
        frappe.set_user("Administrator")
        result = approve(application.name)
        application.reload()
        self.assertEqual(result["status"], "Approved")
        self.assertTrue(application.customer)
        self.assertTrue(frappe.db.exists("Customer", application.customer))
        self.assertTrue(frappe.db.exists("Contact", {"email_id": application.email}))
        self.assertEqual(
            frappe.db.count("Address", {"address_title": application.shop_name}), 2
        )
        frappe.clear_cache(user=self.email)
        frappe.set_user(self.email)
        self.assertTrue(security.has_retailer_access(application.customer))
        visit = frappe.get_doc(
            {
                "doctype": "Retailer Visit",
                "customer": application.customer,
                "salesperson": self.email,
                "visit_date": now_datetime(),
                "outcome": "Follow-up Required",
                "notes": "TEST fictional retailer follow-up.",
                "follow_up_date": add_days(now_datetime(), 7),
            }
        ).insert()
        self.assertEqual(visit.salesperson, self.email)
        self.assertTrue(security.has_retailer_access(application.customer))

    def test_retailer_application_rejection_is_final(self):
        for doctype, field, value, parent_field, parent in (
            (
                "Territory",
                "territory_name",
                "TEST Stage Four Territory",
                "parent_territory",
                "All Territories",
            ),
        ):
            if not frappe.db.exists(doctype, value):
                frappe.get_doc(
                    {
                        "doctype": doctype,
                        field: value,
                        parent_field: parent,
                        "is_group": 0,
                    }
                ).insert()
        self._assign_sales_territory("TEST Stage Four Territory")
        frappe.set_user(self.email)
        application = frappe.get_doc(
            {
                "doctype": "Retailer Application",
                "shop_name": "TEST Rejected Stage Four Boutique",
                "contact_person": "TEST Rejected Contact",
                "phone": "+91 90000 54321",
                "email": "test-rejected-stage-four@example.invalid",
                "territory": "TEST Stage Four Territory",
                "customer_group": "SIS (Shop-in-Shop)",
                "salesperson": self.email,
                "billing_address_line1": "TEST 30 Fictional Market Road",
                "billing_city": "TEST City",
                "billing_state": "Maharashtra",
                "country": "India",
            }
        ).insert()
        frappe.set_user("Administrator")
        result = reject(application.name, "TEST duplicate registration")
        application.reload()
        self.assertEqual(result["status"], "Rejected")
        self.assertEqual(application.rejection_reason, "TEST duplicate registration")
        self.assertFalse(application.customer)
        with self.assertRaises(frappe.ValidationError):
            approve(application.name)
        application.notes = "Attempted edit after review"
        with self.assertRaises(frappe.ValidationError):
            application.save()

    def test_rsm_supervision_model_and_approval_workflow(self):
        territory_name = "TEST Supervision Territory"
        if not frappe.db.exists("Territory", territory_name):
            frappe.get_doc(
                {
                    "doctype": "Territory",
                    "territory_name": territory_name,
                    "parent_territory": "All Territories",
                    "is_group": 0,
                }
            ).insert()

        asm_email = "test-super-asm@example.invalid"
        rsm1_email = "test-super-rsm1@example.invalid"
        rsm2_email = "test-super-rsm2@example.invalid"

        for email, role, first_name in (
            (asm_email, ROLE_ASM, "Test Super ASM"),
            (rsm1_email, ROLE_RSM, "Test Super RSM 1"),
            (rsm2_email, ROLE_RSM, "Test Super RSM 2"),
        ):
            if not frappe.db.exists("User", email):
                frappe.get_doc(
                    {
                        "doctype": "User",
                        "email": email,
                        "first_name": first_name,
                        "send_welcome_email": 0,
                        "roles": [{"role": role}],
                    }
                ).insert()
        frappe.set_user("Administrator")
        assign_res = supervision.assign_asm_supervision(
            asm=asm_email,
            rsm=rsm1_email,
            territory=territory_name,
            effective_from=frappe.utils.nowdate(),
            reason="Initial territory assignment",
        )
        self.assertFalse(assign_res["unchanged"])
        sup1_name = assign_res["name"]
        self.assertEqual(security.assigned_sales_territories(asm_email), [territory_name])
        self.assertEqual(security.assigned_sales_territories(rsm1_email), [territory_name])
        self.assertTrue(
            frappe.db.exists(
                "User Permission",
                {"user": asm_email, "allow": "Territory", "for_value": territory_name},
            )
        )

        # 1. Assigned ASM creates an application
        frappe.set_user(asm_email)
        app1 = frappe.get_doc(
            {
                "doctype": "Retailer Application",
                "shop_name": "TEST Supervised Boutique 1",
                "contact_person": "TEST Contact 1",
                "phone": "+91 90000 66661",
                "email": "test-super-app1@example.invalid",
                "territory": territory_name,
                "customer_group": "Buy & Sell",
                "salesperson": asm_email,
                "billing_address_line1": "TEST 1 Market Road",
                "billing_city": "TEST City",
                "billing_state": "Maharashtra",
                "country": "India",
            }
        ).insert()

        # 2. RSM 2 attempts approval -> rejected because RSM 2 does not supervise ASM
        frappe.set_user(rsm2_email)
        with self.assertRaises(frappe.PermissionError):
            approve(app1.name)

        # 3. RSM 1 approves -> succeeds
        frappe.set_user(rsm1_email)
        res1 = approve(app1.name)
        self.assertEqual(res1["status"], "Approved")

        # 4. Administrator reassigns the Territory and ASM to RSM 2
        frappe.set_user("Administrator")
        reassign_res = supervision.assign_asm_supervision(
            asm=asm_email,
            rsm=rsm2_email,
            territory=territory_name,
            effective_from=frappe.utils.nowdate(),
            reason="Reassigned to RSM 2",
        )
        self.assertEqual(len(reassign_res["superseded"]), 1)
        self.assertEqual(reassign_res["superseded"][0], sup1_name)

        old_sup = frappe.get_doc("ASM Supervision", sup1_name)
        self.assertEqual(old_sup.status, "Superseded")

        new_sup = frappe.get_doc("ASM Supervision", reassign_res["name"])
        self.assertEqual(new_sup.status, "Active")
        self.assertEqual(new_sup.rsm, rsm2_email)
        self.assertFalse(
            frappe.db.exists(
                "User Permission",
                {"user": rsm1_email, "allow": "Territory", "for_value": territory_name},
            )
        )
        self.assertTrue(
            frappe.db.exists(
                "User Permission",
                {"user": rsm2_email, "allow": "Territory", "for_value": territory_name},
            )
        )

        # 5. ASM creates a second application
        frappe.set_user(asm_email)
        app2 = frappe.get_doc(
            {
                "doctype": "Retailer Application",
                "shop_name": "TEST Supervised Boutique 2",
                "contact_person": "TEST Contact 2",
                "phone": "+91 90000 66662",
                "email": "test-super-app2@example.invalid",
                "territory": territory_name,
                "customer_group": "SIS (Shop-in-Shop)",
                "salesperson": asm_email,
                "billing_address_line1": "TEST 2 Market Road",
                "billing_city": "TEST City",
                "billing_state": "Maharashtra",
                "country": "India",
            }
        ).insert()

        # 6. RSM 1 attempts approval on second application -> rejected
        frappe.set_user(rsm1_email)
        with self.assertRaises(frappe.PermissionError):
            approve(app2.name)

        # 7. RSM 2 approves second application -> succeeds
        frappe.set_user(rsm2_email)
        res2 = approve(app2.name)
        self.assertEqual(res2["status"], "Approved")

        # 8. Administrator ends the Territory assignment
        frappe.set_user("Administrator")
        supervision.end_asm_supervision(new_sup.name, reason="Testing end supervision")
        new_sup.reload()
        self.assertEqual(new_sup.status, "Cancelled")
        self.assertEqual(security.assigned_sales_territories(asm_email), [])
        self.assertEqual(security.assigned_sales_territories(rsm2_email), [])

    def test_legacy_sales_roles_do_not_exist_in_database(self):
        self.assertFalse(frappe.db.exists("Role", "Clothing Salesperson"))
        self.assertFalse(frappe.db.exists("Role", "Clothing Sales Manager"))
