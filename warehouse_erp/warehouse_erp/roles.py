"""Canonical roles for Warehouse ERP."""

LEGACY_ROLE_WAREHOUSE_OPERATOR = "Clothing Warehouse Operator"
ROLE_WAREHOUSE_OPERATOR = LEGACY_ROLE_WAREHOUSE_OPERATOR
ROLE_WAREHOUSE_MANAGER = "Clothing Warehouse Manager"
ROLE_BUSINESS_ADMIN = "Clothing Business Administrator"

# Canonical active roles for Warehouse ERP; legacy operator is migrated to manager.
ALL_ROLES = (
    {"role_name": ROLE_WAREHOUSE_MANAGER},
    {"role_name": ROLE_BUSINESS_ADMIN},
)
