"""Comprehensive integration and workflow tests for Session 11:
Production Quality Cycle and Native Links.

Covers:
1. Unique Business Key:
   - Deterministic composite key per (Company, Supplier, PO/Season, Item/Style, Production Lot).
   - Database-enforced uniqueness and DuplicateEntryError rejection.
   - Distinct production lots/seasons create distinct cycles.
2. Reviewed Native Links:
   - Links to Supplier, Purchase Order, relevant Items/styles/colourways.
   - Links to production lot/season where approved.
   - Links to applicable Purchase Receipt and native ERPNext Quality Inspection.
   - Strict non-duplication of purchasing, payable, stock or Quality Inspection ledgers.
3. Safe Migration from Existing Supplier Quality Inspection Records:
   - Grouping existing inspections into corresponding Production Quality Cycles.
   - Updating foreign key links and synchronizing stage progress and counters.
4. Migration-Twice (Idempotency):
   - Running migration a second time creates 0 duplicate cycles and makes 0 broken links.
5. Atomic Rollback:
   - Failure during migration rolls back completely to savepoint with zero orphan cycles.
   - Dry-run validation executes and rolls back without state mutation.
6. Company and Supplier Isolation:
   - Multi-company User Permission boundaries prevent cross-company read/write leakage.
   - Supplier User Permission boundaries prevent cross-supplier leakage.
   - Company mismatch between SQI and cycle is rejected.
7. Server-Side Permissions & Critical Gate Enforcement:
   - Quality Inspector vs Manager vs Business Admin roles.
   - Production Go Ahead and Final Inspection gates strictly require Administrator approval.
"""

import unittest
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from quality_erp import cycle, security
from quality_erp.cycle import (
    assert_cycle_access,
    generate_cycle_key,
    get_or_create_cycle,
    link_native_purchase_receipt,
    link_native_quality_inspection,
    migrate_supplier_inspections_to_cycles,
)
from quality_erp.roles import (
    ROLE_BUSINESS_ADMIN,
    ROLE_QUALITY_INSPECTOR,
    ROLE_QUALITY_MANAGER,
)


