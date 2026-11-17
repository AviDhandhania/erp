"""Centralized accessor for administrator-managed Clothing Sales Settings."""

import frappe
from frappe.utils import cint

DEFAULT_SALES_SETTINGS = {
    "rsm_cycle_days": 80,
    "rsm_warning_days": 70,
    "rsm_grace_days": 5,
    "rsm_escalation_days": 85,
    "sis_stock_review_cycle_days": 90,
    "sis_stock_review_warning_days": 80,
    "sis_stock_review_grace_days": 5,
    "sis_stock_review_escalation_days": 95,
    "sis_general_visit_cycle_days": 30,
    "sis_general_visit_warning_days": 25,
    "sis_general_visit_grace_days": 5,
    "buy_sell_visit_cycle_days": 30,
    "buy_sell_visit_warning_days": 25,
    "buy_sell_visit_grace_days": 5,
    "collection_window_start_days": 90,
    "collection_window_escalation_days": 120,
    "enforce_collection_hard_block": 1,
    "rsm_max_supervised_asms": 4,
    "rsm_max_retailer_capacity": 250,
    "capacity_warning_mode": "Warn",
    "spring_summer_start_month": 2,
    "autumn_winter_start_month": 8,
    "seasonal_prebooking_days": 60,
    "require_geolocation_checkin": 1,
    "geolocation_tolerance_meters": 500,
    "require_photo_evidence": 0,
}


def get_sales_settings() -> dict:
    """Retrieve administrator-managed Clothing Sales Settings with safe defaults fallback."""
    settings = dict(DEFAULT_SALES_SETTINGS)
    try:
        if frappe.db.exists("DocType", "Clothing Sales Settings"):
            doc = frappe.get_single("Clothing Sales Settings")
            for key in DEFAULT_SALES_SETTINGS:
                val = getattr(doc, key, None)
                if val is not None:
                    if isinstance(DEFAULT_SALES_SETTINGS[key], int):
                        settings[key] = cint(val)
                    else:
                        settings[key] = val
    except Exception:
        # Fall back gracefully to defaults during early boot, test setup or migration
        pass
    return settings
