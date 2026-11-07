"""Frappe app hooks for clothing_erp."""

app_name = "clothing_erp"
app_title = "Clothing ERP"
app_publisher = "Clothing ERP Contributors"
app_description = "Open-Source Clothing Distribution ERP built on Frappe and ERPNext"
app_email = "team@clothing-erp.invalid"
app_license = "mit"

required_apps = ["erpnext"]

# Routing and Portal
home_page = "clothing"

website_route_rules = [
	{"from_route": "/", "to_route": "clothing"},
	{"from_route": "/clothing-erp", "to_route": "clothing"},
]

# Installation
after_install = "clothing_erp.install.after_install"