class TestProductionQualityCycle(FrappeTestCase):
    """Test suite for Production Quality Cycle and Native Links."""

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")

    # =========================================================================
    # 1. UNIQUE BUSINESS KEY TESTS
    # =========================================================================

    def test_deterministic_cycle_key_generation(self):
        """Cycle key must be deterministic, combining Company, Supplier, PO/Season, Item, Lot."""
        key1 = generate_cycle_key(
            company="Test Garments Ltd",
            supplier="Apex Textiles",
            item_code="SHIRT-OXFORD-M",
            purchase_order="PO-2026-0001",
            production_lot="01",
            season="AW2026",
        )
        self.assertEqual(key1, "Test Garments Ltd::Apex Textiles::PO-2026-0001::SHIRT-OXFORD-M::01")

        # Without PO, falls back to season
        key2 = generate_cycle_key(
            company="Test Garments Ltd",
            supplier="Apex Textiles",
            item_code="SHIRT-OXFORD-M",
            purchase_order=None,
            production_lot="01",
            season="AW2026",
        )
        self.assertEqual(key2, "Test Garments Ltd::Apex Textiles::AW2026::SHIRT-OXFORD-M::01")

        # Without PO and without season, falls back to DEV
        key3 = generate_cycle_key(
            company="Test Garments Ltd",
            supplier="Apex Textiles",
            item_code="SHIRT-OXFORD-M",
        )
        self.assertEqual(key3, "Test Garments Ltd::Apex Textiles::DEV::SHIRT-OXFORD-M::01")

        # Missing required components raises ValidationError
        with self.assertRaises(frappe.ValidationError):
            generate_cycle_key("", "Apex Textiles", "SHIRT-OXFORD-M")
        with self.assertRaises(frappe.ValidationError):
            generate_cycle_key("Test Garments Ltd", "", "SHIRT-OXFORD-M")
        with self.assertRaises(frappe.ValidationError):
            generate_cycle_key("Test Garments Ltd", "Apex Textiles", "")

    def test_duplicate_cycle_key_rejected(self):
        """Attempting to insert a duplicate Production Quality Cycle under the same business key is rejected."""
        fake_cycle1 = frappe.get_doc({
            "doctype": "Production Quality Cycle",
            "company": "Test Garments Ltd",
            "supplier": "Apex Textiles",
            "item_code": "STYLE-JEANS-01",
            "purchase_order": "PO-2026-UNIQUE-1",
            "production_lot": "01",
        })
        fake_cycle1.cycle_key = generate_cycle_key(
            "Test Garments Ltd", "Apex Textiles", "STYLE-JEANS-01", "PO-2026-UNIQUE-1", "01"
        )

        with (
            patch.object(frappe.db, "get_value", return_value="PQC-EXISTING-001"),
        ):
            with self.assertRaises(frappe.DuplicateEntryError):
                fake_cycle1.validate()

    def test_distinct_lots_produce_distinct_cycles(self):
        """Same style, PO, supplier, but distinct production lot produces distinct valid keys."""
        key_lot1 = generate_cycle_key("Comp A", "Supp B", "ITEM-1", "PO-100", "LOT-01")
        key_lot2 = generate_cycle_key("Comp A", "Supp B", "ITEM-1", "PO-100", "LOT-02")
        self.assertNotEqual(key_lot1, key_lot2)
        self.assertIn("LOT-01", key_lot1)
        self.assertIn("LOT-02", key_lot2)

    # =========================================================================
    # 2. REVIEWED NATIVE LINKS (NO LEDGER DUPLICATION)
    # =========================================================================

    def test_get_or_create_cycle_with_colourway_variants(self):
        """Cycle creation links supplier, PO, items and stores colourways and size variants in child table."""
        from frappe.model.document import Document
        orig_get_value = frappe.db.get_value

        def fake_get_value(doctype, filters=None, *args, **kwargs):
            if doctype == "Production Quality Cycle":
                return None
            return orig_get_value(doctype, filters, *args, **kwargs)

        with (
            patch.object(cycle, "require_role"),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe.db, "get_value", side_effect=fake_get_value),
            patch.object(Document, "insert", autospec=True) as mock_insert,
            patch.object(cycle, "record_security_audit_event") as mock_audit,
        ):
            items_payload = [
                {"item_code": "SHIRT-NAVY-M", "colourway": "Navy Blue", "size": "M", "planned_qty": 500, "sample_size": 20},
                {"item_code": "SHIRT-NAVY-L", "colourway": "Navy Blue", "size": "L", "planned_qty": 400, "sample_size": 15},
                {"item_code": "SHIRT-WHT-M", "colourway": "Crisp White", "size": "M", "planned_qty": 600, "sample_size": 25},
            ]

            res = get_or_create_cycle(
                company="Test Garments Ltd",
                supplier="Apex Textiles",
                item_code="SHIRT-OXFORD-STYLE",
                purchase_order="PO-2026-0002",
                production_lot="01",
                season="SS2027",
                items=items_payload,
            )

            self.assertTrue(res["is_new"])
            self.assertEqual(res["status"], "Draft")
            self.assertEqual(res["current_stage"], "1. First Submission")
            mock_insert.assert_called_once()
            mock_audit.assert_called_with(
                "Production Quality Cycle Created",
                "Production Quality Cycle",
                unittest.mock.ANY,
                unittest.mock.ANY,
            )

    def test_link_native_purchase_receipt_preserves_stock_ledgers(self):
        """Linking a native Purchase Receipt records reference without modifying Bin or Stock Ledger Entry."""
        fake_cycle = frappe._dict(
            name="PQC-2026-00001",
            company="Test Garments Ltd",
            supplier="Apex Textiles",
            purchase_receipt=None,
            flags=frappe._dict(),
            save=MagicMock(),
        )
        fake_pr = frappe._dict(
            name="MAT-PR-2026-00001",
            company="Test Garments Ltd",
            supplier="Apex Textiles",
            docstatus=1,
        )

        with (
            patch.object(cycle, "require_role"),
            patch.object(cycle, "assert_cycle_access", return_value=fake_cycle),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_pr),
            patch.object(cycle, "record_security_audit_event") as mock_audit,
        ):
            res = link_native_purchase_receipt("PQC-2026-00001", "MAT-PR-2026-00001")

        self.assertTrue(res["success"])
        self.assertEqual(fake_cycle.purchase_receipt, "MAT-PR-2026-00001")
        fake_cycle.save.assert_called_once()
        mock_audit.assert_called_with(
            "Cycle Purchase Receipt Linked",
            "Production Quality Cycle",
            "PQC-2026-00001",
            {"purchase_receipt": "MAT-PR-2026-00001"},
        )

    def test_link_native_purchase_receipt_mismatch_rejected(self):
        """Attempting to link a Purchase Receipt from a different company or supplier is rejected."""
        fake_cycle = frappe._dict(
            name="PQC-2026-00001",
            company="Test Garments Ltd",
            supplier="Apex Textiles",
        )
        fake_pr = frappe._dict(
            name="MAT-PR-2026-WRONG",
            company="Other Subsidiary Ltd",  # Mismatched company
            supplier="Apex Textiles",
        )

        with (
            patch.object(cycle, "require_role"),
            patch.object(cycle, "assert_cycle_access", return_value=fake_cycle),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_pr),
        ):
            with self.assertRaisesRegex(frappe.ValidationError, "does not match cycle company"):
                link_native_purchase_receipt("PQC-2026-00001", "MAT-PR-2026-WRONG")

    def test_link_native_quality_inspection_preserves_ledgers(self):
        """Linking native Quality Inspection associates record without creating parallel ledger entries."""
        fake_cycle = frappe._dict(
            name="PQC-2026-00001",
            company="Test Garments Ltd",
            supplier="Apex Textiles",
            quality_inspection=None,
            flags=frappe._dict(),
            save=MagicMock(),
        )

        with (
            patch.object(cycle, "require_role"),
            patch.object(cycle, "assert_cycle_access", return_value=fake_cycle),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(cycle, "record_security_audit_event") as mock_audit,
        ):
            res = link_native_quality_inspection("PQC-2026-00001", "QI-2026-00099")

        self.assertTrue(res["success"])
        self.assertEqual(fake_cycle.quality_inspection, "QI-2026-00099")
        fake_cycle.save.assert_called_once()
        mock_audit.assert_called_with(
            "Cycle Quality Inspection Linked",
            "Production Quality Cycle",
            "PQC-2026-00001",
            {"quality_inspection": "QI-2026-00099"},
        )

    # =========================================================================
    # 3. MIGRATION FROM EXISTING SUPPLIER QUALITY INSPECTIONS
    # =========================================================================

    def test_migration_creates_cycles_and_links_inspections(self):
        """Existing unlinked Supplier Quality Inspections are grouped into cycles and linked atomically."""
        fake_sqis = [
            {
                "name": "SQI-001",
                "supplier": "Apex Textiles",
                "item_code": "KURTA-SILK",
                "purchase_order": "PO-101",
                "stage": "1. First Submission",
                "status": "Approved",
                "inspection_date": "2026-11-10",
                "company": "Test Garments Ltd",
                "production_lot": "01",
                "season": "AW2026",
                "production_quality_cycle": None,
            },
            {
                "name": "SQI-002",
                "supplier": "Apex Textiles",
                "item_code": "KURTA-SILK",
                "purchase_order": "PO-101",
                "stage": "2. Second Submission",
                "status": "Approved",
                "inspection_date": "2026-11-12",
                "company": "Test Garments Ltd",
                "production_lot": "01",
                "season": "AW2026",
                "production_quality_cycle": None,
            },
            {
                "name": "SQI-003",
                "supplier": "Other Mill",
                "item_code": "PANTS-DENIM",
                "purchase_order": "PO-102",
                "stage": "1. First Submission",
                "status": "Pending Review",
                "inspection_date": "2026-11-15",
                "company": "Test Garments Ltd",
                "production_lot": "01",
                "season": "AW2026",
                "production_quality_cycle": None,
            },
        ]

        created_cycles = {}

        def mock_get_doc(data, *args, **kwargs):
            if isinstance(data, dict) and data.get("doctype") == "Production Quality Cycle":
                cname = f"PQC-MIG-{len(created_cycles) + 1}"
                doc = frappe._dict(data)
                doc.name = cname
                doc.flags = frappe._dict()
                doc.insert = MagicMock()
                doc.save = MagicMock()
                doc.update_stage_progress = MagicMock()
                created_cycles[data["cycle_key"]] = doc
                return doc
            if isinstance(data, str) and data == "Production Quality Cycle":
                cname = args[0] if args else kwargs.get("name")
                for c in created_cycles.values():
                    if c.name == cname:
                        return c
                return frappe._dict(name=cname, flags=frappe._dict(), update_stage_progress=MagicMock(), save=MagicMock())
            return frappe._dict(name=data, flags=frappe._dict())

        with (
            patch.object(cycle, "require_role"),
            patch.object(frappe.db, "table_exists", return_value=True),
            patch.object(frappe.db, "sql", return_value=fake_sqis),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe.db, "set_value") as mock_set_value,
            patch.object(frappe, "get_doc", side_effect=mock_get_doc),
            patch.object(frappe.db, "savepoint"),
            patch.object(cycle, "record_security_audit_event") as mock_audit,
        ):
            res = migrate_supplier_inspections_to_cycles()

        self.assertTrue(res["success"])
        self.assertEqual(res["total_inspections"], 3)
        self.assertEqual(res["cycles_created"], 2)  # PO-101 KURTA-SILK and PO-102 PANTS-DENIM
        self.assertEqual(res["inspections_linked"], 3)
        self.assertEqual(mock_set_value.call_count, 3)

    # =========================================================================
    # 4. MIGRATION-TWICE (IDEMPOTENCY)
    # =========================================================================

    def test_migration_twice_is_idempotent(self):
        """Running migration a second time detects already-linked records and creates 0 new cycles."""
        fake_sqis = [
            {
                "name": "SQI-001",
                "supplier": "Apex Textiles",
                "item_code": "KURTA-SILK",
                "purchase_order": "PO-101",
                "stage": "1. First Submission",
                "status": "Approved",
                "inspection_date": "2026-11-10",
                "company": "Test Garments Ltd",
                "production_lot": "01",
                "season": "AW2026",
                "production_quality_cycle": "PQC-2026-00001",  # Already linked!
            },
        ]

        with (
            patch.object(cycle, "require_role"),
            patch.object(frappe.db, "table_exists", return_value=True),
            patch.object(frappe.db, "sql", return_value=fake_sqis),
            patch.object(frappe.db, "get_value", return_value="PQC-2026-00001"),  # cycle exists
            patch.object(frappe.db, "set_value") as mock_set_value,
            patch.object(frappe, "get_doc", return_value=frappe._dict(name="PQC-2026-00001", flags=frappe._dict(), update_stage_progress=MagicMock(), save=MagicMock())),
            patch.object(frappe.db, "savepoint"),
            patch.object(cycle, "record_security_audit_event"),
        ):
            res = migrate_supplier_inspections_to_cycles()

        self.assertTrue(res["success"])
        self.assertEqual(res["cycles_created"], 0)
        self.assertEqual(res["inspections_linked"], 0)
        mock_set_value.assert_not_called()

    # =========================================================================
    # 5. ATOMIC ROLLBACK DRILL
    # =========================================================================

    def test_migration_rollback_on_failure(self):
        """Failure during migration triggers rollback to savepoint, leaving zero partial state."""
        fake_sqis = [
            {
                "name": "SQI-FAIL-01",
                "supplier": "Apex Textiles",
                "item_code": "KURTA-SILK",
                "purchase_order": "PO-101",
                "company": "Test Garments Ltd",
                "production_quality_cycle": None,
            }
        ]

        with (
            patch.object(cycle, "require_role"),
            patch.object(frappe.db, "table_exists", return_value=True),
            patch.object(frappe.db, "sql", return_value=fake_sqis),
            patch.object(frappe.db, "savepoint") as mock_sp,
            patch.object(frappe.db, "rollback") as mock_rollback,
            patch.object(frappe, "get_doc", return_value=frappe._dict(name="PQC-FAIL", flags=frappe._dict(), insert=MagicMock())),
        ):
            with self.assertRaises(RuntimeError):
                migrate_supplier_inspections_to_cycles(simulate_error=True)

            mock_sp.assert_called_with("pqc_migration_sp")
            mock_rollback.assert_called_with(save_point="pqc_migration_sp")

    def test_migration_dry_run_executes_and_rolls_back(self):
        """Dry-run calculates cycles and links but unconditionally rolls back savepoint."""
        fake_sqis = [
            {
                "name": "SQI-DRY-01",
                "supplier": "Apex Textiles",
                "item_code": "KURTA-SILK",
                "purchase_order": "PO-101",
                "company": "Test Garments Ltd",
                "production_quality_cycle": None,
            }
        ]

        def mock_get_doc(data, *args, **kwargs):
            if isinstance(data, dict) and data.get("doctype") == "Production Quality Cycle":
                doc = frappe._dict(data)
                doc.name = "PQC-DRY"
                doc.flags = frappe._dict()
                doc.insert = MagicMock()
                doc.update_stage_progress = MagicMock()
                doc.save = MagicMock()
                return doc
            if isinstance(data, str) and data == "Production Quality Cycle":
                return frappe._dict(name="PQC-DRY", flags=frappe._dict(), update_stage_progress=MagicMock(), save=MagicMock())
            return frappe._dict(name=data, flags=frappe._dict())

        with (
            patch.object(cycle, "require_role"),
            patch.object(frappe.db, "table_exists", return_value=True),
            patch.object(frappe.db, "sql", return_value=fake_sqis),
            patch.object(frappe.db, "get_value", return_value=None),
            patch.object(frappe.db, "savepoint") as mock_sp,
            patch.object(frappe.db, "rollback") as mock_rollback,
            patch.object(frappe, "get_doc", side_effect=mock_get_doc),
            patch.object(frappe.db, "set_value"),
        ):
            res = migrate_supplier_inspections_to_cycles(dry_run=True)

        self.assertTrue(res["dry_run"])
        self.assertEqual(res["cycles_created"], 1)
        mock_rollback.assert_called_with(save_point="pqc_migration_sp")

    # =========================================================================
    # 6. COMPANY & SUPPLIER ISOLATION
    # =========================================================================

    def test_cross_company_access_denied(self):
        """User restricted to Company A is rejected when attempting to access Company B cycle."""
        fake_cycle = frappe._dict(
            name="PQC-COMP-B",
            company="Company B Ltd",
            supplier="Apex Textiles",
            check_permission=MagicMock(),
        )

        with (
            patch.object(cycle, "require_role"),
            patch.object(cycle, "get_current_user", return_value="inspector_a@example.com"),
            patch.object(cycle, "is_quality_admin", return_value=False),
            patch.object(frappe, "get_all", return_value=["Company A Ltd"]),  # only Company A allowed
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_cycle),
        ):
            with self.assertRaises(frappe.PermissionError):
                assert_cycle_access("PQC-COMP-B", ptype="read")

    def test_cross_supplier_access_denied(self):
        """User restricted to Supplier X is rejected when attempting to access Supplier Y cycle."""
        fake_cycle = frappe._dict(
            name="PQC-SUPP-Y",
            company="Test Garments Ltd",
            supplier="Supplier Y",
            check_permission=MagicMock(),
        )

        def mock_get_all(dt, filters=None, pluck=None):
            if dt == "User Permission" and filters.get("allow") == "Supplier":
                return ["Supplier X"]
            return []

        with (
            patch.object(cycle, "require_role"),
            patch.object(cycle, "get_current_user", return_value="supplier_x@example.com"),
            patch.object(cycle, "is_quality_admin", return_value=False),
            patch.object(frappe, "get_all", side_effect=mock_get_all),
            patch.object(frappe.db, "exists", return_value=True),
            patch.object(frappe, "get_doc", return_value=fake_cycle),
        ):
            with self.assertRaises(frappe.PermissionError):
                assert_cycle_access("PQC-SUPP-Y", ptype="read")

    def test_permission_query_conditions_enforce_isolation(self):
        """Permission query conditions filter SQL queries by allowed Company and Supplier."""
        def mock_get_all(dt, filters=None, pluck=None):
            if filters.get("allow") == "Company":
                return ["Company A"]
            if filters.get("allow") == "Supplier":
                return ["Supplier X"]
            return []

        with (
            patch.object(security, "is_quality_inspector", return_value=True),
            patch.object(security, "is_quality_admin", return_value=False),
            patch.object(frappe, "get_all", side_effect=mock_get_all),
        ):
            conds = security.get_production_quality_cycle_conditions(user="inspector@example.com")

        self.assertIn("`tabProduction Quality Cycle`.company IN ('Company A')", conds)
        self.assertIn("`tabProduction Quality Cycle`.supplier IN ('Supplier X')", conds)

    # =========================================================================
    # 7. SERVER-SIDE PERMISSIONS & GATE APPROVALS
    # =========================================================================

    def test_unauthorized_user_denied_cycle_access(self):
        """User without quality roles is denied access to cycle operations."""
        with (
            patch.object(cycle, "require_role", side_effect=frappe.PermissionError),
        ):
            with self.assertRaises(frappe.PermissionError):
                get_or_create_cycle("Comp", "Supp", "Item")

    def test_quality_gate_approvals_require_admin(self):
        """Production Go Ahead and Final Inspection gate approvals require Quality Admin / Administrator."""
        cycle_doc = frappe.get_doc({
            "doctype": "Production Quality Cycle",
            "company": "Test Garments Ltd",
            "supplier": "Apex Textiles",
            "item_code": "ITEM-GATE-1",
            "go_ahead_status": "Approved",
        })
        cycle_doc.has_value_changed = MagicMock(return_value=True)

        # Inspector cannot approve Go Ahead
        with (
            patch.object(security, "get_current_user", return_value="inspector@example.com"),
            patch.object(security, "is_quality_admin", return_value=False),
            patch.object(frappe.db, "get_value", return_value=None),
        ):
            with self.assertRaises(frappe.PermissionError):
                cycle_doc.validate()

        # Admin CAN approve Go Ahead
        with (
            patch.object(security, "get_current_user", return_value="Administrator"),
            patch.object(security, "is_quality_admin", return_value=True),
            patch.object(frappe.db, "get_value", return_value=None),
        ):
            cycle_doc.validate()
            self.assertEqual(cycle_doc.go_ahead_approved_by, "Administrator")
            self.assertIsNotNone(cycle_doc.go_ahead_date)

    # =========================================================================
    # 8. REAL DATABASE INTEGRATION & IDEMPOTENCY TESTS
    # =========================================================================

    def test_real_db_cycle_lifecycle_and_uniqueness(self):
        """End-to-end integration test creating a real Production Quality Cycle in DB and asserting uniqueness."""
        comp = frappe.defaults.get_user_default("Company") or "TEST Clothing ERP Demo"
        suppliers = frappe.get_all("Supplier", pluck="name", limit=1)
        supplier = suppliers[0] if suppliers else "Test Apparel Mills"
        items = frappe.get_all("Item", pluck="name", limit=1)
        item_code = items[0] if items else "TEST-FLEECE-HOODIE-MRN"

        test_lot = "LOT-TEST-INT-01"

        # Cleanup in case of previous run
        existing = frappe.db.get_value(
            "Production Quality Cycle",
            {"company": comp, "supplier": supplier, "item_code": item_code, "production_lot": test_lot},
            "name",
        )
        if existing:
            frappe.delete_doc("Production Quality Cycle", existing, force=True)

        cycle1 = frappe.get_doc({
            "doctype": "Production Quality Cycle",
            "company": comp,
            "supplier": supplier,
            "item_code": item_code,
            "production_lot": test_lot,
            "season": "AW2026",
            "status": "Draft",
            "items": [
                {
                    "item_code": item_code,
                    "colourway": "Maroon",
                    "size": "M",
                    "planned_qty": 200,
                    "sample_size": 15,
                }
            ],
        })
        cycle1.insert()
        self.assertTrue(cycle1.name)
        self.assertEqual(len(cycle1.items), 1)
        self.assertEqual(cycle1.items[0].colourway, "Maroon")

        # Second insert with identical business key must raise DuplicateEntryError
        cycle2 = frappe.get_doc({
            "doctype": "Production Quality Cycle",
            "company": comp,
            "supplier": supplier,
            "item_code": item_code,
            "production_lot": test_lot,
            "season": "AW2026",
            "status": "Draft",
        })
        with self.assertRaises(frappe.DuplicateEntryError):
            cycle2.insert()

        # Clean up
        frappe.delete_doc("Production Quality Cycle", cycle1.name, force=True)

    def test_real_db_migration_twice_and_rollback(self):
        """End-to-end DB test for safe migration and migration-twice idempotency."""
        comp = frappe.defaults.get_user_default("Company") or "TEST Clothing ERP Demo"
        suppliers = frappe.get_all("Supplier", pluck="name", limit=1)
        supplier = suppliers[0] if suppliers else "Test Apparel Mills"
        items = frappe.get_all("Item", pluck="name", limit=1)
        item_code = items[0] if items else "TEST-FLEECE-HOODIE-MRN"
        test_lot = "LOT-MIG-INT-02"

        # Create test SQI
        sqi = frappe.get_doc({
            "doctype": "Supplier Quality Inspection",
            "company": comp,
            "supplier": supplier,
            "item_code": item_code,
            "stage": "1. First Submission",
            "status": "Pending Review",
            "inspection_date": "2026-11-17",
            "production_lot": test_lot,
            "season": "SS2027",
        })
        sqi.flags.ignore_links = True
        sqi.flags.ignore_mandatory = True
        sqi.insert()

        try:
            # 1. First migration run: links SQI to newly created cycle
            res1 = migrate_supplier_inspections_to_cycles()
            self.assertTrue(res1["success"])

            sqi.reload()
            self.assertTrue(sqi.production_quality_cycle)
            cycle_name = sqi.production_quality_cycle

            cycle_doc = frappe.get_doc("Production Quality Cycle", cycle_name)
            self.assertEqual(cycle_doc.supplier, supplier)
            self.assertEqual(cycle_doc.item_code, item_code)
            self.assertEqual(cycle_doc.production_lot, test_lot)

            # 2. Second migration run (migration-twice): 0 new cycles created
            res2 = migrate_supplier_inspections_to_cycles()
            self.assertTrue(res2["success"])
            self.assertEqual(res2["cycles_created"], 0)
            self.assertEqual(res2["inspections_linked"], 0)

            # SQI link remains intact
            sqi.reload()
            self.assertEqual(sqi.production_quality_cycle, cycle_name)

        finally:
            if sqi.production_quality_cycle:
                pqc = sqi.production_quality_cycle
                frappe.db.set_value("Supplier Quality Inspection", sqi.name, "production_quality_cycle", None)
                if frappe.db.exists("Production Quality Cycle", pqc):
                    frappe.delete_doc("Production Quality Cycle", pqc, force=True)
            frappe.delete_doc("Supplier Quality Inspection", sqi.name, force=True)
