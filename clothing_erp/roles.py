"""Role definitions and configurations for Clothing ERP."""

# Operational Roles
ROLE_SALESPERSON = "Clothing Salesperson"
ROLE_WAREHOUSE_OPERATOR = "Clothing Warehouse Operator"

# Management Roles
ROLE_SALES_MANAGER = "Clothing Sales Manager"
ROLE_WAREHOUSE_MANAGER = "Clothing Warehouse Manager"
ROLE_BUSINESS_ADMIN = "Clothing Business Administrator"

# All defined Clothing ERP roles with their metadata
ALL_ROLES = [
	{
		"role_name": ROLE_SALESPERSON,
		"desk_access": 1,
		"description": "Operational role for wholesale salespeople. Can view assigned retailers, browse catalog, create orders, and log visits.",
		"home_page": "salesperson-portal",
	},
	{
		"role_name": ROLE_WAREHOUSE_OPERATOR,
		"desk_access": 1,
		"description": "Operational role for warehouse staff. Can view assigned pick lists, pack orders, scan barcodes, and confirm dispatch.",
		"home_page": "warehouse-operations",
	},
	{
		"role_name": ROLE_SALES_MANAGER,
		"desk_access": 1,
		"description": "Management role for sales oversight. Can assign retailers, approve discounts, review performance, and approve registrations.",
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
