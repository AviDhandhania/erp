"""Frappe app hooks for clothing_erp."""

app_name = "clothing_erp"
app_title = "Clothing ERP"
app_publisher = "Clothing ERP Contributors"
app_description = "Open-Source Clothing Distribution ERP built on Frappe and ERPNext"
app_email = "team@clothing-erp.invalid"
app_license = "mit"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "clothing_erp",
		"logo": "/assets/clothing_erp/images/clothing_erp_logo.svg",
		"title": "Clothing ERP",
		"route": "/desk/clothing-erp",
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

# Document Permission Hooks (Document-level access control)
has_permission = {
	"Customer": "clothing_erp.security.has_retailer_access",
}

permission_query_conditions = {
	"Customer": "clothing_erp.security.get_salesperson_customer_conditions",
}
