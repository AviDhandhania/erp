"""Frappe app hooks for warehouse_erp."""

app_name = "warehouse_erp"
app_title = "Warehouse ERP"
app_publisher = "Clothing ERP Contributors"
app_description = "Warehouse fulfillment scanning, pick lists, dispatch, and stock movements"
app_email = "team@clothing-erp.invalid"
app_license = "mit"
app_logo_url = "/assets/warehouse_erp/images/warehouse_erp_logo.svg"
app_home = "/desk/warehouse-erp"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "warehouse_erp",
		"logo": "/assets/warehouse_erp/images/warehouse_erp_logo.svg",
		"title": "Warehouse ERP",
		"route": "/desk/warehouse-erp",
		"has_permission": "warehouse_erp.security.has_warehouse_app_access",
		"setup_wizard_text": "Configure warehouse operations and fulfillment.",
	}
]

# Routing
website_route_rules = [
	{"from_route": "/warehouse-erp", "to_route": "clothing"},
	{"from_route": "/warehouse", "to_route": "clothing"},
]

# Lifecycle Installation & Migrations
after_install = "warehouse_erp.install.after_install"
after_migrate = "warehouse_erp.install.after_migrate"

extend_bootinfo = "warehouse_erp.boot.restrict_warehouse_app_visibility"
boot_session = "warehouse_erp.boot.restrict_warehouse_app_visibility"

before_request = ["warehouse_erp.boot.apply_runtime_patches"]

# Document Permission Hooks (Document-level access control)
has_permission = {
	"File": "warehouse_erp.file_security.has_file_permission",
	"Warehouse": "warehouse_erp.security.warehouse_has_permission",
	"Pick List": "warehouse_erp.security.pick_list_has_permission",
	"Delivery Note": "warehouse_erp.security.delivery_note_has_permission",
	"Delivery Handoff": "warehouse_erp.security.delivery_handoff_has_permission",
	"Serial and Batch Bundle": "warehouse_erp.security.serial_batch_bundle_has_permission",
}

permission_query_conditions = {
	"Warehouse": "warehouse_erp.security.get_warehouse_conditions",
	"Pick List": "warehouse_erp.security.get_pick_list_conditions",
	"Delivery Note": "warehouse_erp.security.get_delivery_note_conditions",
	"Delivery Handoff": "warehouse_erp.security.get_delivery_handoff_conditions",
}
