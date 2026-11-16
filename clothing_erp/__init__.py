__version__ = "0.3.0"

try:
    import clothing_erp.insights_compat  # noqa: F401
except Exception:
    pass

try:
    from sales_erp.boot import apply_runtime_patches
    apply_runtime_patches()
except Exception:
    pass
