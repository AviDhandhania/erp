"""Retailer visit reporting keeps native permissions and complete date boundaries."""

import unittest
from unittest.mock import patch

import frappe

from clothing_erp.clothing_erp.report.retailer_visit_report import retailer_visit_report


class TestRetailerVisitReport(unittest.TestCase):
    def test_report_uses_permission_aware_query_and_inclusive_to_date(self):
        rows = [
            frappe._dict(outcome="Follow-up Required"),
            frappe._dict(outcome="Issue Reported"),
        ]
        with patch.object(frappe, "get_list", return_value=rows) as get_list:
            columns, data, _, chart, summary = retailer_visit_report.execute(
                {
                    "from_date": "2026-11-01",
                    "to_date": "2026-11-08",
                    "customer": "TEST Retailer",
                }
            )
        kwargs = get_list.call_args.kwargs
        self.assertEqual(get_list.call_args.args[0], "Retailer Visit")
        self.assertNotIn("ignore_permissions", kwargs)
        self.assertEqual(
            kwargs["filters"],
            [
                ["visit_date", ">=", "2026-11-01"],
                ["visit_date", "<", "2026-11-09"],
                ["customer", "=", "TEST Retailer"],
            ],
        )
        self.assertEqual(len(columns), 7)
        self.assertEqual(data, rows)
        self.assertEqual(sum(chart["data"]["datasets"][0]["values"]), 2)
        self.assertEqual([row["value"] for row in summary], [2, 1, 1])

    def test_report_rejects_reversed_date_range_before_query(self):
        with (
            patch.object(frappe, "throw", side_effect=frappe.ValidationError),
            patch.object(frappe, "get_list") as get_list,
            self.assertRaises(frappe.ValidationError),
        ):
            retailer_visit_report.execute(
                {"from_date": "2026-11-09", "to_date": "2026-11-08"}
            )
        self.assertFalse(
            any(
                call.args and call.args[0] == "Retailer Visit"
                for call in get_list.call_args_list
            )
        )
