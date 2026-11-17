"""Frappe app hooks for quality_erp."""

app_name = "quality_erp"
app_title = "Quality ERP"
app_publisher = "Clothing ERP Contributors"
app_description = "Supplier quality inspection cycle, return quarantine, and refurbishment lifecycle"
app_email = "team@clothing-erp.invalid"
app_license = "mit"
app_logo_url = "/assets/quality_erp/images/quality_erp_logo.svg"
app_home = "/desk/quality-erp"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "quality_erp",
		"logo": "/assets/quality_erp/images/quality_erp_logo.svg",
		"title": "Quality ERP",
		"route": "/desk/quality-erp",
		"has_permission": "quality_erp.security.has_quality_app_access",
		"setup_wizard_text": "Configure supplier quality lifecycle and return quarantine.",
	}
]

# Routing
website_route_rules = [
	{"from_route": "/quality-erp", "to_route": "clothing"},
	{"from_route": "/quality", "to_route": "clothing"},
]

# Lifecycle Installation & Migrations
after_install = "quality_erp.install.after_install"
after_migrate = "quality_erp.install.after_migrate"

extend_bootinfo = "quality_erp.boot.restrict_quality_app_visibility"
boot_session = "quality_erp.boot.restrict_quality_app_visibility"

before_request = ["quality_erp.boot.apply_runtime_patches"]

# Document Permission Hooks (Document-level access control)
has_permission = {
	"File": "quality_erp.file_security.has_file_permission",
	"Supplier Quality Inspection": "quality_erp.security.quality_inspection_has_permission",
	"Return Quarantine": "quality_erp.security.return_quarantine_has_permission",
	"Production Quality Cycle": "quality_erp.security.production_quality_cycle_has_permission",
	"Quality Checklist Template": "quality_erp.security.quality_checklist_template_has_permission",
	"Supplier Quality Claim": "quality_erp.security.supplier_quality_claim_has_permission",
}

permission_query_conditions = {
	"Supplier Quality Inspection": "quality_erp.security.get_quality_inspection_conditions",
	"Return Quarantine": "quality_erp.security.get_return_quarantine_conditions",
	"Production Quality Cycle": "quality_erp.security.get_production_quality_cycle_conditions",
	"Supplier Quality Claim": "quality_erp.security.get_supplier_quality_claim_conditions",
}
