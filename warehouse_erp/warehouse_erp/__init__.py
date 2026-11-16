"""Warehouse ERP: Warehouse operations, pick scanning, dispatch, and stock movements."""
__version__ = "1.0.0"

try:
    from warehouse_erp.boot import apply_runtime_patches
    apply_runtime_patches()
except Exception:
    pass

