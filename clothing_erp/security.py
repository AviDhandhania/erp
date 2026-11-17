"""Suite-level security, role validation, and backward-compatibility security routing."""
import frappe
from sales_erp.security import *  # noqa: F401, F403
from sales_erp.security import (
    ROLE_BUSINESS_ADMIN,
    has_any_role,
    is_clothing_admin,
    require_role,
)

# Warehouse permission helpers for backward compatibility
from warehouse_erp.security import (
    warehouse_has_permission,
    pick_list_has_permission,
    delivery_note_has_permission,
    serial_batch_bundle_has_permission,
    get_warehouse_conditions as get_operator_warehouse_conditions,
    get_pick_list_conditions as pick_list_conditions,
    get_delivery_note_conditions as delivery_note_conditions,
)


def has_app_access():
    """Determine desktop launcher tile visibility for the administrative Clothing ERP app."""
    return has_any_role({ROLE_BUSINESS_ADMIN})
