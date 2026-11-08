"""Permission-aware operational report over app-owned Retailer Visit records."""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, getdate

from clothing_erp.roles import ROLE_BUSINESS_ADMIN, ROLE_SALES_MANAGER
from clothing_erp.security import require_role

OUTCOMES = (
    "Order Expected",
    "Follow-up Required",
    "No Requirement",
    "Issue Reported",
    "Closed",
)


def execute(filters=None):
    require_role({ROLE_SALES_MANAGER, ROLE_BUSINESS_ADMIN})
    filters = frappe._dict(filters or {})
    _validate_dates(filters)
    data = _get_data(filters)
    counts = Counter(row.outcome for row in data)
    chart = {
        "data": {
            "labels": [_(outcome) for outcome in OUTCOMES],
            "datasets": [
                {
                    "name": _("Visits"),
                    "values": [counts[outcome] for outcome in OUTCOMES],
                }
            ],
        },
        "type": "bar",
    }
    summary = [
        {
            "value": len(data),
            "label": _("Visits"),
            "datatype": "Int",
            "indicator": "Blue",
        },
        {
            "value": counts["Follow-up Required"],
            "label": _("Follow-ups"),
            "datatype": "Int",
            "indicator": "Orange",
        },
        {
            "value": counts["Issue Reported"],
            "label": _("Issues"),
            "datatype": "Int",
            "indicator": "Red",
        },
    ]
    return _columns(), data, None, chart, summary


def _validate_dates(filters):
    if (
        filters.from_date
        and filters.to_date
        and getdate(filters.from_date) > getdate(filters.to_date)
    ):
        frappe.throw(_("From Date cannot be after To Date."))


def _get_data(filters):
    query_filters = []
    if filters.from_date:
        query_filters.append(["visit_date", ">=", filters.from_date])
    if filters.to_date:
        query_filters.append(["visit_date", "<", add_days(filters.to_date, 1)])
    for fieldname in ("customer", "salesperson", "outcome"):
        if filters.get(fieldname):
            query_filters.append([fieldname, "=", filters.get(fieldname)])
    return frappe.get_list(
        "Retailer Visit",
        filters=query_filters,
        fields=[
            "name",
            "customer",
            "salesperson",
            "visit_date",
            "outcome",
            "follow_up_date",
            "notes",
        ],
        order_by="visit_date desc, name desc",
        limit_page_length=0,
    )


def _columns():
    return [
        {
            "label": _("Visit"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Retailer Visit",
            "width": 150,
        },
        {
            "label": _("Visit Date"),
            "fieldname": "visit_date",
            "fieldtype": "Datetime",
            "width": 150,
        },
        {
            "label": _("Retailer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 190,
        },
        {
            "label": _("Salesperson User"),
            "fieldname": "salesperson",
            "fieldtype": "Link",
            "options": "User",
            "width": 190,
        },
        {
            "label": _("Outcome"),
            "fieldname": "outcome",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": _("Follow-up Date"),
            "fieldname": "follow_up_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {"label": _("Notes"), "fieldname": "notes", "fieldtype": "Data", "width": 300},
    ]
