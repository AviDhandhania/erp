"""Frappe app hooks for clothing_erp."""

app_name = "clothing_erp"
app_title = "Clothing ERP"
app_publisher = "Clothing ERP Contributors"
app_description = "Open-Source Clothing Distribution ERP built on Frappe and ERPNext"
app_email = "team@clothing-erp.invalid"
app_license = "mit"
app_logo_url = "/assets/clothing_erp/images/clothing_erp_logo.svg"
app_home = "/desk/clothing-erp"

required_apps = [
	"erpnext",
	"insights",
	"india_compliance",
	"sales_erp",
	"warehouse_erp",
	"quality_erp",
]

add_to_apps_screen = [
	{
		"name": "clothing_erp",
		"logo": "/assets/clothing_erp/images/clothing_erp_logo.svg",
		"title": "Clothing ERP",
		"route": "/desk/clothing-erp",
		"has_permission": "clothing_erp.security.has_app_access",
	}
]

# Routing & Portal Homepage
home_page = "clothing"

website_route_rules = [
	{"from_route": "/", "to_route": "clothing"},
	{"from_route": "/clothing-erp", "to_route": "clothing"},
	{"from_route": "/salesperson", "to_route": "clothing"},
	{"from_route": "/warehouse", "to_route": "clothing"},
	{"from_route": "/quality", "to_route": "clothing"},
]

# Lifecycle Installation & Migrations
after_install = "clothing_erp.install.after_install"
after_migrate = "clothing_erp.install.after_migrate"

extend_bootinfo = "clothing_erp.boot.restrict_app_and_workspace_visibility"
boot_session = "clothing_erp.boot.restrict_app_and_workspace_visibility"

before_request = [
	"clothing_erp.boot.apply_runtime_patches",
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

# Document Permission Hooks (Suite-level access control)
has_permission = {
	"User": "clothing_erp.security.user_has_permission",
}

permission_query_conditions = {
	"User": "clothing_erp.security.user_query_conditions",
}
