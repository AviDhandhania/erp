"""Role definitions and configurations for Clothing ERP."""

# Field Sales Roles
ROLE_ASM = "Clothing Area Sales Manager"
ROLE_RSM = "Clothing Regional Sales Manager"

# Source-compatible aliases. New permissions and stored role assignments use the
# business names above; these aliases keep existing service modules readable
# while the wider sales workflow is migrated in small, testable slices.
ROLE_SALESPERSON = ROLE_ASM
ROLE_SALES_MANAGER = ROLE_RSM

LEGACY_ROLE_SALESPERSON = "Clothing Salesperson"
LEGACY_ROLE_SALES_MANAGER = "Clothing Sales Manager"

# Warehouse roles
ROLE_WAREHOUSE_OPERATOR = "Clothing Warehouse Operator"

# Management Roles
ROLE_WAREHOUSE_MANAGER = "Clothing Warehouse Manager"
ROLE_BUSINESS_ADMIN = "Clothing Business Administrator"

# All defined Clothing ERP roles with their metadata
ALL_ROLES = [
	{
		"role_name": ROLE_ASM,
		"desk_access": 1,
		"description": "Area Sales Manager. Works with every retailer in assigned territories, creates applications and orders, and records visits.",
		"home_page": "salesperson-portal",
	},
	{
		"role_name": ROLE_WAREHOUSE_OPERATOR,
		"desk_access": 1,
		"description": "Operational role for warehouse staff. Can view assigned pick lists, pack orders, scan barcodes, and confirm dispatch.",
		"home_page": "warehouse-operations",
	},
	{
		"role_name": ROLE_RSM,
		"desk_access": 1,
		"description": "Regional Sales Manager. Supervises field sales, reviews retailer applications, visits, and orders in assigned territories.",
		"home_page": "clothing-erp",
	},
	{
		"role_name": ROLE_WAREHOUSE_MANAGER,
		"desk_access": 1,
		"description": "Management role for inventory control. Can assign picking tasks, resolve stock discrepancies, and manage warehouse entries.",
		"home_page": "clothing-erp",
	},
	{
		"role_name": ROLE_BUSINESS_ADMIN,
		"desk_access": 1,
		"description": "Business oversight across all clothing distribution operations, catalogues, and pricing policies.",
		"home_page": "clothing-erp",
	},
]

# Standard System Manager and Administrator have full access across all operations
SUPER_USER_ROLES = {"Administrator", "System Manager"}
MANAGEMENT_ROLES = {ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER, ROLE_WAREHOUSE_MANAGER}
OPERATIONAL_ROLES = {ROLE_SALESPERSON, ROLE_WAREHOUSE_OPERATOR}
