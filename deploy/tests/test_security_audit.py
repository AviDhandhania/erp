# Copyright (c) 2026, Clothing ERP Contributors
# License: MIT. See LICENSE

import ast
import os
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP_NAMES = ("sales_erp", "warehouse_erp", "quality_erp")

# Approved ledger of runtime non-test ignore_permissions=True occurrences
# Format: (relative_file_path, function_or_scope, justification)
APPROVED_RUNTIME_IGNORE_PERMISSIONS = {
    ("sales_erp/sales_erp/gallery.py", "_delete_orphan", "Scheduled background cleaner of orphaned temporary images"),
    ("sales_erp/sales_erp/ordering.py", "create_draft_sales_order", "Inserts draft Sales Order after validating ASM territory ownership and credit exposure"),
    ("sales_erp/sales_erp/ordering.py", "reject_clothing_order", "Updates rejection reason and adds workflow comment on draft order under row lock"),
    ("sales_erp/sales_erp/ordering.py", "resubmit_clothing_order", "Updates and resubmits draft Sales Order after validating territory scope and credit exposure"),
    ("sales_erp/sales_erp/ordering.py", "amend_clothing_order", "Creates amended draft Sales Order from cancelled order after validating territory scope and credit exposure"),
    ("sales_erp/sales_erp/pricing.py", "set_template_price", "Admin-only template pricing update for size variants"),
    ("sales_erp/sales_erp/retailer_assignment.py", "_replace_assignment", "Admin-only territory/salesperson reassignment with customer row-lock"),
    ("sales_erp/sales_erp/retailer_defaults.py", "ensure_retailer_defaults", "Idempotent customer group hierarchy provisioning"),
    ("sales_erp/sales_erp/sales_erp/doctype/retailer_application/retailer_application.py", "_make_contact", "Creates primary Contact after RSM approval"),
    ("sales_erp/sales_erp/sales_erp/doctype/retailer_application/retailer_application.py", "_make_address", "Creates Billing/Shipping Address after RSM approval"),
    ("sales_erp/sales_erp/sales_erp/doctype/retailer_application/retailer_application.py", "approve", "Creates ERPNext Customer after RSM approves application under row lock"),
    ("sales_erp/sales_erp/sales_erp/doctype/retailer_credit_limit_request/retailer_credit_limit_request.py", "approve_credit_limit_request", "Admin-only customer credit limit change under row-lock"),
    ("sales_erp/sales_erp/sales_erp/doctype/retailer_credit_limit_request/retailer_credit_limit_request.py", "reject_credit_limit_request", "Admin-only credit limit rejection with mandatory reason"),
    ("sales_erp/sales_erp/sales_erp/doctype/retailer_visit/retailer_visit.py", "review_visit", "RSM-only supervisory review of completed visit"),
    ("sales_erp/sales_erp/supervision.py", "_ensure_territory_permission", "Admin-only maintenance of native Territory User Permissions"),
    ("sales_erp/sales_erp/supervision.py", "remove_assignment_permissions", "Admin-only removal of Territory User Permissions on reassignment"),
    ("sales_erp/sales_erp/supervision.py", "record_assignment_history", "Admin-only territory assignment history record"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "_close_pick_assignments", "Closes open Frappe ToDo assignments upon pick completion under row lock"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "verify_pick_item", "Updates Pick List item scanned count under warehouse permission and row lock"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "undo_pick_item_scan", "Reverses scanned pick count under warehouse permission and row lock"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "split_pick_shortage_row", "Splits shortage pick item under warehouse permission and row lock"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "complete_pick_list", "Submits Pick List and closes open assignments under row lock"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "create_packing_slip", "Creates native Packing Slip under warehouse permission and row lock"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "dispatch_delivery_note", "Submits Delivery Note after validating warehouse permission and LR details"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "create_pick_list_from_sales_orders", "Creates native Pick List from submitted Sales Orders under warehouse permission and row lock"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "prepare_billing_from_delivery_note", "Creates draft Sales Invoice from Delivery Note without granting billing submission rights"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "record_delivery_handoff", "Inserts immutable Delivery Handoff record with carrier signature and proof photo"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "assign_to_wave", "Updates custom wave ID on Pick Lists after checking write permission"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "assign_to_route", "Updates custom route ID on Delivery Notes after checking write permission"),
    ("warehouse_erp/warehouse_erp/fulfillment.py", "update_transport_metadata", "Updates transport fields on Delivery Note after checking write permission"),
    ("sales_erp/sales_erp/file_security.py", "save_secure_file", "Inserts private File document after validating content bytes, magic signature, and decompression bounds"),
    ("sales_erp/sales_erp/file_security.py", "reference_safe_delete_file", "Deletes unreferenced local File document after verifying zero active references across suite"),
    ("quality_erp/quality_erp/file_security.py", "save_secure_file", "Inserts private File document after validating content bytes, magic signature, and decompression bounds"),
    ("quality_erp/quality_erp/file_security.py", "reference_safe_delete_file", "Deletes unreferenced local File document after verifying zero active references across suite"),
    ("warehouse_erp/warehouse_erp/file_security.py", "save_secure_file", "Inserts private File document after validating content bytes, magic signature, and decompression bounds"),
    ("warehouse_erp/warehouse_erp/barcodes.py", "allocate_item_barcode", "Allocates immutable barcode to Item after role validation, check-digit verification and collision check"),
}


