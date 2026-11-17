"""Frappe app hooks for sales_erp."""

app_name = "sales_erp"
app_title = "Sales ERP"
app_publisher = "Clothing ERP Contributors"
app_description = "Wholesale apparel sales, interactive catalogue, draft ordering, and territory management"
app_email = "team@clothing-erp.invalid"
app_license = "mit"
app_logo_url = "/assets/sales_erp/images/sales_erp_logo.svg"
app_home = "/desk/sales-erp"

required_apps = ["erpnext", "insights", "india_compliance"]

doctype_js = {
	"Retailer Application": "public/js/retailer_application.js",
}

add_to_apps_screen = [
	{
		"name": "sales_erp",
		"logo": "/assets/sales_erp/images/sales_erp_logo.svg",
		"title": "Sales ERP",
		"route": "/desk/sales-erp",
		"has_permission": "sales_erp.security.has_sales_app_access",
		"setup_wizard_text": "Configure wholesale clothing sales and territory management.",
	}
]

# Routing & Portal Homepage
home_page = "clothing"

website_route_rules = [
	{"from_route": "/", "to_route": "clothing"},
	{"from_route": "/clothing-erp", "to_route": "clothing"},
	{"from_route": "/sales-erp", "to_route": "clothing"},
	{"from_route": "/salesperson", "to_route": "clothing"},
	{"from_route": "/warehouse", "to_route": "clothing"},
	{"from_route": "/quality", "to_route": "clothing"},
]

# Lifecycle Installation & Migrations
after_install = "sales_erp.install.after_install"
after_migrate = "sales_erp.install.after_migrate"

extend_bootinfo = "sales_erp.boot.restrict_sales_app_visibility"
boot_session = "sales_erp.boot.restrict_sales_app_visibility"

before_request = [
	"sales_erp.boot.apply_runtime_patches",
	"sales_erp.insights_compat.enforce_insights_admin_access",
]

override_whitelisted_methods = {
	"insights.setup.setup_wizard.setup_demo_data": "sales_erp.insights_compat.setup_demo_data",
}

doc_events = {
	"Item": {
		"on_update": "sales_erp.gallery.cleanup_removed_gallery_files",
	},
	"Delivery Note": {
		"on_submit": "sales_erp.delivery_follow_up.on_delivery_note_submitted",
	},
}

scheduler_events = {
	"daily": ["sales_erp.cadence.evaluate_rsm_visit_cadence"],
	"daily_long": ["sales_erp.gallery.cleanup_orphan_gallery_files"],
}

# Document Permission Hooks (Document-level access control)
has_permission = {
	"Customer": "sales_erp.security.customer_has_permission",
	"Sales Order": "sales_erp.security.operational_document_has_permission",
	"Retailer Application": "sales_erp.security.retailer_record_has_permission",
	"Retailer Visit": "sales_erp.security.retailer_record_has_permission",
	"Retailer Credit Limit Request": "sales_erp.security.retailer_credit_limit_request_has_permission",
	"RSM Visit Obligation": "sales_erp.sales_erp.doctype.rsm_visit_obligation.rsm_visit_obligation.rsm_visit_obligation_has_permission",
	"Delivery Follow-Up Obligation": "sales_erp.delivery_follow_up.delivery_follow_up_has_permission",
	"ASM Supervision": "sales_erp.security.asm_supervision_has_permission",
	"Retailer Assignment History": "sales_erp.security.retailer_assignment_history_has_permission",
	"User": "sales_erp.security.user_has_permission",
}

permission_query_conditions = {
	"Customer": "sales_erp.security.get_salesperson_customer_conditions",
	"Sales Order": "sales_erp.security.sales_order_conditions",
	"Retailer Application": "sales_erp.security.retailer_application_conditions",
	"Retailer Visit": "sales_erp.security.retailer_visit_conditions",
	"Retailer Credit Limit Request": "sales_erp.security.retailer_credit_limit_request_conditions",
	"RSM Visit Obligation": "sales_erp.sales_erp.doctype.rsm_visit_obligation.rsm_visit_obligation.rsm_visit_obligation_query_conditions",
	"Delivery Follow-Up Obligation": "sales_erp.delivery_follow_up.delivery_follow_up_query_conditions",
	"ASM Supervision": "sales_erp.security.asm_supervision_conditions",
	"Retailer Assignment History": "sales_erp.security.retailer_assignment_history_conditions",
	"User": "sales_erp.security.user_query_conditions",
}
