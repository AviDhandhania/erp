"""Canonical roles for Sales ERP."""

ROLE_ASM = "Clothing Area Sales Manager"
ROLE_RSM = "Clothing Regional Sales Manager"
ROLE_SALESPERSON = ROLE_ASM
ROLE_SALES_MANAGER = ROLE_RSM
ROLE_BUSINESS_ADMIN = "Clothing Business Administrator"
ROLE_WAREHOUSE_OPERATOR = "Clothing Warehouse Operator"
ROLE_WAREHOUSE_MANAGER = "Clothing Warehouse Manager"

SUPER_USER_ROLES = {"System Manager", "Administrator"}

# Deprecated/retired role names
LEGACY_ROLE_SALESPERSON = "Clothing Salesperson"
LEGACY_ROLE_SALES_MANAGER = "Clothing Sales Manager"

ALL_ROLES = (
    {"role_name": ROLE_ASM},
    {"role_name": ROLE_RSM},
    {"role_name": ROLE_BUSINESS_ADMIN},
)
