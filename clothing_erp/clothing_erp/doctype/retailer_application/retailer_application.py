"""Backward-compatibility re-export of Retailer Application controller and APIs."""
from sales_erp.sales_erp.doctype.retailer_application.retailer_application import (
    RetailerApplication,
    approve,
    reject,
    request_more_info,
    resubmit,
    get_territory_assignment,
    find_duplicates,
    validate_retailer_type,
)

__all__ = [
    "RetailerApplication",
    "approve",
    "reject",
    "request_more_info",
    "resubmit",
    "get_territory_assignment",
    "find_duplicates",
    "validate_retailer_type",
]
