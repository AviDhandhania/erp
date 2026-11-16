"""Sales ERP: Wholesale apparel sales, catalog, ordering, and territory management."""
__version__ = "1.0.0"

try:
    from sales_erp.boot import apply_runtime_patches
    apply_runtime_patches()
except Exception:
    pass