class TestSecurityAudit(unittest.TestCase):
    """Automated static analysis asserting security invariants across all suite applications."""

    def _iter_python_files(self, exclude_tests=False):
        for app in APP_NAMES:
            app_dir = os.path.join(REPO_ROOT, app)
            for root, _, files in os.walk(app_dir):
                for f in files:
                    if not f.endswith(".py"):
                        continue
                    if exclude_tests and ("/tests/" in root or f.startswith("test_")):
                        continue
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, REPO_ROOT)
                    yield full_path, rel_path

    def test_mutating_endpoints_enforce_post(self):
        """Every whitelisted endpoint that performs data mutations must explicitly require methods=['POST']."""
        mutating_prefixes = (
            "create_", "set_", "submit_", "cancel_", "approve_", "reject_",
            "reassign_", "bulk_reassign", "assign_", "end_", "record_",
            "review_", "resubmit_", "request_more_info", "verify_", "undo_",
            "resolve_", "split_", "complete_", "dispatch_", "bulk_dispatch",
            "intake_", "move_", "switch_preview"
        )

        violations = []
        for full_path, rel_path in self._iter_python_files(exclude_tests=True):
            with open(full_path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=full_path)
                except SyntaxError:
                    continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue

                for dec in node.decorator_list:
                    is_whitelist = False
                    methods = []

                    if isinstance(dec, ast.Attribute) and dec.attr == "whitelist":
                        is_whitelist = True
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr == "whitelist":
                        is_whitelist = True
                        for kw in dec.keywords:
                            if kw.arg == "methods" and isinstance(kw.value, ast.List):
                                methods = [
                                    elt.s if hasattr(elt, "s") else elt.value
                                    for elt in kw.value.elts
                                ]

                    if is_whitelist:
                        fn_name = node.name
                        is_mutating_name = any(fn_name.startswith(p) for p in mutating_prefixes)
                        if is_mutating_name and "POST" not in methods:
                            violations.append(
                                f"{rel_path}:{node.lineno} -> {fn_name}() accepts methods={methods or 'ALL'}"
                            )

        self.assertEqual(
            violations,
            [],
            "Mutating whitelisted endpoints must explicitly declare methods=['POST']:\n" + "\n".join(violations)
        )

    def test_raw_sql_queries_are_parameterized(self):
        """All frappe.db.sql calls must use parameter bindings; no direct unsanitized variable interpolation."""
        violations = []
        for full_path, rel_path in self._iter_python_files(exclude_tests=True):
            with open(full_path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=full_path)
                except SyntaxError:
                    continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                # Detect frappe.db.sql(...)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == "db"
                    and node.func.attr == "sql"
                ):
                    first_arg = node.args[0] if node.args else None
                    if first_arg is None:
                        continue

                    # If it's a format call or % op without parameterized args
                    has_params = len(node.args) > 1 or any(
                        k.arg in ("values", "params") for k in node.keywords
                    )

                    # Check for direct % formatting on the string (e.g. "SELECT ... %s" % var)
                    if isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, ast.Mod):
                        violations.append(
                            f"{rel_path}:{node.lineno}: Unsafe % string formatting used inside frappe.db.sql"
                        )
                    # Check for f-string without parameters
                    elif isinstance(first_arg, ast.JoinedStr):
                        # Allowed exceptions: dynamic placeholders like `, `.join(['%s'] * len(items))
                        # or internal where_clause constructed with '%s' where params are passed
                        if not has_params:
                            # If no params are passed, f-string into SQL is strictly forbidden
                            src = ast.unparse(first_arg)
                            violations.append(
                                f"{rel_path}:{node.lineno}: f-string SQL query has no query parameters: {src[:60]}"
                            )

        self.assertEqual(
            violations,
            [],
            "Unsafe SQL query formatting detected:\n" + "\n".join(violations)
        )

    def test_ignore_permissions_must_be_in_approved_ledger(self):
        """Every runtime ignore_permissions=True in production code must be recorded in the approved ledger."""
        unapproved = []
        for full_path, rel_path in self._iter_python_files(exclude_tests=True):
            # Skip install and seed scripts which are CLI/migration only
            if rel_path.endswith("/install.py") or rel_path.endswith("/seed.py"):
                continue

            with open(full_path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=full_path)
                except SyntaxError:
                    continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                uses_ignore_permissions = False
                for kw in node.keywords:
                    if kw.arg == "ignore_permissions":
                        if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            uses_ignore_permissions = True

                if uses_ignore_permissions:
                    # Determine enclosing function name
                    fn_name = "module_level"
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.FunctionDef):
                            for subnode in ast.walk(parent):
                                if subnode is node:
                                    fn_name = parent.name
                                    break

                    registered = False
                    for app_file, app_fn, _ in APPROVED_RUNTIME_IGNORE_PERMISSIONS:
                        if rel_path == app_file and (fn_name == app_fn or app_fn == "*"):
                            registered = True
                            break

                    if not registered:
                        unapproved.append(
                            f"{rel_path}:{node.lineno} in {fn_name}() uses ignore_permissions=True without ledger approval"
                        )

        self.assertEqual(
            unapproved,
            [],
            "Unreviewed runtime ignore_permissions=True found. Each must be audited and registered:\n"
            + "\n".join(unapproved)
        )


if __name__ == "__main__":
    unittest.main()
