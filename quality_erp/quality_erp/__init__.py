"""Quality ERP: Supplier quality inspection, returns quarantine, and refurbishment lifecycle."""
__version__ = "1.0.0"

try:
    from quality_erp.boot import apply_runtime_patches
    apply_runtime_patches()
except Exception:
    pass

