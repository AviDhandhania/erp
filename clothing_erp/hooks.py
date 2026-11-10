"""Frappe app hooks for clothing_erp."""

app_name = "clothing_erp"
app_title = "Clothing ERP"
app_publisher = "Clothing ERP Contributors"
app_description = "Open-Source Clothing Distribution ERP built on Frappe and ERPNext"
app_email = "team@clothing-erp.invalid"
app_license = "mit"
app_logo_url = "/assets/clothing_erp/images/clothing_erp_logo.svg"
app_home = "/desk/clothing-erp"

required_apps = ["erpnext", "insights"]

doctype_js = {
	"Retailer Application": "public/js/retailer_application.js",
}

add_to_apps_screen = [
	{
		"name": "clothing_erp",
		"logo": "/assets/clothing_erp/images/clothing_erp_logo.svg",
		"title": "Clothing ERP",
		"route": "/desk/clothing-erp",
		"has_permission": "clothing_erp.security.has_app_access",
		"setup_wizard_text": "Configure wholesale clothing distribution.",
	}
]

# Routing & Portal Homepage
home_page = "clothing"

website_route_rules = [
	{"from_route": "/", "to_route": "clothing"},
	{"from_route": "/clothing-erp", "to_route": "clothing"},
	{"from_route": "/salesperson", "to_route": "clothing"},
	{"from_route": "/warehouse", "to_route": "clothing"},
]

# Lifecycle Installation & Migrations
after_install = "clothing_erp.install.after_install"
after_migrate = "clothing_erp.install.after_migrate"

extend_bootinfo = "clothing_erp.boot.restrict_erpnext_app_visibility"

before_request = [
	"clothing_erp.insights_compat.enforce_insights_admin_access",
]

override_whitelisted_methods = {
	"insights.setup.setup_wizard.setup_demo_data": "clothing_erp.insights_compat.setup_demo_data",
}

doc_events = {
	"Item": {
		"on_update": "clothing_erp.gallery.cleanup_removed_gallery_files",
	}
}

scheduler_events = {
	"daily_long": ["clothing_erp.gallery.cleanup_orphan_gallery_files"],
}

# Document Permission Hooks (Document-level access control)
has_permission = {
	"Customer": "clothing_erp.security.customer_has_permission",
	"Warehouse": "clothing_erp.security.warehouse_has_permission",
	"Sales Order": "clothing_erp.security.operational_document_has_permission",
	"Delivery Note": "clothing_erp.security.operational_document_has_permission",
	"Pick List": "clothing_erp.security.operational_document_has_permission",
	"Serial and Batch Bundle": "clothing_erp.security.serial_batch_bundle_has_permission",
	"Retailer Application": "clothing_erp.security.retailer_record_has_permission",
	"Retailer Visit": "clothing_erp.security.retailer_record_has_permission",
	"User": "clothing_erp.security.user_has_permission",
}

permission_query_conditions = {
	"Customer": "clothing_erp.security.get_salesperson_customer_conditions",
	"Warehouse": "clothing_erp.security.get_operator_warehouse_conditions",
	"Sales Order": "clothing_erp.security.sales_order_conditions",
	"Delivery Note": "clothing_erp.security.delivery_note_conditions",
	"Pick List": "clothing_erp.security.pick_list_conditions",
	"Retailer Application": "clothing_erp.security.retailer_application_conditions",
	"Retailer Visit": "clothing_erp.security.retailer_visit_conditions",
	"User": "clothing_erp.security.user_query_conditions",
}
